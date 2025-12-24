# lims_core/views_ui.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from .models import Sample, Experiment


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
def sample_detail(request, pk: int):
    sample = get_object_or_404(Sample, pk=pk)
    return render(
        request,
        "lims_core/samples/detail.html",
        {
            "sample": sample,
        },
    )


@login_required
def experiment_detail(request, pk: int):
    experiment = get_object_or_404(Experiment, pk=pk)
    return render(
        request,
        "lims_core/experiments/detail.html",
        {
            "experiment": experiment,
        },
    )
