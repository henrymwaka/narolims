# lims_core/apps.py
from django.apps import AppConfig


class LimsCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lims_core"

    def ready(self):
        from . import signals  # noqa
