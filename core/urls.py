# core/urls.py
from django.contrib import admin
from django.urls import path, include  # <-- IMPORTANTE
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),  # signup/login/lista do Gitea
    path("projects/", include("projects.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)