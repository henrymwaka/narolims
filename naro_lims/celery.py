# naro_lims/celery.py
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "naro_lims.settings")

app = Celery("naro_lims")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
