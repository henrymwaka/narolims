# lims_core/tests/test_workflow_runtime_sla.py
from __future__ import annotations

from datetime import timedelta

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from rest_framework.test import APIClient

from lims_core.models import (
    Laboratory,
    Project,
    Sample,
    WorkflowEvent,
)
from lims_core.views_workflow_runtime import _get_state_entered_at


# ---------------------------------------------------------------------
# Test primitives: institute, lab, membership, scoped API client
# ---------------------------------------------------------------------

def ensure_test_institute():
    """
    Laboratory.institute is NOT NULL in this schema, so we must create one.
    """
    Institute = apps.get_model("lims_core", "Institute")
    inst, _ = Institute.objects.get_or_create(
        code="TESTINST",
        defaults={"name": "Test Institute"},
    )
    return inst


def ensure_test_lab() -> Laboratory:
    """
    Create a valid lab with a valid institute.
    """
    institute = ensure_test_institute()

    lab, _ = Laboratory.objects.get_or_create(
        code="TESTLAB",
        defaults={
            "name": "Test Lab",
            "institute": institute,
            "location": "",
            "is_active": True,
        },
    )

    # If the row exists from legacy data without institute, repair it.
    if getattr(lab, "institute_id", None) is None:
        lab.institute = institute
        lab.save(update_fields=["institute"])

    return lab


def create_api_user(*, username: str):
    """
    These tests validate SLA payload exposure, not permission policy.
    Use an admin-capable account to avoid false negatives from permission gates.
    """
    User = get_user_model()
    user = User.objects.create_user(username=username, password="x")

    # Many permission layers short-circuit for staff/superuser.
    # If your custom permission ignores these flags, lab membership + lab context below still applies.
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    return user


def bind_user_to_lab_if_supported(user, lab: Laboratory) -> None:
    """
    Best-effort: if the codebase has a membership/assignment model linking user <-> laboratory,
    create it so object-level permissions pass.

    This is intentionally generic to survive refactors (model renames).
    """
    UserModel = get_user_model()

    def is_fk_to(field, target_model):
        return (
            isinstance(field, models.ForeignKey)
            and field.remote_field
            and field.remote_field.model == target_model
        )

    for M in apps.get_models():
        if M._meta.app_label != "lims_core":
            continue

        user_fk = None
        lab_fk = None

        for f in M._meta.fields:
            if is_fk_to(f, UserModel):
                user_fk = f
            if is_fk_to(f, Laboratory):
                lab_fk = f

        if not (user_fk and lab_fk):
            continue

        kwargs = {user_fk.name: user, lab_fk.name: lab}

        # Fill required non-null fields without defaults
        for f in M._meta.fields:
            if f.name in kwargs:
                continue
            if isinstance(f, models.AutoField):
                continue
            if getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False):
                continue
            if f.null:
                continue
            if f.has_default():
                continue
            if isinstance(f, models.BooleanField):
                kwargs[f.name] = True
                continue
            if isinstance(f, (models.CharField, models.TextField)):
                if f.choices:
                    kwargs[f.name] = f.choices[0][0]
                else:
                    kwargs[f.name] = "TEST"
                continue
            if isinstance(f, models.IntegerField):
                kwargs[f.name] = 1
                continue
            if isinstance(f, models.DateTimeField):
                kwargs[f.name] = timezone.now()
                continue

            # If we hit a required FK, try common options
            if isinstance(f, models.ForeignKey):
                target = f.remote_field.model
                if target.__name__ == "Institute":
                    kwargs[f.name] = ensure_test_institute()
                    continue

        # Create (or reuse) membership row
        M.objects.get_or_create(**kwargs)
        return  # bind one suitable model only


def make_scoped_client(*, user, lab: Laboratory) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)

    # Session-based "active lab" keys (common patterns)
    session = client.session
    for k in ("active_lab_id", "active_laboratory_id", "laboratory_id", "lab_id"):
        session[k] = lab.pk
    for k in ("active_lab_code", "laboratory_code", "lab_code"):
        session[k] = lab.code
    session.save()

    return client


def get_timeline(client: APIClient, *, sample: Sample, lab: Laboratory):
    """
    Supply lab headers as well, since many stacks resolve lab context from headers.
    """
    return client.get(
        f"/lims/workflows/sample/{sample.pk}/timeline/",
        HTTP_X_LAB_CODE=lab.code,
        HTTP_X_LAB_ID=str(lab.pk),
    )


# ---------------------------------------------------------------------
# Factories (schema-aware)
# ---------------------------------------------------------------------

def create_project() -> Project:
    lab = ensure_test_lab()
    return Project.objects.create(
        laboratory=lab,
        code="TEST-PROJ",
        name="Test Project",
        is_active=True,
    )


def create_sample(*, status: str = "REGISTERED") -> Sample:
    return Sample.objects.create(
        project=create_project(),
        status=status,
    )


def create_workflow_event(
    *,
    kind: str,
    object_id: int,
    from_status: str,
    to_status: str,
    performed_by,
    created_at,
    role: str = "SYSTEM",
    comment: str = "",
) -> WorkflowEvent:
    """
    WorkflowEvent.created_at uses auto_now_add=True, so passed values are ignored.
    Create first, then UPDATE created_at explicitly.
    """
    e = WorkflowEvent.objects.create(
        kind=kind,
        object_id=object_id,
        from_status=from_status,
        to_status=to_status,
        performed_by=performed_by,
        role=role,
        comment=comment,
    )

    WorkflowEvent.objects.filter(pk=e.pk).update(created_at=created_at)
    e.refresh_from_db()
    return e


# ---------------------------------------------------------------------
# Tests: state entry resolution (pure function tests)
# ---------------------------------------------------------------------

@pytest.mark.django_db
def test_get_state_entered_at_prefers_latest_matching_transition():
    User = get_user_model()
    user = User.objects.create_user(username="u1", password="x")

    sample = create_sample(status="REGISTERED")

    t1 = timezone.now() - timedelta(days=2)
    t2 = timezone.now() - timedelta(hours=3)

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="INITIAL",
        to_status="REGISTERED",
        performed_by=user,
        created_at=t1,
    )

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="IN_PROCESS",
        to_status="REGISTERED",
        performed_by=user,
        created_at=t2,
    )

    entered_at = _get_state_entered_at(
        kind="sample",
        object_id=sample.pk,
        current_status="REGISTERED",
        obj=sample,
    )

    assert entered_at == t2


@pytest.mark.django_db
def test_get_state_entered_at_falls_back_to_latest_event():
    User = get_user_model()
    user = User.objects.create_user(username="u2", password="x")

    sample = create_sample(status="REGISTERED")

    t1 = timezone.now() - timedelta(days=1)

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="INITIAL",
        to_status="IN_PROCESS",
        performed_by=user,
        created_at=t1,
    )

    entered_at = _get_state_entered_at(
        kind="sample",
        object_id=sample.pk,
        current_status="REGISTERED",
        obj=sample,
    )

    assert entered_at == t1


# ---------------------------------------------------------------------
# Tests: SLA payload exposure via API (requires auth + lab scope)
# ---------------------------------------------------------------------

@pytest.mark.django_db
def test_timeline_sla_payload_has_stable_minimum_fields():
    lab = ensure_test_lab()
    user = create_api_user(username="u3")
    bind_user_to_lab_if_supported(user, lab)

    sample = create_sample(status="REGISTERED")

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="INITIAL",
        to_status="REGISTERED",
        performed_by=user,
        created_at=timezone.now() - timedelta(hours=6),
    )

    client = make_scoped_client(user=user, lab=lab)

    resp = get_timeline(client, sample=sample, lab=lab)
    assert resp.status_code == 200

    sla = resp.json()["sla"]

    for key in (
        "applies",
        "status",
        "severity",
        "entered_at",
        "age_seconds",
        "warn_after_seconds",
        "breach_after_seconds",
        "remaining_seconds",
    ):
        assert key in sla


@pytest.mark.django_db
def test_latest_matching_transition_is_used_for_state_time_if_exposed():
    lab = ensure_test_lab()
    user = create_api_user(username="u4")
    bind_user_to_lab_if_supported(user, lab)

    sample = create_sample(status="REGISTERED")

    t1 = timezone.now() - timedelta(days=2)
    t2 = timezone.now() - timedelta(hours=1)

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="INITIAL",
        to_status="REGISTERED",
        performed_by=user,
        created_at=t1,
    )

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="IN_PROCESS",
        to_status="REGISTERED",
        performed_by=user,
        created_at=t2,
    )

    client = make_scoped_client(user=user, lab=lab)

    resp = get_timeline(client, sample=sample, lab=lab)
    assert resp.status_code == 200

    # API returns ISO string
    assert resp.json()["entered_at"].startswith(t2.isoformat()[:19])
