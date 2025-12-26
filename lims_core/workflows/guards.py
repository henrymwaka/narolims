# lims_core/workflows/guards.py

from django.core.exceptions import PermissionDenied
from django.db import models


class WorkflowWriteGuardMixin(models.Model):
    """
    Prevent direct modification of workflow-controlled fields outside the workflow engine.

    Models inheriting this mixin must transition via the workflow API/engine.
    Direct .save() changes to WORKFLOW_FIELD are blocked.

    Escape hatch:
      - pass _workflow_bypass=True to save(), OR
      - set instance._workflow_bypass = True
    Use sparingly (tests, data fixes, admin repair scripts).
    """

    WORKFLOW_FIELD = "status"
    WORKFLOW_BYPASS_KWARG = "_workflow_bypass"

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        bypass = bool(
            kwargs.pop(self.WORKFLOW_BYPASS_KWARG, False)
            or getattr(self, "_workflow_bypass", False)
        )

        if not bypass and self.pk is not None and self.WORKFLOW_FIELD:
            old = (
                self.__class__.objects.filter(pk=self.pk)
                .values_list(self.WORKFLOW_FIELD, flat=True)
                .first()
            )
            new = getattr(self, self.WORKFLOW_FIELD, None)

            if old != new:
                raise PermissionDenied(
                    f"Direct modification of '{self.WORKFLOW_FIELD}' is forbidden. "
                    "Use workflow transition APIs."
                )

        return super().save(*args, **kwargs)
