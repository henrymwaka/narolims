# lims_core/metadata/schema_revision.py

from django.db import transaction
from django.utils import timezone

from lims_core.metadata.models import MetadataSchema, MetadataField


@transaction.atomic
def clone_schema_revision(*, schema: MetadataSchema, user, reason: str = "") -> MetadataSchema:
    """
    Creates a new editable schema revision, copying fields.
    The original schema should remain locked and untouched.
    """
    new_schema = MetadataSchema.objects.create(
        code=f"{schema.code}.v{schema.version + 1}",
        name=schema.name,
        description=schema.description,
        object_type=schema.object_type,
        analysis_context=schema.analysis_context,
        version=schema.version + 1,
        supersedes=schema,
        is_locked=False,
        locked_at=None,
        locked_by=None,
        lock_reason="",
    )

    fields = schema.fields.all().order_by("order", "id")
    new_fields = []
    for f in fields:
        new_fields.append(
            MetadataField(
                schema=new_schema,
                code=f.code,
                label=f.label,
                field_type=f.field_type,
                required=f.required,
                choices=getattr(f, "choices", ""),
                help_text=getattr(f, "help_text", ""),
                order=f.order,
            )
        )

    MetadataField.objects.bulk_create(new_fields)

    # Optional: record revision reason somewhere central, if you have an audit model
    _ = reason
    _ = timezone.now()
    _ = user

    return new_schema
