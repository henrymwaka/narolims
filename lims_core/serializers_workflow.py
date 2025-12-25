# lims_core/serializers_workflow.py
from __future__ import annotations

from typing import Dict, Any

from rest_framework import serializers

from lims_core.models import Sample, Experiment
from lims_core.workflows.executor import execute_transition
from lims_core.workflows import allowed_next_states


class WorkflowTransitionSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("sample", "experiment"))
    object_id = serializers.IntegerField()
    new_status = serializers.CharField()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        kind = attrs["kind"]
        object_id = attrs["object_id"]
        new_status = attrs["new_status"].strip().upper()

        model = Sample if kind == "sample" else Experiment

        try:
            instance = model.objects.select_related("laboratory").get(pk=object_id)
        except model.DoesNotExist:
            raise serializers.ValidationError(
                {"object_id": f"{kind.capitalize()} does not exist."}
            )

        allowed = allowed_next_states(kind, instance.status)
        if new_status not in allowed:
            raise serializers.ValidationError(
                {
                    "new_status": (
                        f"Invalid transition from {instance.status}. "
                        f"Allowed: {allowed}"
                    )
                }
            )

        attrs["instance"] = instance
        attrs["new_status"] = new_status
        return attrs

    def save(self, **kwargs):
        request = self.context["request"]
        user = request.user

        execute_transition(
            instance=self.validated_data["instance"],
            kind=self.validated_data["kind"],
            new_status=self.validated_data["new_status"],
            user=user,
        )

        return self.validated_data["instance"]
