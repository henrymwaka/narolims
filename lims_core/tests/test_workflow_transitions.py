import pytest


@pytest.mark.django_db
def test_role_enforced_transition(api_client, users, sample_with_roles):
    sample = sample_with_roles
    sample.status = "QC_PENDING"
    sample.save(update_fields=["status"])

    # LAB_TECH cannot pass QC
    api_client.login(username="labtech", password="pass123")
    resp = api_client.patch(
        f"/lims/workflows/sample/{sample.id}/",
        {"status": "QC_PASSED"},
        format="json",
        secure=True,
    )
    assert resp.status_code == 403
    api_client.logout()

    # QA can pass QC
    api_client.login(username="qa", password="pass123")
    resp = api_client.patch(
        f"/lims/workflows/sample/{sample.id}/",
        {"status": "QC_PASSED"},
        format="json",
        secure=True,
    )
    assert resp.status_code == 200
    api_client.logout()
