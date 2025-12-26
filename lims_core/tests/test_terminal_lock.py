# lims_core/tests/test_terminal_lock.py

import pytest

from lims_core.models import Sample


@pytest.mark.django_db
def test_terminal_state_locked(api_client, users, sample_with_roles):
    admin, _labtech = users
    sample = sample_with_roles

    # Put sample into terminal state without triggering save() guard
    Sample.objects.filter(pk=sample.pk).update(status="ARCHIVED")
    sample.refresh_from_db()

    api_client.force_authenticate(user=admin)

    # Transition endpoint in your code is POST .../transition/
    resp = api_client.post(
        f"/lims/workflows/sample/{sample.id}/transition/",
        {"to_status": "IN_PROCESS"},
        format="json",
    )

    assert resp.status_code == 400

    payload = resp.json()
    msg = ""
    if isinstance(payload, dict):
        msg = str(payload.get("status") or payload.get("detail") or payload)

    assert "terminal state" in msg.lower()
