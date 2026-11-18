from django.contrib import admin

from .models import Comparison, RankedTitle, Title, ViewingActivity


@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(ViewingActivity)
class ViewingActivityAdmin(admin.ModelAdmin):
    list_display = ("raw_title", "watched_on", "user", "service", "imported_at")
    list_filter = ("service",)
    search_fields = ("raw_title", "user__username")
    raw_id_fields = ("title",)


@admin.register(RankedTitle)
class RankedTitleAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "rating", "wins", "losses")
    search_fields = ("title__name", "user__username")
    raw_id_fields = ("title",)


@admin.register(Comparison)
class ComparisonAdmin(admin.ModelAdmin):
    list_display = ("winner", "loser", "user", "created_at")
    search_fields = ("user__username",)
    raw_id_fields = ("winner", "loser")
