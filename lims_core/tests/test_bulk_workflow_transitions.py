import pytest

from lims_core.models import WorkflowEvent
from lims_core.services.workflow_bulk import bulk_transition


# ===============================================================
# BULK SAMPLE WORKFLOW TRANSITIONS
# ===============================================================

@pytest.mark.django_db
def test_bulk_sample_transition_success(
    user_technician,
    laboratory,
    project,
    sample_factory,
):
    samples = [
        sample_factory(
            laboratory=laboratory,
            project=project,
            status="REGISTERED",
        )
        for _ in range(3)
    ]

    result = bulk_transition(
        kind="sample",
        objects=samples,
        target_status="IN_PROCESS",
        actor=user_technician,
        actor_role="LAB_TECH",
        comment="Batch processing started",
    )

    assert result["failed"] == []
    assert set(result["success"]) == {s.id for s in samples}

    for s in samples:
        s.refresh_from_db()
        assert s.status == "IN_PROCESS"

    events = WorkflowEvent.objects.filter(kind="sample")
    assert events.count() == 3

    for ev in events:
        assert ev.from_status == "REGISTERED"
        assert ev.to_status == "IN_PROCESS"
        assert ev.role == "LAB_TECH"


@pytest.mark.django_db
def test_bulk_sample_partial_failure(
    user_technician,
    laboratory,
    project,
    sample_factory,
):
    good = sample_factory(
        laboratory=laboratory,
        project=project,
        status="REGISTERED",
    )
    bad = sample_factory(
        laboratory=laboratory,
        project=project,
        status="ARCHIVED",
    )

    result = bulk_transition(
        kind="sample",
        objects=[good, bad],
        target_status="IN_PROCESS",
        actor=user_technician,
        actor_role="LAB_TECH",
    )

    assert good.id in result["success"]
    assert len(result["failed"]) == 1
    assert result["failed"][0]["id"] == bad.id

    good.refresh_from_db()
    bad.refresh_from_db()

    assert good.status == "IN_PROCESS"
    assert bad.status == "ARCHIVED"

    assert WorkflowEvent.objects.filter(object_id=good.id).count() == 1
    assert WorkflowEvent.objects.filter(object_id=bad.id).count() == 0


@pytest.mark.django_db
def test_bulk_sample_role_violation(
    user_technician,
    laboratory,
    project,
    sample_factory,
):
    sample = sample_factory(
        laboratory=laboratory,
        project=project,
        status="QC_PENDING",
    )

    result = bulk_transition(
        kind="sample",
        objects=[sample],
        target_status="QC_PASSED",
        actor=user_technician,
        actor_role="LAB_TECH",
    )

    assert result["success"] == []
    assert len(result["failed"]) == 1
    assert "not permitted" in result["failed"][0]["error"]

    sample.refresh_from_db()
    assert sample.status == "QC_PENDING"
    assert WorkflowEvent.objects.count() == 0


# ===============================================================
# BULK EXPERIMENT WORKFLOW TRANSITIONS
# ===============================================================

@pytest.mark.django_db
def test_bulk_experiment_transition(
    user_technician,
    laboratory,
    project,
    experiment_factory,
):
    experiments = [
        experiment_factory(
            laboratory=laboratory,
            project=project,
            status="PLANNED",
        )
        for _ in range(2)
    ]

    result = bulk_transition(
        kind="experiment",
        objects=experiments,
        target_status="RUNNING",
        actor=user_technician,
        actor_role="LAB_TECH",
    )

    assert result["failed"] == []
    assert len(result["success"]) == 2

    for e in experiments:
        e.refresh_from_db()
        assert e.status == "RUNNING"

    assert WorkflowEvent.objects.filter(kind="experiment").count() == 2


# ===============================================================
# ERROR HANDLING AND AUDIT GUARANTEES
# ===============================================================

@pytest.mark.django_db
def test_bulk_unknown_kind_rejected(
    user_admin,
    laboratory,
    project,
    sample_factory,
):
    sample = sample_factory(
        laboratory=laboratory,
        project=project,
        status="REGISTERED",
    )

    result = bulk_transition(
        kind="invalid_kind",
        objects=[sample],
        target_status="IN_PROCESS",
        actor=user_admin,
        actor_role="ADMIN",
    )

    assert result["success"] == []
    assert len(result["failed"]) == 1
    assert "Unknown workflow kind" in result["failed"][0]["error"]


@pytest.mark.django_db
def test_workflow_event_records_exact_transition(
    user_admin,
    laboratory,
    project,
    sample_factory,
):
    sample = sample_factory(
        laboratory=laboratory,
        project=project,
        status="REGISTERED",
    )

    bulk_transition(
        kind="sample",
        objects=[sample],
        target_status="ARCHIVED",
        actor=user_admin,
        actor_role="ADMIN",
        comment="Force archive",
    )

    ev = WorkflowEvent.objects.get(object_id=sample.id)

    assert ev.from_status == "REGISTERED"
    assert ev.to_status == "ARCHIVED"
    assert ev.performed_by == user_admin
    assert ev.comment == "Force archive"
