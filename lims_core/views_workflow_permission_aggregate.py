# lims_core/views_workflow_permission_aggregate.py

from __future__ import annotations

from typing import Dict, List, Set, Tuple, Type

from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ParseError, PermissionDenied

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from lims_core.models import Sample, Experiment, Laboratory, UserRole
from lims_core.workflows import allowed_next_states, required_roles, normalize_role


KIND_TO_MODEL: Dict[str, Type] = {
    "sample": Sample,
    "experiment": Experiment,
}


def _parse_object_ids(raw: str) -> List[int]:
    raw = (raw or "").strip()
    if not raw:
        raise ParseError("object_ids is required")

    ids: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except (TypeError, ValueError) as exc:
            raise ParseError("object_ids must be a comma-separated list of integers") from exc

    if not ids:
        raise ParseError("object_ids is required")

    # Preserve order, drop duplicates
    seen: Set[int] = set()
    ordered: List[int] = []
    for i in ids:
        if i not in seen:
            ordered.append(i)
            seen.add(i)
    return ordered


def _get_lab_id_from_request(request) -> str:
    # DRF normalizes headers into META keys with HTTP_ prefix
    lab_id = (
        request.META.get("HTTP_X_LABORATORY")
        or request.headers.get("X-Laboratory")
        or request.headers.get("X-LABORATORY")
    )
    if not lab_id:
        raise ParseError("Missing X_LABORATORY header")
    return str(lab_id).strip()


def _get_user_role_for_lab(user, lab: Laboratory) -> str:
    role = (
        UserRole.objects.filter(user=user, laboratory=lab)
        .values_list("role", flat=True)
        .first()
    )
    if not role:
        raise PermissionDenied("User has no role for this laboratory")
    return normalize_role(role)


def _label(source: str, target: str) -> str:
    return f"{source}->{target}"


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="object_ids",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Comma-separated list of object IDs to aggregate permissions for.",
        ),
        OpenApiParameter(
            name="X-LABORATORY",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.HEADER,
            required=True,
            description="Laboratory UUID/PK to scope permission checks.",
        ),
    ],
    responses={200: OpenApiTypes.OBJECT},
)
class WorkflowPermissionAggregateView(APIView):
    """
    Aggregates workflow transition permissions across many objects.

    Output contract (what tests expect):
      allowed_on_all: list[str]  transitions allowed for every object (e.g. "REGISTERED->IN_PROCESS")
      allowed_on_any: list[str]  transitions allowed for at least one object
      blocked_objects: dict[transition -> list[object_id]] objects that cannot do that transition
      terminal_objects: list[object_id] objects with no valid next states from their current state

    Note: "summary" is returned for UI/backwards compatibility, but tests read top-level keys.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str, *args, **kwargs):
        kind = (kind or "").strip().lower()
        if kind not in KIND_TO_MODEL:
            raise ParseError("Unsupported workflow kind")

        model = KIND_TO_MODEL[kind]

        lab_id = _get_lab_id_from_request(request)
        lab = get_object_or_404(Laboratory, id=lab_id)

        user_role = _get_user_role_for_lab(request.user, lab)

        object_ids = _parse_object_ids(request.query_params.get("object_ids", ""))

        # Pull objects, scoped to the lab
        qs = model.objects.filter(id__in=object_ids, laboratory=lab)
        objects_by_id = {obj.id: obj for obj in qs}

        # If any requested IDs are missing or not in this lab, treat as a bad request
        missing = [oid for oid in object_ids if oid not in objects_by_id]
        if missing:
            raise ParseError(f"Unknown object_ids: {','.join(str(x) for x in missing)}")

        objects = [objects_by_id[oid] for oid in object_ids]

        # 1) Determine candidate transitions across the selection
        #    Candidate transitions are SOURCE->TARGET pairs that are valid next moves
        #    for at least one object (based on its current status).
        candidate_pairs: Set[Tuple[str, str]] = set()
        per_obj_valid_pairs: Dict[int, Set[Tuple[str, str]]] = {}

        terminal_objects: List[int] = []
        for obj in objects:
            source = str(getattr(obj, "status", "") or "")
            targets = list(allowed_next_states(kind, source))
            pairs = {(source, t) for t in targets}
            per_obj_valid_pairs[obj.id] = pairs
            candidate_pairs |= pairs
            if not pairs:
                terminal_objects.append(obj.id)

        # 2) For each candidate transition, decide allowed/blocked per object
        allowed_on_any: Set[str] = set()
        allowed_on_all: Set[str] = {_label(s, t) for (s, t) in candidate_pairs} if candidate_pairs else set()

        # Deterministic ordering: sort by label
        sorted_pairs = sorted(candidate_pairs, key=lambda p: _label(p[0], p[1]))
        blocked_objects: Dict[str, List[int]] = {_label(s, t): [] for (s, t) in sorted_pairs}

        for (source, target) in sorted_pairs:
            transition = _label(source, target)

            for obj in objects:
                valid_for_obj = (source, target) in per_obj_valid_pairs[obj.id]

                if valid_for_obj:
                    roles = [normalize_role(r) for r in required_roles(kind, source, target)]
                    role_ok = user_role in roles
                else:
                    role_ok = False

                if valid_for_obj and role_ok:
                    allowed_on_any.add(transition)
                else:
                    blocked_objects[transition].append(obj.id)
                    allowed_on_all.discard(transition)

        payload = {
            "allowed_on_all": sorted(allowed_on_all),
            "allowed_on_any": sorted(allowed_on_any),
            "blocked_objects": blocked_objects,
            "terminal_objects": terminal_objects,
        }

        return Response({**payload, "summary": payload})
