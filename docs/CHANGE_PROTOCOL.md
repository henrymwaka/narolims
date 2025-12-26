# NARO-LIMS Change Protocol and File Mapping Guide

This document defines the required engineering approach for making changes to NARO-LIMS safely and predictably. It exists to prevent regressions, reduce time lost in debugging, and make large changes easier to review and roll back.

## Goals

- Prevent regressions caused by unscoped edits
- Make every change traceable to the files and layers it touches
- Keep workflow, permissions, and lab scoping coherent
- Keep commits small, reviewable, and reversible
- Maintain a stable test baseline at all times

---

## 1. Operating principles

1. No blind edits  
   Every change starts with mapping where the behavior lives, how it is called, and how it is tested.

2. One change set, one intent  
   Do not mix workflow, auth, UI, docs, and infra changes in one commit unless they are inseparable.

3. Tests are the contract  
   If you change behavior, you must change or add tests to encode that behavior.

4. Workflow state is protected  
   Direct writes to guarded workflow fields (example: `Sample.status`) must remain forbidden outside explicit bypass for migrations and test setup.

5. Preserve rollback paths  
   Every change should have a clear revert strategy, including database and configuration.

---

## 2. Mandatory pre-change mapping checklist

Before editing code, write down answers to these. If you cannot answer them, map first.

### Entry point
- UI URL (if applicable)
- API endpoint path
- HTTP method(s)
- Required headers (example: `X-Laboratory`)
- Authentication mechanism (session, token, both)
- Expected request payload and response keys

### Routing
- URL pattern name
- URL file(s) involved
- Reverse names used by frontend or templates

### View or ViewSet
- View function or class
- Serializer(s) used
- Permission classes used
- Pagination or throttling (if any)

### Domain layer
- Service function(s) invoked
- Workflow rules module (if workflow-related)
- Validation and guardrails that apply

### Models and database
- Models and fields touched
- Constraints (NOT NULL, unique, FK requirements)
- Signals, `save()` overrides, guards

### Side effects
- Workflow events and audit logs
- Notifications
- File writes
- Background jobs or Celery tasks

### Tests
- Existing tests that cover this today
- New tests to add
- Regression test to prevent recurrence

---

## 3. Canonical API contracts (do not drift)

### Workflow transition endpoint payload
The canonical request body for workflow transitions is:

```json
{ "to": "QC_PASSED" }

Backwards-compatible aliases accepted for legacy callers only:

{ "to_status": "QC_PASSED" }
{ "status": "QC_PASSED" }

Rules:

All new code and tests must use to.

Aliases exist only to avoid breaking older clients and should be phased out later.

When validation fails for missing target, error key should be to.
4. Files that must be mapped before changes
A) Routing and public API surface

lims_core/urls.py

lims_core/views.py

lims_core/views_workflow_permissions.py

lims_core/views_workflow_permission_aggregate.py

lims_core/views_workflow_introspection.py

lims_core/views_workflow_api.py

lims_core/views_workflow_bulk.py

Change rules:

Any new endpoint must have a test that hits it (status code and payload).

Any auth change must be tested for both authenticated and unauthenticated requests.

B) Workflow rules and guardrails (high risk)

lims_core/workflows/rules.py

lims_core/workflows/guards.py

lims_core/workflows/__init__.py

lims_core/workflows/executor.py (if present)

lims_core/services/workflow_bulk.py

Change rules:

Never weaken guards to make tests pass.

Use _workflow_bypass=True only for test setup and controlled repair scripts.

If transitions change, update all affected tests:

allowed transitions endpoint tests

transition endpoint tests

permission matrix tests

aggregate permission tests

bulk transition tests

terminal lock tests

C) Auth, permissions, membership model (high risk)

naro_lims/settings.py (DRF config, middleware assumptions)

lims_core/models.py for membership models (UserRole, StaffMember)

lims_core/views.py lab scoping and role resolution helpers (if used)

lims_core/tests/conftest.py test auth harness

Change rules:

Tests must not rely on default session state.

Ensure logout clears auth without recursion or hidden side effects.

When lab context is required, tests must set it consistently (header or query param).

D) Database constraints and fixtures (frequent failure point)

Model constraints: NOT NULL, unique, FK requirements

Fixtures and factories:

lims_core/tests/conftest.py

any test helpers in lims_core/tests/

Change rules:

Fixtures must satisfy real constraints.

Use idempotent patterns where appropriate:

get_or_create for stable lookup objects (roles, institutes)

unique generators for sample_id and other unique fields

Never create labs without institutes if Laboratory.institute is required.

E) Build, CI, and repo governance

Makefile

.github/workflows/*

.github/CODEOWNERS

.gitignore

README.md

Change rules:

Only edit these when intentionally changing build or governance.

Do not let them drift as incidental edits during feature work.

5. Standard change workflow (the safe sequence)
Step 1: Baseline verification

Run a fast suite proving the area is stable:

make test-fast


If baseline is failing, fix baseline first. Do not add features on top of failing baseline.

Step 2: Tests first

Add or update a failing test that represents the bug or missing behavior.

Ensure the failure is for the right reason (not fixtures or missing payload keys).

Step 3: Implement in the correct layer

Prefer this order:

Pure logic in services (easy to test)

Workflow rules and permission checks

Views and controllers

URL routing

UI templates and JS (if any)

Step 4: Run focused tests during development

Examples:

pytest -q lims_core/tests/test_workflow_allowed.py -q
pytest -q lims_core/tests/test_workflow_permission_matrix.py -q
pytest -q lims_core/tests/test_workflow_permission_aggregate.py -q
pytest -q lims_core/tests/test_workflow_transitions.py -q
pytest -q lims_core/tests/test_bulk_workflow_transitions.py -q
pytest -q lims_core/tests/test_terminal_lock.py -q

Step 5: Final gate before commit
make test-fast
git diff
git status

6. Workflow guardrail rules (non-negotiable)

Direct modification of guarded workflow fields must remain blocked.

Any test that needs a starting state must use explicit bypass:

Example:

set status

save with _workflow_bypass=True

Do not introduce implicit bypasses or broaden bypass scope.

7. Commit and checkpoint rules
Recommended commit structure

Commit 1: workflow logic and endpoints and tests

Commit 2: docs only

Commit 3: build or CI only (if required)

Checkpoint commit message format

Checkpoint: <topic> (<test status>)

Example:
Checkpoint: workflow permissions and bulk transitions (36 tests green)

Tagging rules

Use annotated, signed tags for checkpoints when signing is working.

Do not push all tags blindly if you have older local tags.

Preferred:

git tag -s checkpoint-<topic>-YYYY-MM-DD -m "<short message>"
git push origin checkpoint-<topic>-YYYY-MM-DD


If a tag already exists on remote and you need to replace it, delete remote tag first, then recreate and push.

8. Definition of done for any change

A change is done only when:

make test-fast passes

New behavior is encoded in tests

Fixtures satisfy DB constraints

Commit is scoped and reviewable

Documentation is updated if the change is non-trivial

Optional: checkpoint tag created for major milestones

9. Quick troubleshooting map
401 Unauthorized

Check:

test client login logic in lims_core/tests/conftest.py

DRF auth settings in naro_lims/settings.py

endpoint permission classes

missing lab context header or query parameter

403 Forbidden

Check:

user lacks UserRole membership for the lab

role mismatch for the transition

permission logic differs between allowed endpoint and transition executor

400 Bad Request

Check:

payload key mismatch (to vs to_status vs status)

serializer required fields missing

content type and format="json" missing in tests

IntegrityError / NOT NULL / UNIQUE violations

Check:

required FK fields not created in fixtures

unique fields duplicated or blank

get_or_create vs create used appropriately

Workflow guard PermissionDenied

This is expected when directly saving guarded status fields. Use workflow APIs, or explicit bypass for test setup only.
