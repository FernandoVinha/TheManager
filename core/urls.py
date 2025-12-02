# core/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),

    # Accounts (login/signup)
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),

    # Projects com namespace "projects"
    path(
        "projects/",
        include(("projects.urls", "projects"), namespace="projects"),
    ),

    # Tasck (kanban, tasks, etc)
    path("", include(("tasck.urls", "tasck"), namespace="tasck")),

    # System settings (email, gitea, openai, etc)
    path(
        "settings/",
        include(("system_settings.urls", "system_settings"), namespace="system_settings"),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
