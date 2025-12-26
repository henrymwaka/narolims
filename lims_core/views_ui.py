# lims_core/views_ui.py

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, get_object_or_404

from .models import Sample, Experiment, UserRole
from .workflows import workflow_definition


@login_required
def workflow_widget_demo(request):
    """
    Browser-facing demo page for the workflow widget.
    Uses Django session authentication.
    """
    return render(
        request,
        "lims_core/workflow_widget.html",
        {
            "workflow_kind": "sample",
            "workflow_object_id": 1,
        },
    )


@login_required
def sample_list(request):
    """
    Simple Samples list UI for supervisors and bench users:
    - shows samples in the user's lab
    - allows bulk workflow transitions via /lims/workflows/sample/bulk/
    """
    # Determine a default lab_id for this user
    lab_ids = list(
        UserRole.objects.filter(user=request.user)
        .values_list("laboratory_id", flat=True)
        .distinct()
    )
    lab_id = None
    if lab_ids:
        lab_id = int(request.GET.get("lab") or lab_ids[0])

    qs = Sample.objects.select_related("project").all()

    # Scope to lab when possible (covers both Sample.laboratory and Project.laboratory patterns)
    if lab_id:
        qs = qs.filter(
            Q(laboratory_id=lab_id) | Q(project__laboratory_id=lab_id)
        )

    # Lightweight ordering
    qs = qs.order_by("-id")[:500]

    wf = workflow_definition("sample")
    statuses = [s["code"] for s in wf.get("statuses", []) if "code" in s]

    context = {
        "samples": qs,
        "lab_id": lab_id or "",
        "available_labs": lab_ids,
        "workflow_statuses": statuses,
    }
    return render(request, "lims_core/samples/list.html", context)


@login_required
def sample_detail(request, pk: int):
    sample = get_object_or_404(Sample, pk=pk)
    return render(
        request,
        "lims_core/samples/detail.html",
        {"sample": sample},
    )


@login_required
def experiment_detail(request, pk: int):
    experiment = get_object_or_404(Experiment, pk=pk)
    return render(
        request,
        "lims_core/experiments/detail.html",
        {"experiment": experiment},
    )
