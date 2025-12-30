# lims_core/workflows/runtime.py

"""
Workflow runtime enforcement layer.

Responsibilities:
- Gate workflow transitions
- Enforce metadata completeness and validity
- Raise structured exceptions on hard blocks

This module MUST remain free of UI, serializers, or persistence logic.
"""

from typing import Dict, List


class WorkflowBlocked(Exception):
    """
    Raised when a workflow transition is blocked due to unmet requirements.
    """

    def __init__(
        self,
        *,
        missing_fields: List[str] | None = None,
        invalid_fields: List[str] | None = None,
    ):
        self.missing_fields = missing_fields or []
        self.invalid_fields = invalid_fields or []
        super().__init__("Workflow transition blocked due to metadata violations")


def enforce_metadata_gate(
    *,
    laboratory,
    object_type: str,
    object_id: int,
) -> None:
    """
    Enforce metadata requirements before a workflow transition.

    Raises WorkflowBlocked if requirements are not met.
    """

    from lims_core.workflows.metadata_gating import check_metadata_gate

    gate = check_metadata_gate(
        laboratory=laboratory,
        object_type=object_type,
        object_id=object_id,
    )

    if gate["allowed"]:
        return

    raise WorkflowBlocked(
        missing_fields=gate.get("missing_fields", []),
        invalid_fields=gate.get("invalid_fields", []),
    )
