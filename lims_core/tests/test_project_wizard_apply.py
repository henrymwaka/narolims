import pytest
from django.contrib.auth import get_user_model

from lims_core.models.core import Institute, Laboratory
from lims_core.models.drafts import ProjectDraft
from lims_core.wizard.services import apply_project_draft


@pytest.mark.django_db
def test_apply_project_draft_creates_project_and_samples():
    User = get_user_model()
    u = User.objects.create_superuser("wiz_admin", "wiz_admin@example.com", "pass")

    inst = Institute.objects.create(code="I1", name="Inst")
    lab = Laboratory.objects.create(code="LAB", name="Lab", institute=inst, is_active=True)

    draft = ProjectDraft.objects.create(
        created_by=u,
        laboratory=lab,
        payload={
            "laboratory_id": lab.id,
            "template": {"workflow_code": "DEFAULT", "workflow_name": "Default workflow", "workflow_version": "v1"},
            "project": {"name": "Wizard Project", "description": "desc"},
            "samples": {"create_placeholders": True, "count": 3, "sample_type": "test"},
        },
    )

    project = apply_project_draft(draft=draft, user=u)
    assert project.name == "Wizard Project"
    assert project.laboratory_id == lab.id
    assert project.samples.count() == 3
