import pytest


@pytest.mark.django_db
def test_terminal_state_locked(api_client, users, sample_with_roles):
    sample = sample_with_roles
    sample.status = "ARCHIVED"
    sample.save(update_fields=["status"])

    api_client.login(username="admin", password="pass123")
    resp = api_client.patch(
        f"/lims/workflows/sample/{sample.id}/",
        {"status": "IN_PROCESS"},
        format="json",
        secure=True,
    )

    assert resp.status_code == 409
    api_client.logout()
