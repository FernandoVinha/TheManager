# core/urls.py
from django.contrib import admin
from django.urls import path, include  # <-- IMPORTANTE

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),  # signup/login/lista do Gitea
    path("projects/", include("projects.urls")),
]
