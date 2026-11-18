from django.contrib import admin

from .models import Recommendation, RecommendationSet


class RecommendationInline(admin.TabularInline):
    model = Recommendation
    extra = 0


@admin.register(RecommendationSet)
class RecommendationSetAdmin(admin.ModelAdmin):
    list_display = ("user", "model", "created_at")
    search_fields = ("user__username",)
    inlines = [RecommendationInline]
