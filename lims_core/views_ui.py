# lims_core/views_ui.py

from __future__ import annotations

import traceback

from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect

from .models import Sample, Experiment, UserRole
from .workflows import workflow_definition


def landing(request):
    """
    Public landing page for the platform namespace (/lims/).

    Rules:
      - Do not touch the database (must be safe even during partial migrations).
      - If authenticated, send to the workspace dashboard (/lims/ui/).
    """
    if getattr(request, "user", None) and request.user.is_authenticated:
        return redirect("/lims/ui/")

    return render(request, "lims_core/landing.html")


def ui_logout(request):
    """
    UI logout endpoint (GET-safe).
    Avoids DRF logout 405 by using Django's auth_logout directly.

    Redirect order:
      1) ?next=/some/path
      2) /lims/  (public landing)
    """
    next_url = request.GET.get("next") or "/lims/"
    auth_logout(request)
    return redirect(next_url)


@login_required
def home(request):
    """
    Authenticated workspace home (/lims/ui/).
    Intentionally light on DB access. Dynamic stats are loaded via /lims/ui/stats/.
    """
    return render(
        request,
        "lims_core/home.html",
        {
            "username": getattr(request.user, "username", ""),
        },
    )


@login_required
def ui_stats(request):
    """
    JSON stats used by the workspace homepage. Must never 500.
    Returns best-effort lab-scoped counts and recent items.
    """
    payload = {
        "ok": True,
        "lab_id": "",
        "available_labs": [],
        "stats": {"samples_total": None, "experiments_total": None},
        "recent_samples": [],
        "recent_events": [],
        "open_alerts": [],
    }

    try:
        lab_ids = list(
            UserRole.objects.filter(user=request.user)
            .values_list("laboratory_id", flat=True)
            .distinct()
        )
        payload["available_labs"] = lab_ids

        lab_id = None
        if lab_ids:
            raw = request.GET.get("lab") or lab_ids[0]
            try:
                lab_id = int(raw)
            except (TypeError, ValueError):
                lab_id = int(lab_ids[0])

        payload["lab_id"] = lab_id or ""

        # Samples
        try:
            samples_qs = Sample.objects.select_related("project").all()
            if lab_id:
                samples_qs = samples_qs.filter(
                    Q(laboratory_id=lab_id) | Q(project__laboratory_id=lab_id)
                )
            payload["stats"]["samples_total"] = samples_qs.count()
            payload["recent_samples"] = [
                {
                    "id": s.id,
                    "code": getattr(s, "code", "") or str(s.id),
                    "status": getattr(s, "status", ""),
                }
                for s in samples_qs.order_by("-id")[:8]
            ]
        except (ProgrammingError, OperationalError):
            pass

        # Experiments
        try:
            exp_qs = Experiment.objects.all()
            if lab_id and hasattr(Experiment, "laboratory_id"):
                exp_qs = exp_qs.filter(laboratory_id=lab_id)
            payload["stats"]["experiments_total"] = exp_qs.count()
        except (ProgrammingError, OperationalError):
            pass

        # Optional models, never fail
        try:
            from .models import WorkflowEvent  # type: ignore

            qs = WorkflowEvent.objects.order_by("-id")[:10]
            payload["recent_events"] = [
                {
                    "label": str(e),
                    "created_at": str(
                        getattr(e, "created_at", "")
                        or getattr(e, "created", "")
                        or ""
                    ),
                }
                for e in qs
            ]
        except Exception:
            payload["recent_events"] = []

        try:
            from .models import WorkflowAlert  # type: ignore

            qs = WorkflowAlert.objects.all()
            if hasattr(WorkflowAlert, "resolved"):
                qs = qs.filter(resolved=False)
            elif hasattr(WorkflowAlert, "is_resolved"):
                qs = qs.filter(is_resolved=False)

            payload["open_alerts"] = [
                {
                    "label": str(a),
                    "created_at": str(
                        getattr(a, "created_at", "")
                        or getattr(a, "created", "")
                        or ""
                    ),
                }
                for a in qs.order_by("-id")[:6]
            ]
        except Exception:
            payload["open_alerts"] = []

        return JsonResponse(payload)

    except Exception:
        print("ui_stats() ERROR")
        print(traceback.format_exc())
        payload["ok"] = False
        payload["error"] = "stats_unavailable"
        return JsonResponse(payload, status=200)


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


def _extract_workflow_statuses(wf: dict) -> list[str]:
    raw = wf.get("statuses") or wf.get("states") or []
    out: list[str] = []

    for item in raw:
        if isinstance(item, str):
            val = item.strip()
            if val:
                out.append(val)
            continue

        if isinstance(item, dict):
            val = item.get("code") or item.get("name") or item.get("id") or item.get("status")
            if isinstance(val, str):
                val = val.strip()
                if val:
                    out.append(val)

    seen = set()
    cleaned: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            cleaned.append(s)
    return cleaned


@login_required
def sample_list(request):
    lab_ids = list(
        UserRole.objects.filter(user=request.user)
        .values_list("laboratory_id", flat=True)
        .distinct()
    )

    lab_id = None
    if lab_ids:
        raw = request.GET.get("lab") or lab_ids[0]
        try:
            lab_id = int(raw)
        except (TypeError, ValueError):
            lab_id = int(lab_ids[0])

    qs = Sample.objects.select_related("project").all()
    if lab_id:
        qs = qs.filter(Q(laboratory_id=lab_id) | Q(project__laboratory_id=lab_id))

    qs = qs.order_by("-id")[:500]

    wf = workflow_definition("sample")
    statuses = _extract_workflow_statuses(wf)
    if not statuses:
        statuses = list(qs.values_list("status", flat=True).distinct().order_by("status"))

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
    return render(request, "lims_core/samples/detail.html", {"sample": sample})


@login_required
def experiment_detail(request, pk: int):
    experiment = get_object_or_404(Experiment, pk=pk)
    return render(request, "lims_core/experiments/detail.html", {"experiment": experiment})
