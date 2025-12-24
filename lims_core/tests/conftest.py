import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from lims_core.models import (
    Institute,
    Laboratory,
    Project,
    Sample,
    UserRole,
)

User = get_user_model()


# ---------------------------------------------------------------------
# API CLIENT
# ---------------------------------------------------------------------

@pytest.fixture
def api_client(settings):
    """
    DRF client configured to behave like production behind Cloudflare/Nginx.
    """
    client = APIClient()
    client.defaults["HTTP_X_FORWARDED_PROTO"] = "https"
    client.defaults["HTTP_X_FORWARDED_HOST"] = "narolims.reslab.dev"
    return client


# ---------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------

@pytest.fixture
def users(db):
    """
    Core test users representing system roles.
    """
    admin = User.objects.create_user(
        username="admin",
        password="pass123",
        is_staff=True,
        is_superuser=True,
    )

    labtech = User.objects.create_user(
        username="labtech",
        password="pass123",
    )

    qa = User.objects.create_user(
        username="qa",
        password="pass123",
    )

    return {
        "admin": admin,
        "labtech": labtech,
        "qa": qa,
    }


# ---------------------------------------------------------------------
# INSTITUTE / LABORATORY
# ---------------------------------------------------------------------

@pytest.fixture
def institute(db):
    return Institute.objects.create(
        code="TEST-INST",
        name="Test Institute",
        is_active=True,
    )


@pytest.fixture
def laboratory(db, institute):
    return Laboratory.objects.create(
        institute=institute,
        code="TESTLAB",
        name="Test Laboratory",
        is_active=True,
    )


# ---------------------------------------------------------------------
# PROJECT
# ---------------------------------------------------------------------

@pytest.fixture
def project(db, laboratory, users):
    """
    Project model has NO `code` field.
    `created_by` is required and NOT NULL.
    """
    return Project.objects.create(
        laboratory=laboratory,
        name="Test Project",
        description="Project used for workflow tests",
        is_active=True,
        created_by=users["admin"],
    )


# ---------------------------------------------------------------------
# SAMPLE + ROLE BINDINGS
# ---------------------------------------------------------------------

@pytest.fixture
def sample_with_roles(db, users, laboratory, project):
    """
    Creates:
    - One Sample in QC_PENDING
    - Role bindings for ADMIN, LAB_TECH, QA
    """

    sample = Sample.objects.create(
        laboratory=laboratory,
        project=project,
        status="QC_PENDING",
        sample_id="SAMPLE-001",
        sample_type="TEST",
    )

    UserRole.objects.create(
        user=users["admin"],
        laboratory=laboratory,
        role="ADMIN",
    )

    UserRole.objects.create(
        user=users["labtech"],
        laboratory=laboratory,
        role="LAB_TECH",
    )

    UserRole.objects.create(
        user=users["qa"],
        laboratory=laboratory,
        role="QA",
    )

    return sample
