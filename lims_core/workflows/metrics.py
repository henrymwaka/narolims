from datetime import timedelta
from typing import Dict, List

from django.utils.timezone import now

from lims_core.models import WorkflowTransition


def compute_time_in_states(
    *,
    kind: str,
    object_id: int,
) -> Dict[str, timedelta]:
    """
    Returns time spent in each workflow state.

    Example output:
    {
        "RECEIVED": timedelta(hours=2),
        "QC_PENDING": timedelta(days=1),
        "QC_PASSED": timedelta(hours=3),
    }
    """

    transitions = list(
        WorkflowTransition.objects
        .filter(kind=kind, object_id=object_id)
        .order_by("created_at", "id")
    )

    durations: Dict[str, timedelta] = {}

    if not transitions:
        return durations

    for i, current in enumerate(transitions):
        start = current.created_at

        if i + 1 < len(transitions):
            end = transitions[i + 1].created_at
        else:
            end = now()

        delta = end - start
        durations[current.to_status] = (
            durations.get(current.to_status, timedelta()) + delta
        )

    return durations


def compute_total_cycle_time(
    *,
    kind: str,
    object_id: int,
) -> timedelta:
    """
    Total time from first transition to last (or now).
    """

    qs = WorkflowTransition.objects.filter(
        kind=kind,
        object_id=object_id,
    ).order_by("created_at")

    first = qs.first()
    last = qs.last()

    if not first:
        return timedelta()

    end = last.created_at if last else now()
    return end - first.created_at
