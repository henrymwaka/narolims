# Checkpoint Release Notes
## checkpoint-workflow-tests-green-2025-12-26

**Date:** 2025-12-26  
**Scope:** Workflow permissions, guarded transitions, test harness stabilization

### Summary
This checkpoint stabilizes the Sample workflow authorization layer and the supporting test suite. Role-based transition visibility and enforcement are now consistently validated through API-level tests, with guarded workflow fields protected from direct writes except via explicit bypass during controlled setup.

### Key changes
- Implemented and validated role-dependent workflow visibility via `/lims/workflows/sample/<id>/allowed/`.
- Implemented and validated role-enforced transitions via `/lims/workflows/sample/<id>/transition/`.
- Hardened workflow rules and guardrails to prevent direct state manipulation outside controlled bypass.
- Added bulk workflow transition service (`lims_core/services/workflow_bulk.py`) with corresponding test coverage.
- Stabilized fixtures and factories to respect DB constraints (notably unique `sample_id`) and idempotent membership setup.
- Fixed DRF test client authentication/logout behavior (resolved 401 failures and logout recursion).
- Added engineering change protocol guide: `docs/CHANGE_PROTOCOL.md`.
- Test baseline: `make test-fast` green (36 tests passing).

### Files touched (high-level)
- Workflow: `lims_core/workflows/{guards.py,rules.py,__init__.py}`
- API: `lims_core/{urls.py,views.py}` + workflow view modules
- Tests: `lims_core/tests/*` (fixtures + workflow permission/transition suites)
- Docs: `docs/CHANGE_PROTOCOL.md`

### Validation
- `make test-fast` → **PASS** (36 tests)

### Notes / follow-ups
- The checkpoint tag was pushed unsigned due to tag signing configuration mismatch; a signed follow-up tag can be created once SSH signing is enabled (`gpg.format=ssh`).
