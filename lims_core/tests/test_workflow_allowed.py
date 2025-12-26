# lims_core/tests/test_workflow_allowed.py
import pytest


@pytest.mark.django_db
def test_allowed_states_by_role(api_client, users, sample_with_roles):
    """
    Verify that allowed workflow transitions depend on both
    the current sample status and the user's role.

    Policy enforced:
    - From QC_PENDING:
        * LAB_TECH: no transitions
        * QA: QC_PASSED, QC_FAILED
        * ADMIN: QC_PASSED, QC_FAILED
    """
    sample = sample_with_roles

    # Ensure starting state (bypass guardrails explicitly)
    sample.status = "QC_PENDING"
    sample.save(update_fields=["status"], _workflow_bypass=True)

    # LAB_TECH should NOT see QC transitions
    assert api_client.login(username="labtech", password="pass123") is True
    resp = api_client.get(
        f"/lims/workflows/sample/{sample.id}/allowed/",
        secure=True,
    )
    assert resp.status_code == 200
    assert resp.json()["allowed"] == []
    api_client.logout()

    # QA should see QC transitions
    assert api_client.login(username="qa", password="pass123") is True
    resp = api_client.get(
        f"/lims/workflows/sample/{sample.id}/allowed/",
        secure=True,
    )
    assert resp.status_code == 200
    assert set(resp.json()["allowed"]) == {"QC_PASSED", "QC_FAILED"}
    api_client.logout()

    # ADMIN sees all valid transitions FROM QC_PENDING
    assert api_client.login(username="admin", password="pass123") is True
    resp = api_client.get(
        f"/lims/workflows/sample/{sample.id}/allowed/",
        secure=True,
    )
    assert resp.status_code == 200
    assert set(resp.json()["allowed"]) == {"QC_PASSED", "QC_FAILED"}
    api_client.logout()
