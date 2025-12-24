# lims_core/tasks.py
from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

from lims_core.workflows.sla_scanner import check_sla_breaches


@shared_task
def scan_workflow_sla(created_by_user_id: int | None = None) -> int:
    user = None
    if created_by_user_id:
        User = get_user_model()
        user = User.objects.filter(id=created_by_user_id).first()

    return check_sla_breaches(created_by=user)
