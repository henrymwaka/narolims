# lims_core/tests/conftest.py

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional, Type

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import models
from rest_framework.test import APIClient

from lims_core.models import Experiment, Laboratory, Project, Sample, UserRole


def _rand(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _build_min_kwargs_for_model(model_cls: Type[models.Model], prefix: str = "X") -> Dict[str, Any]:
    """
    Create a minimal kwargs dict for a model by satisfying required fields.
    This avoids guessing exact field names for related models like Institute.
    """
    kwargs: Dict[str, Any] = {}

    for field in model_cls._meta.get_fields():
        # Skip reverse relations and m2m
        if not hasattr(field, "attname"):
            continue
        if getattr(field, "many_to_many", False):
            continue
        if getattr(field, "one_to_many", False):
            continue

        # Concrete model fields only
        if not isinstance(field, models.Field):
            continue

        # Auto fields and timestamps usually handled automatically
        if isinstance(field, (models.AutoField, models.BigAutoField)):
            continue

        # If Django can set this automatically or it has a default, skip
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        if field.has_default():
            continue
        if field.null:
            continue
        if field.blank:
            continue

        name = field.name

        # If already supplied, skip
        if name in kwargs:
            continue

        if isinstance(field, models.CharField):
            # Prefer semantic values for common names
            if name in {"code", "name", "title"}:
                kwargs[name] = _rand(prefix.upper())
            else:
                kwargs[name] = _rand(prefix)
        elif isinstance(field, models.TextField):
            kwargs[name] = f"{prefix} text"
        elif isinstance(field, models.BooleanField):
            kwargs[name] = True
        elif isinstance(field, models.IntegerField):
            kwargs[name] = 1
        elif isinstance(field, models.UUIDField):
            kwargs[name] = uuid.uuid4()
        elif isinstance(field, models.ForeignKey):
            rel_model = field.remote_field.model
            # Avoid infinite recursion on self FK
            if rel_model == model_cls:
                continue
            rel_kwargs = _build_min_kwargs_for_model(rel_model, prefix=prefix)
            kwargs[name] = rel_model.objects.create(**rel_kwargs)
        else:
            # Last resort: try a safe placeholder
            if isinstance(field, models.DateField):
                kwargs[name] = "2025-01-01"
            elif isinstance(field, models.DateTimeField):
                kwargs[name] = "2025-01-01T00:00:00Z"

    return kwargs


class AuthAPIClient(APIClient):
    """
    Test client that uses force_authenticate for predictable DRF auth.
    """

    _user = None

    def login(self, username: str, password: str, **kwargs) -> bool:  # type: ignore[override]
        user = authenticate(username=username, password=password)
        if not user:
            return False
        self.force_authenticate(user=user)
        self._user = user
        return True

    def logout(self) -> None:  # type: ignore[override]
        # DO NOT call force_authenticate(user=None) here.
        # DRF's force_authenticate(user=None) calls self.logout() internally.
        super().logout()
        self.handler._force_user = None
        self.handler._force_token = None
        self._user = None


@pytest.fixture
def api_client() -> AuthAPIClient:
    return AuthAPIClient()


@pytest.fixture
def user_admin(db):
    User = get_user_model()
    user, created = User.objects.get_or_create(username="admin", defaults={"is_staff": True, "is_superuser": False})
    # Always ensure password works even if user already existed
    user.set_password("pass123")
    user.is_staff = True
    user.save(update_fields=["password", "is_staff"])
    return user


@pytest.fixture
def user_technician(db):
    User = get_user_model()
    user, created = User.objects.get_or_create(username="labtech", defaults={"is_staff": False, "is_superuser": False})
    user.set_password("pass123")
    user.save(update_fields=["password"])
    return user


@pytest.fixture
def user_qa(db):
    User = get_user_model()
    user, created = User.objects.get_or_create(username="qa", defaults={"is_staff": False, "is_superuser": False})
    user.set_password("pass123")
    user.save(update_fields=["password"])
    return user


@pytest.fixture
def users(user_admin, user_technician):
    # Tests expect [admin, labtech]
    return [user_admin, user_technician]


@pytest.fixture
def institute(db):
    """
    Laboratory.institute is NOT NULL in your schema.
    Create an institute-like object using the actual related model.
    """
    institute_field = Laboratory._meta.get_field("institute")
    model_cls = institute_field.remote_field.model
    kwargs = _build_min_kwargs_for_model(model_cls, prefix="INST")
    # Try to make code/name nicer if those exist
    if "code" in {f.name for f in model_cls._meta.fields}:
        kwargs["code"] = _rand("INST")
    if "name" in {f.name for f in model_cls._meta.fields}:
        kwargs["name"] = _rand("Institute")
    return model_cls.objects.create(**kwargs)


@pytest.fixture
def laboratory(db, institute) -> Laboratory:
    """
    Pure laboratory fixture.
    No UserRole side effects here.
    """
    return Laboratory.objects.create(
        institute=institute,
        code=_rand("CODE"),
        name=_rand("Lab"),
    )


@pytest.fixture
def project(db, laboratory) -> Project:
    """
    Project fixture. Some schemas require laboratory or institute, so we
    satisfy required fields dynamically and then override the useful ones.
    """
    kwargs = _build_min_kwargs_for_model(Project, prefix="PRJ")

    # Override common fields if present
    field_names = {f.name for f in Project._meta.fields}
    if "laboratory" in field_names:
        kwargs["laboratory"] = laboratory
    if "name" in field_names:
        kwargs["name"] = _rand("Name")

    # If your Project has an institute FK too, keep it consistent
    if "institute" in field_names and hasattr(laboratory, "institute_id"):
        kwargs["institute"] = laboratory.institute

    return Project.objects.create(**kwargs)


@pytest.fixture
def sample_factory(db) -> Callable[..., Sample]:
    """
    Factory for creating samples with unique sample_id.
    """

    def _factory(
        *,
        laboratory: Laboratory,
        project: Project,
        status: str = "REGISTERED",
        sample_id: Optional[str] = None,
        sample_type: Optional[str] = None,
        **extra: Any,
    ) -> Sample:
        sid = sample_id or _rand("SAMPLE")
        stype = sample_type or "DEFAULT"

        return Sample.objects.create(
            laboratory=laboratory,
            project=project,
            sample_id=sid,
            sample_type=stype,
            status=status,
            **extra,
        )

    return _factory


@pytest.fixture
def experiment_factory(db) -> Callable[..., Experiment]:
    """
    Factory for creating experiments, keeping fields minimal and consistent.
    """

    def _factory(
        *,
        laboratory: Laboratory,
        status: str = "DRAFT",
        **extra: Any,
    ) -> Experiment:
        kwargs = {
            "laboratory": laboratory,
            "status": status,
        }

        # Fill common required fields if they exist
        field_names = {f.name for f in Experiment._meta.fields}
        if "code" in field_names and "code" not in extra:
            kwargs["code"] = _rand("EXP")
        if "name" in field_names and "name" not in extra:
            kwargs["name"] = _rand("Experiment")

        kwargs.update(extra)
        return Experiment.objects.create(**kwargs)

    return _factory


@pytest.fixture
def sample_with_roles(db, laboratory, project, user_admin, user_technician, user_qa, sample_factory) -> Sample:
    """
    Sample plus membership roles used by workflow tests.
    """
    # Role assignments (idempotent)
    UserRole.objects.get_or_create(user=user_admin, laboratory=laboratory, defaults={"role": "ADMIN"})
    UserRole.objects.get_or_create(user=user_technician, laboratory=laboratory, defaults={"role": "LAB_TECH"})
    UserRole.objects.get_or_create(user=user_qa, laboratory=laboratory, defaults={"role": "QA"})

    # Create the sample
    return sample_factory(
        laboratory=laboratory,
        project=project,
        status="REGISTERED",
    )
