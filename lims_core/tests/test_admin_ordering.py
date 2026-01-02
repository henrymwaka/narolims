# lims_core/tests/test_admin_ordering.py

import pytest
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone

from lims_core.models import Institute, Laboratory, Project

# Import the ModelAdmin classes from the module where they are defined
from lims_core import admin as lims_admin


@pytest.mark.django_db
def test_laboratory_admin_search_results_are_deterministically_ordered():
    """
    Guardrail: Django admin autocomplete paginates, and unordered querysets can raise
    UnorderedObjectListWarning and yield inconsistent pages.
    We enforce deterministic ordering for Laboratory search results.
    """
    site = AdminSite()
    rf = RequestFactory()
    request = rf.get("/admin/autocomplete/")

    User = get_user_model()
    request.user = User.objects.create_superuser(
        username="admin_ordering",
        email="admin_ordering@example.com",
        password="pass",
    )

    inst = Institute.objects.create(code="INST", name="Institute")
    # Intentionally create out of order
    Laboratory.objects.create(code="LAB2", name="Zulu Lab", institute=inst, is_active=True)
    Laboratory.objects.create(code="LAB1", name="Alpha Lab", institute=inst, is_active=True)
    Laboratory.objects.create(code="LAB3", name="Alpha Lab", institute=inst, is_active=True)  # tie-break by id

    ma = lims_admin.LaboratoryAdmin(Laboratory, site)
    qs, _use_distinct = ma.get_search_results(request, Laboratory.objects.all(), search_term="")

    # 1) Must be ordered to avoid pagination warnings
    assert qs.ordered is True

    # 2) Verify deterministic ordering: name then id
    rows = list(qs.values_list("name", "id"))
    assert rows == sorted(rows, key=lambda x: (x[0], x[1]))


@pytest.mark.django_db
def test_project_admin_search_results_are_deterministically_ordered():
    """
    Guardrail: Project autocomplete must be ordered.
    ProjectAdmin forces ordering: -created_at, code, id.
    """
    site = AdminSite()
    rf = RequestFactory()
    request = rf.get("/admin/autocomplete/")

    User = get_user_model()
    u = User.objects.create_superuser(
        username="admin_ordering2",
        email="admin_ordering2@example.com",
        password="pass",
    )
    request.user = u

    inst = Institute.objects.create(code="INST2", name="Institute 2")
    lab = Laboratory.objects.create(code="LABX", name="Lab X", institute=inst, is_active=True)

    p_old = Project.objects.create(laboratory=lab, name="Old Project", created_by=u)
    p_new = Project.objects.create(laboratory=lab, name="New Project", created_by=u)

    # Force created_at timestamps to make ordering test deterministic
    now = timezone.now()
    Project.objects.filter(pk=p_old.pk).update(created_at=now - timedelta(days=2), code="OLD")
    Project.objects.filter(pk=p_new.pk).update(created_at=now - timedelta(hours=1), code="NEW")

    ma = lims_admin.ProjectAdmin(Project, site)
    qs, _use_distinct = ma.get_search_results(request, Project.objects.all(), search_term="")

    assert qs.ordered is True

    ids = list(qs.values_list("id", flat=True))
    assert ids[0] == p_new.id
    assert ids[1] == p_old.id
