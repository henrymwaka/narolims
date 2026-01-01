# lims_core/workflows/sla.py
from __future__ import annotations

from datetime import timedelta
from typing import Optional, Dict, Any

"""
Authoritative SLA definitions and helpers.

This module is PURE LOGIC + DATA.
- No Django imports
- Safe to import at startup
- Must align exactly with workflow rules
- UI and API should consume computed SLA status, not raw rules
"""

SLA_DEFINITIONS: Dict[str, Dict[str, Optional[Dict[str, Any]]]] = {
    "sample": {
        # Sample lifecycle
        "REGISTERED": {
            "warn_after": timedelta(hours=12),
            "breach_after": timedelta(hours=24),
            "severity": "warning",
        },
        "IN_PROCESS": {
            "warn_after": timedelta(days=2),
            "breach_after": timedelta(days=3),
            "severity": "critical",
        },

        # QC lifecycle (add these if you want them monitored)
        # Tune these to match your lab realities.
        "QC_PENDING": {
            "warn_after": timedelta(hours=12),
            "breach_after": timedelta(hours=24),
            "severity": "warning",
        },
        "QC_PASSED": {
            # Often used as "ready to close out / archive" stage
            "warn_after": timedelta(days=3),
            "breach_after": timedelta(days=7),
            "severity": "warning",
        },

        # Terminal or non-SLA stages
        "ARCHIVED": None,
        "REJECTED": None,

        # Kept for compatibility if referenced elsewhere, but not part of your current sample statuses
        "APPROVED": None,
    },
    "experiment": {
        "PLANNED": {
            "warn_after": timedelta(days=1),
            "breach_after": timedelta(days=2),
            "severity": "warning",
        },
        "RUNNING": {
            "warn_after": timedelta(days=5),
            "breach_after": timedelta(days=7),
            "severity": "critical",
        },
        "COMPLETED": None,
    },
}


def get_sla(kind: str, state: str) -> Optional[Dict[str, Any]]:
    """
    Return SLA definition for a workflow kind + state.

    Returns a dict that always includes legacy compatibility key:
      - max_age = breach_after (if breach_after exists)
    """
    if not kind or not state:
        return None

    kind = kind.strip().lower()
    state = state.strip().upper()

    base = SLA_DEFINITIONS.get(kind, {}).get(state)
    if not base:
        return None

    out = dict(base)

    # Backward compatible alias for older code paths
    if out.get("max_age") is None and out.get("breach_after") is not None:
        out["max_age"] = out["breach_after"]

    return out
