# lims_core/services/workflow_service.py
"""
Workflow transition service.

This module is kept for backward compatibility with older internal call sites.

Authoritative behavior is implemented in:
- lims_core.workflows.executor.execute_transition (policy: terminal lock, legality, roles)
- lims_core.workflows.transition_service.transition_object (mechanics: write status, WorkflowTransition, resolve alerts)

Rule:
- Do not implement independent workflow logic here.
- Delegate to executor to prevent policy drift.
"""

from __future__ import annotations

from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied

from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

from lims_core.workflows.executor import execute_transition as _execute_transition


@transaction.atomic
def perform_workflow_transition(
    *,
    instance,
    kind: str,
    new_status: str,
    user,
):
    """
    Backward-compatible wrapper.

    Ensures terminal lock, transition legality, role enforcement, alert resolution,
    and SLA evaluation stay identical to the API/UI workflow path.
    """
    try:
        result = _execute_transition(
            instance=instance,
            kind=kind,
            new_status=new_status,
            user=user,
        )
    except DRFValidationError as e:
        raise ValidationError(e.detail)
    except DRFPermissionDenied as e:
        raise PermissionDenied(str(e))

    # executor persists via queryset update inside transition_object, refresh instance
    instance.refresh_from_db(fields=["status"] + (["updated_at"] if hasattr(instance, "updated_at") else []))
    return instance
