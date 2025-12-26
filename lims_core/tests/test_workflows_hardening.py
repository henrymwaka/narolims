from __future__ import annotations

import pathlib


def test_no_workflows_py_shadowing():
    p = pathlib.Path("lims_core/workflows.py")
    assert not p.exists(), (
        "Do not allow lims_core/workflows.py to exist. "
        "It can shadow the lims_core/workflows/ package and cause inconsistent imports."
    )


def test_workflows_public_api_contract():
    import lims_core.workflows as w

    required = {
        "workflow_definition",
        "allowed_transitions",
        "allowed_next_states",
        "normalize_role",
        "required_roles",
        "validate_transition_with_role",
    }

    missing = sorted(required - set(dir(w)))
    assert not missing, f"Workflows API missing exports: {missing}"

    assert callable(w.workflow_definition)
    assert callable(w.allowed_transitions)
    assert callable(w.allowed_next_states)
    assert callable(w.normalize_role)
    assert callable(w.required_roles)
    assert callable(w.validate_transition_with_role)
