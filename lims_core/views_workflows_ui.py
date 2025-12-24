# lims_core/views_workflows_ui.py
from __future__ import annotations

from django.shortcuts import render
from django.http import Http404

from .workflows import workflow_definition


def workflow_definition_ui(request, kind: str):
    """
    Lightweight HTML renderer for workflow definitions.
    Intended for demos, documentation, and stakeholder visibility.
    """

    try:
        definition = workflow_definition(kind)
    except Exception:
        raise Http404("Unknown workflow type")

    context = {
        "kind": definition["kind"],
        "statuses": definition["statuses"],
        "transitions": definition["transitions"],
        "terminal_states": set(definition["terminal_states"]),
    }

    return render(request, "lims/workflow_definition.html", context)
