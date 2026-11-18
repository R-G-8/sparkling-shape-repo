from django import forms

from .importers import MAX_UPLOAD_BYTES


class NetflixUploadForm(forms.Form):
    file = forms.FileField(
        label="NetflixViewingHistory.csv",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Choose a .csv file. Netflix's download is called NetflixViewingHistory.csv.")
        if upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("That file is larger than 5 MB. Netflix history files are much smaller.")
        return upload
