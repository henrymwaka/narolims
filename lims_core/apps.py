# lims_core/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class LimsCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lims_core"

    def ready(self):
        # Always safe
        from . import signals  # noqa

        # Register Django system checks only
        try:
            from .checks import metadata_renderers  # noqa
        except Exception as exc:
            logger.warning(
                "Metadata renderer checks not registered: %s",
                exc,
            )
