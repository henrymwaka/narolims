# lims_core/tests/test_workflow_permission_aggregate.py
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from lims_core.models import UserRole


@pytest.mark.django_db
def test_aggregate_allowed_on_all_samples(
    user_technician,
    laboratory,
    project,
    sample_factory,
):
    """
    If all samples can move REGISTERED -> IN_PROCESS,
    it must appear in allowed_on_all.
    """
    # Explicit membership (idempotent)
    UserRole.objects.get_or_create(
        user=user_technician,
        laboratory=laboratory,
        role="LAB_TECH",
    )

    samples = [
        sample_factory(
            laboratory=laboratory,
            project=project,
            status="REGISTERED",
        )
        for _ in range(3)
    ]

    client = APIClient()
    client.force_authenticate(user=user_technician)

    url = reverse(
        "lims_core:workflow-permission-aggregate",
        kwargs={"kind": "sample"},
    )

    resp = client.get(
        url,
        {"object_ids": ",".join(str(s.id) for s in samples)},
        HTTP_X_LABORATORY=str(laboratory.id),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "allowed_on_all" in body
    assert "REGISTERED->IN_PROCESS" in set(body["allowed_on_all"])


@pytest.mark.django_db
def test_aggregate_denies_if_missing_lab_header(
    user_technician,
    laboratory,
    project,
    sample_factory,
):
    UserRole.objects.get_or_create(
        user=user_technician,
        laboratory=laboratory,
        role="LAB_TECH",
    )

    s = sample_factory(laboratory=laboratory, project=project, status="REGISTERED")

    client = APIClient()
    client.force_authenticate(user=user_technician)

    url = reverse("lims_core:workflow-permission-aggregate", kwargs={"kind": "sample"})

    resp = client.get(url, {"object_ids": str(s.id)})
    assert resp.status_code in (400, 403)


@pytest.mark.django_db
def test_aggregate_forbidden_if_user_not_member(
    user_technician,
    laboratory,
    project,
    sample_factory,
):
    # Intentionally NO UserRole row created here
    s = sample_factory(laboratory=laboratory, project=project, status="REGISTERED")

    client = APIClient()
    client.force_authenticate(user=user_technician)

    url = reverse("lims_core:workflow-permission-aggregate", kwargs={"kind": "sample"})

    resp = client.get(
        url,
        {"object_ids": str(s.id)},
        HTTP_X_LABORATORY=str(laboratory.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_aggregate_handles_unknown_kind(
    user_technician,
    laboratory,
):
    UserRole.objects.get_or_create(
        user=user_technician,
        laboratory=laboratory,
        role="LAB_TECH",
    )

    client = APIClient()
    client.force_authenticate(user=user_technician)

    url = reverse("lims_core:workflow-permission-aggregate", kwargs={"kind": "nope"})

    resp = client.get(
        url,
        {"object_ids": "1,2,3"},
        HTTP_X_LABORATORY=str(laboratory.id),
    )
    assert resp.status_code in (400, 404)


@pytest.mark.django_db
def test_aggregate_empty_object_ids(
    user_technician,
    laboratory,
):
    UserRole.objects.get_or_create(
        user=user_technician,
        laboratory=laboratory,
        role="LAB_TECH",
    )

    client = APIClient()
    client.force_authenticate(user=user_technician)

    url = reverse("lims_core:workflow-permission-aggregate", kwargs={"kind": "sample"})

    resp = client.get(
        url,
        {"object_ids": ""},
        HTTP_X_LABORATORY=str(laboratory.id),
    )
    assert resp.status_code in (400, 200)
