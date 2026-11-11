from django.contrib import admin

from .models import Visitor


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("id", "variant", "impression_at", "clicked_at")
    list_filter = ("variant",)
