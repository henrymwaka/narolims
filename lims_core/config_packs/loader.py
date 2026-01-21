from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

try:
    import yaml  # PyYAML
except Exception:  # pragma: no cover
    yaml = None


@dataclass(frozen=True)
class WizardStep:
    code: str
    title: str
    template: str


@dataclass(frozen=True)
class WizardConfig:
    wizard_id: str
    title: str
    steps: List[WizardStep]


class ConfigPackError(RuntimeError):
    pass


def _packs_base_dir() -> Path:
    # lims_core/config_packs/<pack_code>/*
    return Path(__file__).resolve().parent


def _read_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise ConfigPackError("PyYAML is not installed. Install pyyaml or vendor a parser.")
    if not path.exists():
        raise ConfigPackError(f"Missing config file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigPackError(f"Invalid YAML root (expected mapping): {path}")
    return data


def _validate_wizard(raw: Dict[str, Any], pack_code: str) -> WizardConfig:
    wizard_id = raw.get("wizard_id")
    title = raw.get("title", "Wizard")
    steps = raw.get("steps")

    if not isinstance(wizard_id, str) or not wizard_id.strip():
        raise ConfigPackError(f"{pack_code}: wizard.yaml missing valid wizard_id")

    if not isinstance(steps, list) or not steps:
        raise ConfigPackError(f"{pack_code}: wizard.yaml must contain a non-empty steps list")

    parsed_steps: List[WizardStep] = []
    seen: set[str] = set()

    for i, s in enumerate(steps, start=1):
        if not isinstance(s, dict):
            raise ConfigPackError(f"{pack_code}: step #{i} must be a mapping")

        code = s.get("code")
        stitle = s.get("title")
        template = s.get("template")

        if not isinstance(code, str) or not code.strip():
            raise ConfigPackError(f"{pack_code}: step #{i} missing valid code")
        if code in seen:
            raise ConfigPackError(f"{pack_code}: duplicate step code '{code}'")
        seen.add(code)

        if not isinstance(stitle, str) or not stitle.strip():
            raise ConfigPackError(f"{pack_code}: step '{code}' missing valid title")
        if not isinstance(template, str) or not template.strip():
            raise ConfigPackError(f"{pack_code}: step '{code}' missing valid template")

        parsed_steps.append(WizardStep(code=code, title=stitle, template=template))

    return WizardConfig(wizard_id=wizard_id.strip(), title=str(title), steps=parsed_steps)


def get_active_pack_code() -> str:
    # Later: allow per-lab override from DB.
    return getattr(settings, "CONFIG_PACK_DEFAULT", None) or "default"


def load_pack_wizard(pack_code: Optional[str] = None) -> WizardConfig:
    pack_code = (pack_code or get_active_pack_code()).strip()
    base = _packs_base_dir() / pack_code

    # pack.yaml exists mainly for metadata sanity
    _ = _read_yaml(base / "pack.yaml")
    raw_wizard = _read_yaml(base / "wizard.yaml")
    return _validate_wizard(raw_wizard, pack_code=pack_code)
