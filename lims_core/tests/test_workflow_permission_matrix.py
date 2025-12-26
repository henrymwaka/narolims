# lims_core/tests/test_workflow_permission_matrix.py

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from lims_core.models import UserRole


@pytest.mark.django_db
def test_permission_matrix_sample_lab_tech(
    user_technician,
    laboratory,
    project,
    sample_factory,
):
    """
    LAB_TECH should be able to move REGISTERED -> IN_PROCESS
    """
    # Explicit lab membership
    UserRole.objects.create(
        user=user_technician,
        laboratory=laboratory,
        role="LAB_TECH",
    )

    sample = sample_factory(
        laboratory=laboratory,
        project=project,
        status="REGISTERED",
    )

    client = APIClient()
    client.force_authenticate(user=user_technician)

    url = reverse(
        "lims_core:workflow-permission-matrix",
        kwargs={"kind": "sample"},
    )

    resp = client.get(
        url,
        {"object_ids": str(sample.id)},
        HTTP_X_LABORATORY=str(laboratory.id),
    )

    assert resp.status_code == 200

    data = resp.json()
    assert data["kind"] == "sample"
    assert "LAB_TECH" in data["roles"]

    obj = data["objects"][0]
    assert obj["id"] == sample.id
    assert obj["current_status"] == "REGISTERED"
    assert "IN_PROCESS" in obj["allowed_transitions"]
    assert obj["terminal"] is False


@pytest.mark.django_db
def test_permission_matrix_terminal_state(
    user_admin,
    laboratory,
    project,
    sample_factory,
):
    """
    Terminal states must report no transitions.
    """
    UserRole.objects.create(
        user=user_admin,
        laboratory=laboratory,
        role="ADMIN",
    )

    sample = sample_factory(
        laboratory=laboratory,
        project=project,
        status="ARCHIVED",
    )

    client = APIClient()
    client.force_authenticate(user=user_admin)

    url = reverse(
        "lims_core:workflow-permission-matrix",
        kwargs={"kind": "sample"},
    )

    resp = client.get(
        url,
        {"object_ids": str(sample.id)},
        HTTP_X_LABORATORY=str(laboratory.id),
    )

    assert resp.status_code == 200

    obj = resp.json()["objects"][0]
    assert obj["terminal"] is True
    assert obj["allowed_transitions"] == []
    assert obj["blocked_reason"] == "Terminal state"


@pytest.mark.django_db
def test_permission_matrix_role_blocked(
    user_technician,
    laboratory,
    project,
    sample_factory,
):
    """
    LAB_TECH should NOT be allowed to ARCHIVE from REGISTERED.
    """
    UserRole.objects.create(
        user=user_technician,
        laboratory=laboratory,
        role="LAB_TECH",
    )

    sample = sample_factory(
        laboratory=laboratory,
        project=project,
        status="REGISTERED",
    )

    client = APIClient()
    client.force_authenticate(user=user_technician)

    url = reverse(
        "lims_core:workflow-permission-matrix",
        kwargs={"kind": "sample"},
    )

    resp = client.get(
        url,
        {"object_ids": str(sample.id)},
        HTTP_X_LABORATORY=str(laboratory.id),
    )

    assert resp.status_code == 200

    obj = resp.json()["objects"][0]
    assert "ARCHIVED" not in obj["allowed_transitions"]


@pytest.mark.django_db
def test_permission_matrix_experiment_lab_tech(
    user_technician,
    laboratory,
    project,
    experiment_factory,
):
    """
    LAB_TECH should be able to move PLANNED -> RUNNING.
    """
    UserRole.objects.create(
        user=user_technician,
        laboratory=laboratory,
        role="LAB_TECH",
    )

    exp = experiment_factory(
        laboratory=laboratory,
        project=project,
        status="PLANNED",
    )

    client = APIClient()
    client.force_authenticate(user=user_technician)

    url = reverse(
        "lims_core:workflow-permission-matrix",
        kwargs={"kind": "experiment"},
    )

    resp = client.get(
        url,
        {"object_ids": str(exp.id)},
        HTTP_X_LABORATORY=str(laboratory.id),
    )

    assert resp.status_code == 200

    obj = resp.json()["objects"][0]
    assert obj["current_status"] == "PLANNED"
    assert "RUNNING" in obj["allowed_transitions"]


@pytest.mark.django_db
def test_permission_matrix_unknown_kind_rejected(
    user_admin,
    laboratory,
):
    UserRole.objects.create(
        user=user_admin,
        laboratory=laboratory,
        role="ADMIN",
    )

    client = APIClient()
    client.force_authenticate(user=user_admin)

    url = reverse(
        "lims_core:workflow-permission-matrix",
        kwargs={"kind": "invalid"},
    )

    resp = client.get(
        url,
        {"object_ids": "1"},
        HTTP_X_LABORATORY=str(laboratory.id),
    )

    assert resp.status_code == 400
    assert "Unsupported workflow kind" in resp.json()["detail"]
