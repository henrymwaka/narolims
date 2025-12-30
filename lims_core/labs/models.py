# lims_core/labs/models.py

from django.db import models


class LaboratoryProfile(models.Model):
    """
    Describes a laboratory's operational and metadata configuration.

    - One profile per Laboratory
    - Binds the lab to metadata schemas
    - Drives UI rendering, validation, and workflow gating
    - Provides default analysis context for cross-matrix labs
    """

    laboratory = models.OneToOneField(
        "lims_core.Laboratory",
        on_delete=models.CASCADE,
        related_name="profile",  # canonical accessor
    )

    # --------------------------------------------------
    # Administrative classification
    # --------------------------------------------------
    lab_type = models.CharField(
        max_length=64,
        help_text="e.g. soils, water, biotech, food_science, biochemistry",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of lab scope and capabilities",
    )

    # --------------------------------------------------
    # Metadata schema binding (LAB DEFAULT)
    # --------------------------------------------------
    # Used when no analysis context–specific schema applies
    schema_code = models.CharField(
        max_length=64,
        help_text="Logical default schema identifier, e.g. INTAKE_CORE",
    )

    schema_version = models.CharField(
        max_length=16,
        default="v1",
        help_text="Default schema version applied to this laboratory",
    )

    # --------------------------------------------------
    # NEW: Default analysis context (minimal change)
    # --------------------------------------------------
    default_analysis_context = models.ForeignKey(
        "lims_core.AnalysisContext",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_labs",
        help_text=(
            "Default analysis context for new samples in this lab "
            "(e.g. SOIL_CHEMISTRY, WATER_QUALITY, FOOD_SAFETY)."
        ),
    )

    # --------------------------------------------------
    # Status & audit
    # --------------------------------------------------
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Laboratory Profile"
        verbose_name_plural = "Laboratory Profiles"
        ordering = ["laboratory__code"]

    def __str__(self):
        return (
            f"{self.laboratory.code} | "
            f"{self.lab_type} | "
            f"{self.schema_code}:{self.schema_version}"
        )

    # --------------------------------------------------
    # Compatibility alias (NO DB impact)
    # --------------------------------------------------
    @property
    def laboratoryprofile(self):
        """
        Compatibility alias so code expecting lab.laboratoryprofile
        continues to work without breaking the schema.

        DO NOT remove.
        """
        return self
