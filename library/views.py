import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import NetflixUploadForm
from .importers import MAX_UPLOAD_BYTES, CSVImportError, import_viewing_history, parse_netflix_csv
from .models import RankedTitle
from .ranking import InvalidPick, next_pair, ranked_list, record_pick
from .services import SERVICES, SERVICES_BY_SLUG

logger = logging.getLogger(__name__)

# Room for the multipart boundaries and the CSRF field around a 5 MB file.
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 64 * 1024


@login_required
def choose_service(request):
    return render(request, "library/choose_service.html", {"services": SERVICES})


@login_required
@require_http_methods(["GET", "POST"])
def service_import(request, slug):
    service = SERVICES_BY_SLUG.get(slug)
    if service is None:
        raise Http404("Unknown streaming service")
    if not service.supported:
        return render(request, "library/coming_soon.html", {"service": service, "services": SERVICES})

    form = NetflixUploadForm()
    error = None
    if request.method == "POST":
        # Refuse oversized uploads before Django reads (and spools) the body.
        if int(request.META.get("CONTENT_LENGTH") or 0) > MAX_REQUEST_BYTES:
            error = "That file is larger than 5 MB. Netflix history files are much smaller."
        else:
            form = NetflixUploadForm(request.POST, request.FILES)
            if form.is_valid():
                upload = form.cleaned_data["file"]
                try:
                    rows = parse_netflix_csv(upload.read())
                except CSVImportError as exc:
                    error = str(exc)
                else:
                    result = import_viewing_history(request.user, rows)
                    logger.info(
                        "netflix import user=%s rows=%s new_rows=%s titles=%s",
                        request.user.pk,
                        result.rows_in_file,
                        result.new_rows,
                        result.titles_in_file,
                    )
                    messages.success(request, _import_message(result))
                    return redirect("dashboard")
    return render(request, "library/netflix.html", {"service": service, "form": form, "error": error})


def _import_message(result):
    titles = f"{result.titles_in_file} title{'s' if result.titles_in_file != 1 else ''}"
    rows = f"{result.rows_in_file} viewing record{'s' if result.rows_in_file != 1 else ''}"
    if result.new_rows == 0:
        return f"Imported {titles} from {rows}. Everything in this file was already in your history, so nothing was added."
    message = f"Imported {titles} from {rows}: {result.new_rows} new"
    if result.duplicate_rows:
        message += f", {result.duplicate_rows} already in your history"
    return message + "."


@login_required
@require_http_methods(["GET", "POST"])
def rank(request):
    if request.method == "POST":
        try:
            record_pick(request.user, int(request.POST["winner"]), int(request.POST["loser"]))
        except (KeyError, ValueError, InvalidPick):
            messages.error(request, "That pick didn't work. Try this pair instead.")
        return redirect("rank")

    avoid = None
    skip = request.GET.get("skip", "")
    if "-" in skip:
        try:
            avoid = tuple(int(part) for part in skip.split("-", 1))
        except ValueError:
            avoid = None

    pair = next_pair(request.user, avoid=avoid)
    picks = request.user.comparisons.count()
    return render(request, "library/rank.html", {"pair": pair, "picks": picks})


@login_required
def my_ranking(request):
    ranked = list(ranked_list(request.user))
    unranked = RankedTitle.objects.filter(user=request.user, wins=0, losses=0).count()
    return render(request, "library/ranking.html", {"ranked": ranked, "unranked": unranked})
