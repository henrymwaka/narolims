from rest_framework import serializers
from .models import Project, Sample, Experiment, InventoryItem, UserRole, AuditLog
import uuid


class ProjectSerializer(serializers.ModelSerializer):
    created_by_username = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = Project
        fields = [
            "id", "name", "description", "start_date", "end_date",
            "created_by", "created_by_username",
        ]
        read_only_fields = ["id", "created_by", "created_by_username"]


class SampleSerializer(serializers.ModelSerializer):
    project_name = serializers.ReadOnlyField(source="project.name")
    # make it optional so create() can auto-generate
    sample_id = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Sample
        fields = [
            "id", "project", "project_name", "sample_id", "sample_type",
            "collected_on", "collected_by", "storage_location", "metadata",
        ]
        read_only_fields = ["id", "project_name"]

    def _gen_sample_id(self):
        return f"SMP-{uuid.uuid4().hex[:8].upper()}"

    def create(self, validated_data):
        # Only generate if omitted or blank
        if not validated_data.get("sample_id"):
            for _ in range(5):  # low collision chance; still be safe
                candidate = self._gen_sample_id()
                if not Sample.objects.filter(sample_id=candidate).exists():
                    validated_data["sample_id"] = candidate
                    break
        return super().create(validated_data)


class ExperimentSerializer(serializers.ModelSerializer):
    project_name = serializers.ReadOnlyField(source="project.name")
    sample_ids = serializers.SlugRelatedField(
        source="samples", many=True, read_only=True, slug_field="sample_id"
    )

    class Meta:
        model = Experiment
        fields = [
            "id", "project", "project_name", "name", "description",
            "samples", "sample_ids", "protocol_reference",
            "start_date", "end_date", "results",
        ]
        read_only_fields = ["id", "project_name", "sample_ids"]


class InventoryItemSerializer(serializers.ModelSerializer):
    # Works whether your model has `updated_at` or legacy `last_updated`
    updated_at = serializers.SerializerMethodField()

    def get_updated_at(self, obj):
        return getattr(obj, "updated_at", getattr(obj, "last_updated", None))

    class Meta:
        model = InventoryItem
        fields = [
            "id", "name", "category", "quantity", "unit",
            "location", "supplier", "expiry_date", "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class UserRoleSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")
    # Works whether model has `assigned_on` or refactored `created_at`
    assigned_on = serializers.SerializerMethodField()

    def get_assigned_on(self, obj):
        return getattr(obj, "assigned_on", getattr(obj, "created_at", None))

    class Meta:
        model = UserRole
        fields = ["id", "user", "username", "role", "assigned_on"]
        read_only_fields = ["id", "username", "assigned_on"]


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")
    # Emit `timestamp`, using `created_at` if refactored
    timestamp = serializers.SerializerMethodField()

    def get_timestamp(self, obj):
        return getattr(obj, "timestamp", getattr(obj, "created_at", None))

    class Meta:
        model = AuditLog
        fields = ["id", "user", "username", "action", "timestamp", "details"]
        read_only_fields = ["id", "username", "timestamp"]
