from __future__ import annotations

from typing import Any, Dict, List

from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    Institute,
    Laboratory,
    StaffMember,
    Project,
    Sample,
    Experiment,
    InventoryItem,
    UserRole,
    AuditLog,
)

from .workflows import allowed_next_states


# ===============================================================
# Helpers
# ===============================================================

class ImmutableFieldsMixin:
    """
    Blocks updates to selected fields if they appear in incoming validated data.
    """
    immutable_fields: tuple[str, ...] = ()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if self.instance is not None and self.immutable_fields:
            for field in self.immutable_fields:
                if field in attrs:
                    raise serializers.ValidationError(
                        {field: "This field is immutable."}
                    )
        return super().validate(attrs)


class UserSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = fields


# ===============================================================
# Institute / Laboratory
# ===============================================================

class InstituteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institute
        fields = (
            "id",
            "code",
            "name",
            "location",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class LaboratorySerializer(serializers.ModelSerializer):
    institute_code = serializers.CharField(source="institute.code", read_only=True)
    institute_name = serializers.CharField(source="institute.name", read_only=True)

    class Meta:
        model = Laboratory
        fields = (
            "id",
            "institute",
            "institute_code",
            "institute_name",
            "code",
            "name",
            "location",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "institute_code",
            "institute_name",
        )


# ===============================================================
# Staff
# ===============================================================

class StaffMemberSerializer(ImmutableFieldsMixin, serializers.ModelSerializer):
    user = UserSlimSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    institute_code = serializers.CharField(source="institute.code", read_only=True)
    laboratory_code = serializers.CharField(source="laboratory.code", read_only=True)

    immutable_fields = ("institute", "laboratory")

    class Meta:
        model = StaffMember
        fields = (
            "id",
            "institute",
            "institute_code",
            "laboratory",
            "laboratory_code",
            "user",
            "user_id",
            "staff_type",
            "full_name",
            "email",
            "phone",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "institute_code",
            "laboratory_code",
            "user",
        )


# ===============================================================
# Project
# ===============================================================

class ProjectSerializer(serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(source="laboratory.code", read_only=True)
    created_by = UserSlimSerializer(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "name",
            "description",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "created_by",
            "created_at",
            "updated_at",
        )


# ===============================================================
# Sample
# ===============================================================

class SampleSerializer(ImmutableFieldsMixin, serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(source="laboratory.code", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    allowed_next_states = serializers.SerializerMethodField()

    immutable_fields = ("project",)

    class Meta:
        model = Sample
        fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "project",
            "project_name",
            "sample_id",
            "sample_type",
            "status",
            "allowed_next_states",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "project_name",
            "allowed_next_states",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        # Schema freezing handled in Sample.save()
        return super().create(validated_data)

    def get_allowed_next_states(self, obj: Sample) -> List[str]:
        return allowed_next_states("sample", obj.status)


# ===============================================================
# Experiment
# ===============================================================

class ExperimentSerializer(ImmutableFieldsMixin, serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(source="laboratory.code", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    allowed_next_states = serializers.SerializerMethodField()

    immutable_fields = ("project",)

    class Meta:
        model = Experiment
        fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "project",
            "project_name",
            "name",
            "status",
            "allowed_next_states",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "project_name",
            "allowed_next_states",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        # Schema freezing handled in Experiment.save()
        return super().create(validated_data)

    def get_allowed_next_states(self, obj: Experiment) -> List[str]:
        return allowed_next_states("experiment", obj.status)


# ===============================================================
# Inventory
# ===============================================================

class InventoryItemSerializer(serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(source="laboratory.code", read_only=True)

    class Meta:
        model = InventoryItem
        fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "name",
            "quantity",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "created_at",
            "updated_at",
        )


# ===============================================================
# UserRole
# ===============================================================

class UserRoleSerializer(serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(source="laboratory.code", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserRole
        fields = (
            "id",
            "user",
            "user_username",
            "laboratory",
            "laboratory_code",
            "role",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "user_username",
            "created_at",
            "updated_at",
        )


# ===============================================================
# AuditLog (READ-ONLY)
# ===============================================================

class AuditLogSerializer(serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(source="laboratory.code", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "laboratory",
            "laboratory_code",
            "user",
            "user_username",
            "action",
            "details",
            "created_at",
        )
        read_only_fields = fields
