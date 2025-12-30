# lims_core/labs/models_analysis_context.py

from django.db import models


class AnalysisContext(models.Model):
    """
    Represents the ANALYTICAL CONTEXT under which a sample is examined.

    Examples:
    - SOIL_CHEMISTRY
    - PLANT_MINERAL
    - WATER_QUALITY
    - FOOD_SAFETY
    - BIOCHEMISTRY

    This is intentionally:
    - lab-agnostic
    - sample-type-agnostic
    - workflow-agnostic
    """

    # Stable machine identifier (used in code & schemas)
    code = models.CharField(
        max_length=64,
        unique=True,
        help_text="Stable identifier, e.g. SOIL_CHEMISTRY, WATER_QUALITY",
    )

    # Human-facing name
    name = models.CharField(
        max_length=128,
        help_text="Human-readable name, e.g. Soil Chemistry",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of analytical scope",
    )

    # Optional grouping for UI / reporting
    category = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional grouping, e.g. environmental, food, biological",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Analysis Context"
        verbose_name_plural = "Analysis Contexts"
        ordering = ["name"]

    def __str__(self):
        return self.name
