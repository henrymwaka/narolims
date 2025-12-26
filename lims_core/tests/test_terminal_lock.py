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

    # Authenticate as admin
    assert api_client.login(username="admin", password="pass123") is True

    # Provide a payload that passes validation first, so we actually test terminal locking.
    # Some code paths still validate against `to_status`, while others accept `to`.
    payload = {"to_status": "IN_PROCESS", "to": "IN_PROCESS"}

    resp = api_client.post(
        f"/lims/workflows/sample/{sample.id}/transition/",
        payload,
        format="json",
        secure=True,
    )

    assert resp.status_code == 400

    data = resp.json()
    msg = ""

    if isinstance(data, dict):
        # Common patterns for DRF error payloads
        msg = str(
            data.get("detail")
            or data.get("status")
            or data.get("error")
            or data.get("non_field_errors")
            or data
        ).lower()
    else:
        msg = str(data).lower()

    # We want to confirm the failure is due to terminal state, not payload shape
    assert ("terminal" in msg) or ("archiv" in msg)
