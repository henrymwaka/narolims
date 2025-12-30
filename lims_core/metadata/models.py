# lims_core/metadata/models.py

from django.db import models
from django.conf import settings


class MetadataSchema(models.Model):
    """
    Defines a metadata schema applied to a specific object type
    under a given laboratory profile and optional analysis context.

    IMPORTANT:
    - LaboratoryProfile and AnalysisContext live inside the lims_core app
      (they are under lims_core/labs/ but the app label is lims_core).
    """

    laboratory_profile = models.ForeignKey(
        "lims_core.LaboratoryProfile",
        on_delete=models.CASCADE,
        related_name="metadata_schemas",
        help_text="Laboratory profile this schema belongs to",
    )

    analysis_context = models.ForeignKey(
        "lims_core.AnalysisContext",
        on_delete=models.PROTECT,
        related_name="metadata_schemas",
        null=True,
        blank=True,
        help_text="Optional analysis context (e.g. Soil Fertility, Food Safety)",
    )

    code = models.CharField(
        max_length=64,
        help_text="Logical schema identifier (e.g. SAMPLE_CORE, WATER_QUALITY)",
    )

    version = models.CharField(
        max_length=16,
        default="v1",
        help_text="Schema version identifier",
    )

    name = models.CharField(
        max_length=128,
        help_text="Human-readable schema name",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of schema purpose",
    )

    applies_to = models.CharField(
        max_length=64,
        help_text="Object type this schema applies to (e.g. sample, batch)",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this schema is currently active",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Metadata Schema"
        verbose_name_plural = "Metadata Schemas"
        ordering = ["code", "version"]
        unique_together = (
            "laboratory_profile",
            "analysis_context",
            "code",
            "version",
            "applies_to",
        )

    def __str__(self):
        ctx = self.analysis_context.code if self.analysis_context else "default"
        return f"{self.code} ({self.version}) [{ctx}]"


class MetadataField(models.Model):
    """
    Defines an individual field inside a metadata schema.
    """

    FIELD_TYPES = (
        ("text", "Text"),
        ("number", "Number"),
        ("date", "Date"),
        ("boolean", "Boolean"),
        ("choice", "Choice"),
    )

    schema = models.ForeignKey(
        MetadataSchema,
        on_delete=models.CASCADE,
        related_name="fields",
        help_text="Schema this field belongs to",
    )

    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order within the schema",
    )

    code = models.CharField(
        max_length=64,
        help_text="Machine-readable field code",
    )

    label = models.CharField(
        max_length=128,
        help_text="Human-readable field label",
    )

    field_type = models.CharField(
        max_length=16,
        choices=FIELD_TYPES,
        default="text",
    )

    required = models.BooleanField(
        default=False,
        help_text="Whether this field is mandatory",
    )

    help_text = models.TextField(
        blank=True,
        help_text="Optional guidance for users",
    )

    choices = models.TextField(
        blank=True,
        help_text="Comma-separated values for choice fields",
    )

    class Meta:
        verbose_name = "Metadata Field"
        verbose_name_plural = "Metadata Fields"
        ordering = ["schema", "order"]
        unique_together = ("schema", "code")

    def __str__(self):
        return f"{self.schema.code}:{self.code}"

    def get_choices_list(self):
        if not self.choices:
            return []
        return [c.strip() for c in self.choices.split(",") if c.strip()]


class MetadataValue(models.Model):
    """
    Stores metadata values per object instance.
    """

    schema_field = models.ForeignKey(
        MetadataField,
        on_delete=models.CASCADE,
        related_name="values",
    )

    object_type = models.CharField(
        max_length=64,
        help_text="Object type (e.g. sample, batch)",
    )

    object_id = models.PositiveIntegerField(
        help_text="Primary key of the target object",
    )

    value_text = models.TextField(blank=True)
    value_number = models.FloatField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User who last set this value",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Metadata Value"
        verbose_name_plural = "Metadata Values"
        unique_together = ("schema_field", "object_type", "object_id")
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.schema_field} = {self.get_value()}"

    def get_value(self):
        ft = self.schema_field.field_type
        if ft == "number":
            return self.value_number
        if ft == "date":
            return self.value_date
        if ft == "boolean":
            return self.value_boolean
        return self.value_text
