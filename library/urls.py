from django.urls import path

from . import views

urlpatterns = [
    path("import/", views.choose_service, name="choose_service"),
    path("import/<slug:slug>/", views.service_import, name="service_import"),
    path("rank/", views.rank, name="rank"),
    path("rankings/", views.my_ranking, name="my_ranking"),
]
