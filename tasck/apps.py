# tasck/apps.py
from django.apps import AppConfig

class TasckConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tasck"

    def ready(self):
        # importa os signals do app
        from . import signals  # noqa: F401
