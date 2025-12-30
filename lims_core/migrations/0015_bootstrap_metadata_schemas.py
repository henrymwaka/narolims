# lims_core/migrations/0015_bootstrap_metadata_schemas.py

from django.db import migrations


def bootstrap_metadata_schemas(apps, schema_editor):
    """
    Ensure every LaboratoryProfile has at least one active MetadataSchema
    for SAMPLE objects.

    Safe, idempotent, and non-destructive.
    """

    LaboratoryProfile = apps.get_model(
        "lims_core", "LaboratoryProfile"
    )
    MetadataSchema = apps.get_model(
        "lims_core", "MetadataSchema"
    )

    for profile in LaboratoryProfile.objects.all():
        has_schema = MetadataSchema.objects.filter(
            laboratory_profile=profile,
            applies_to="sample",
            is_active=True,
        ).exists()

        if has_schema:
            continue

        MetadataSchema.objects.create(
            name="Default Sample Metadata",
            code=f"DEFAULT_SAMPLE_{profile.id}",
            applies_to="sample",
            laboratory_profile=profile,
            version=1,
            description=(
                "Auto-created baseline metadata schema. "
                "Edit or replace with laboratory-specific definitions."
            ),
            is_active=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("lims_core", "0014_alter_metadatafield_unique_together_metadatavalue"),
    ]

    operations = [
        migrations.RunPython(
            bootstrap_metadata_schemas,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
