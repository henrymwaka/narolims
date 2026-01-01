from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model

from .models import ConfigPack, SchemaPackItem, WorkflowPackDefinition, RolePackDefinition


def pack_to_dict(pack: ConfigPack) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "pack": {
            "code": pack.code,
            "name": pack.name,
            "kind": pack.kind,
            "version": pack.version,
            "description": pack.description,
            "is_published": pack.is_published,
        },
        "schema_items": [],
        "workflow_defs": [],
        "role_defs": [],
    }

    if pack.kind == ConfigPack.KIND_SCHEMA:
        for item in SchemaPackItem.objects.filter(pack=pack).select_related("schema").order_by("order", "id"):
            data["schema_items"].append(
                {
                    "order": item.order,
                    "is_required": item.is_required,
                    "schema": {
                        "code": item.schema.code,
                        "version": item.schema.version,
                    },
                }
            )

    if pack.kind == ConfigPack.KIND_WORKFLOW:
        for wd in WorkflowPackDefinition.objects.filter(pack=pack).order_by("object_kind", "code", "version"):
            data["workflow_defs"].append(
                {
                    "object_kind": wd.object_kind,
                    "code": wd.code,
                    "name": wd.name,
                    "version": wd.version,
                    "is_active": wd.is_active,
                    "definition": wd.definition,
                }
            )

    if pack.kind == ConfigPack.KIND_ROLE:
        for rd in RolePackDefinition.objects.filter(pack=pack).order_by("code", "version"):
            data["role_defs"].append(
                {
                    "code": rd.code,
                    "name": rd.name,
                    "version": rd.version,
                    "is_active": rd.is_active,
                    "definition": rd.definition,
                }
            )

    return data


def upsert_pack_from_dict(payload: Dict[str, Any], *, user=None) -> ConfigPack:
    p = payload.get("pack", {}) or {}

    pack, _ = ConfigPack.objects.update_or_create(
        code=p["code"],
        defaults={
            "name": p.get("name", p["code"]),
            "kind": p["kind"],
            "version": p.get("version", "v1"),
            "description": p.get("description", ""),
            "is_published": bool(p.get("is_published", False)),
        },
    )

    # Clear and rebuild contents for idempotency
    if pack.kind == ConfigPack.KIND_SCHEMA:
        SchemaPackItem.objects.filter(pack=pack).delete()
        for item in payload.get("schema_items", []) or []:
            schema_ref = (item.get("schema") or {})
            from lims_core.metadata.models import MetadataSchema  # local import to avoid cycles

            schema = MetadataSchema.objects.get(code=schema_ref["code"], version=schema_ref["version"])
            SchemaPackItem.objects.create(
                pack=pack,
                schema=schema,
                order=int(item.get("order", 10)),
                is_required=bool(item.get("is_required", False)),
            )

    if pack.kind == ConfigPack.KIND_WORKFLOW:
        WorkflowPackDefinition.objects.filter(pack=pack).delete()
        for wd in payload.get("workflow_defs", []) or []:
            WorkflowPackDefinition.objects.create(
                pack=pack,
                object_kind=wd["object_kind"],
                code=wd["code"],
                name=wd.get("name", wd["code"]),
                version=wd.get("version", "v1"),
                is_active=bool(wd.get("is_active", True)),
                definition=wd.get("definition", {}) or {},
            )

    if pack.kind == ConfigPack.KIND_ROLE:
        RolePackDefinition.objects.filter(pack=pack).delete()
        for rd in payload.get("role_defs", []) or []:
            RolePackDefinition.objects.create(
                pack=pack,
                code=rd["code"],
                name=rd.get("name", rd["code"]),
                version=rd.get("version", "v1"),
                is_active=bool(rd.get("is_active", True)),
                definition=rd.get("definition", {}) or {},
            )

    return pack
