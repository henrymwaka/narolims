# lims_core/serializers.py
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

from .workflows import validate_transition, allowed_next_states


# ===============================================================
# Helpers
# ===============================================================
class ImmutableFieldsMixin:
    """
    Blocks updates to selected fields if they appear in incoming data.
    Works for both PATCH and PUT.
    """
    immutable_fields: tuple[str, ...] = ()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if self.instance is not None and self.immutable_fields:
            for f in self.immutable_fields:
                if f in attrs:
                    raise serializers.ValidationError(
                        {f: "This field is immutable."}
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
    institute_code = serializers.CharField(
        source="institute.code", read_only=True
    )
    institute_name = serializers.CharField(
        source="institute.name", read_only=True
    )

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

    institute_code = serializers.CharField(
        source="institute.code", read_only=True
    )
    laboratory_code = serializers.CharField(
        source="laboratory.code", read_only=True
    )

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
    laboratory_code = serializers.CharField(
        source="laboratory.code", read_only=True
    )
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
# Sample (workflow-aware)
# ===============================================================
class SampleSerializer(ImmutableFieldsMixin, serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(
        source="laboratory.code", read_only=True
    )
    project_name = serializers.CharField(
        source="project.name", read_only=True
    )

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

    def get_allowed_next_states(self, obj: Sample) -> List[str]:
        return allowed_next_states("sample", obj.status)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        attrs = super().validate(attrs)

        if self.instance and "status" in attrs:
            try:
                validate_transition(
                    kind="sample",
                    old=self.instance.status,
                    new=attrs["status"],
                )
            except ValueError as e:
                raise serializers.ValidationError({"status": str(e)})

        return attrs


# ===============================================================
# Experiment (workflow-aware)
# ===============================================================
class ExperimentSerializer(ImmutableFieldsMixin, serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(
        source="laboratory.code", read_only=True
    )
    project_name = serializers.CharField(
        source="project.name", read_only=True
    )

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

    def get_allowed_next_states(self, obj: Experiment) -> List[str]:
        return allowed_next_states("experiment", obj.status)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        attrs = super().validate(attrs)

        if self.instance and "status" in attrs:
            try:
                validate_transition(
                    kind="experiment",
                    old=self.instance.status,
                    new=attrs["status"],
                )
            except ValueError as e:
                raise serializers.ValidationError({"status": str(e)})

        return attrs


# ===============================================================
# Inventory
# ===============================================================
class InventoryItemSerializer(serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(
        source="laboratory.code", read_only=True
    )

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
    laboratory_code = serializers.CharField(
        source="laboratory.code", read_only=True
    )
    user_username = serializers.CharField(
        source="user.username", read_only=True
    )

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
# AuditLog
# ===============================================================
class AuditLogSerializer(serializers.ModelSerializer):
    laboratory = serializers.PrimaryKeyRelatedField(read_only=True)
    laboratory_code = serializers.CharField(
        source="laboratory.code", read_only=True
    )
    user_username = serializers.CharField(
        source="user.username", read_only=True
    )

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
