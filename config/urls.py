from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path("", core_views.home, name="home"),
    path("signup/", core_views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", core_views.dashboard, name="dashboard"),
    path("healthz", core_views.healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("", include("abtest.urls")),
]
