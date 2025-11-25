from django.urls import path
from . import views

app_name = "system_settings"

urlpatterns = [
    path("", views.settings_home_view, name="home"),
    path("email/", views.email_settings_view, name="email_settings"),
    path("gitea/", views.gitea_settings_view, name="gitea_settings"),
]
