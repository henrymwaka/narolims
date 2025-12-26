import pytest


def _try_transition(client, sample_id: int, lab_id: int, target_state: str):
    """
    Different workflow implementations name the target field differently.
    Try the common ones and return the first non-400 response.
    If all fail, raise with the last error body to show what the API expects.
    """
    url = f"/lims/workflows/sample/{sample_id}/transition/"
    header = {"HTTP_X_LABORATORY": str(lab_id)}

    attempts = [
        {"to": target_state},
        {"to_state": target_state},
        {"to_status": target_state},
        {"status": target_state},
    ]

    last = None
    for payload in attempts:
        resp = client.post(url, payload, format="json", secure=True, **header)
        if resp.status_code != 400:
            return resp
        last = resp

    try:
        detail = last.json() if last is not None else None
    except Exception:
        detail = getattr(last, "content", b"").decode("utf-8", errors="replace") if last is not None else None

    raise AssertionError(f"Transition API returned 400 for all payload variants. Last error: {detail}")


@pytest.mark.django_db
def test_role_enforced_transition(api_client, users, sample_with_roles):
    sample = sample_with_roles

    # Put the sample into QC_PENDING using bypass (direct status edits are guarded)
    sample.status = "QC_PENDING"
    sample.save(update_fields=["status"], _workflow_bypass=True)

    lab_id = sample.laboratory_id

    # LAB_TECH should be blocked from QC decisions
    assert api_client.login(username="labtech", password="pass123") is True
    resp = _try_transition(api_client, sample.id, lab_id, "QC_PASSED")
    assert resp.status_code in (403, 401)
    api_client.logout()

    # ADMIN should be allowed
    assert api_client.login(username="admin", password="pass123") is True
    resp = _try_transition(api_client, sample.id, lab_id, "QC_PASSED")
    assert resp.status_code == 200

    sample.refresh_from_db()
    assert sample.status == "QC_PASSED"
