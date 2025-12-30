# lims_core/tests/test_sla_compute.py
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from lims_core.workflows.sla import get_sla
from lims_core.views_workflow_runtime import (
    _compute_sla_payload,
    _td_seconds,
)


@pytest.mark.django_db
def test_get_sla_case_insensitive_and_unknown():
    assert get_sla("sample", "REGISTERED") is not None
    assert get_sla("SAMPLE", "registered") is not None
    assert get_sla("sample", "no_such_state") is None
    assert get_sla("no_such_kind", "REGISTERED") is None


def test_td_seconds_none_and_value():
    assert _td_seconds(None) is None
    assert _td_seconds(timedelta(seconds=61)) == 61


@pytest.mark.django_db
def test_compute_sla_payload_no_sla_applies(monkeypatch):
    """
    If SLA is not configured for this state, applies must be False.
    """
    now = timezone.now()
    payload = _compute_sla_payload(kind="sample", status="DOES_NOT_EXIST", entered_at=now)
    assert payload["applies"] is False
    assert payload["status"] == "none"
    assert payload["severity"] is None


@pytest.mark.django_db
def test_compute_sla_payload_ok_warning_breached_legacy_max_age(monkeypatch):
    """
    Your SLA config currently supports legacy 'max_age'. The view code derives:
      breach_after = max_age
      warn_after = 0.6 * breach_after (best-effort)
    This test checks the three main SLA states.
    """
    # Use an existing state that has SLA in your sla.py. REGISTERED is defined there.
    sla_def = get_sla("sample", "REGISTERED")
    assert sla_def is not None

    # Derive breach_after from max_age (legacy)
    breach_after = sla_def.get("breach_after") or sla_def.get("max_age")
    assert breach_after is not None

    # Derived warn is 60% of breach (as per your code)
    derived_warn_after = sla_def.get("warn_after")
    if derived_warn_after is None:
        derived_warn_after = breach_after * 0.6

    base_now = timezone.now()

    # OK: age = 0.1 * warn
    entered_ok = base_now - (derived_warn_after * 0.1)
    ok_payload = _compute_sla_payload(kind="sample", status="REGISTERED", entered_at=entered_ok)
    assert ok_payload["applies"] is True
    assert ok_payload["status"] == "ok"

    # WARNING: age = warn + small delta
    entered_warn = base_now - (derived_warn_after + timedelta(minutes=1))
    warn_payload = _compute_sla_payload(kind="sample", status="REGISTERED", entered_at=entered_warn)
    assert warn_payload["applies"] is True
    assert warn_payload["status"] == "warning"

    # BREACHED: age = breach + small delta
    entered_breached = base_now - (breach_after + timedelta(minutes=1))
    breached_payload = _compute_sla_payload(kind="sample", status="REGISTERED", entered_at=entered_breached)
    assert breached_payload["applies"] is True
    assert breached_payload["status"] == "breached"
    assert breached_payload["remaining_seconds"] is not None
    assert breached_payload["remaining_seconds"] < 0  # negative when breached


@pytest.mark.django_db
def test_compute_sla_payload_missing_entered_at(monkeypatch):
    payload = _compute_sla_payload(kind="sample", status="REGISTERED", entered_at=None)
    assert payload["applies"] is False
    assert payload["status"] == "none"
