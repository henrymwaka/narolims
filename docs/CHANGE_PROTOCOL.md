# NARO-LIMS Change Protocol and File Mapping Guide

This document defines the non-negotiable workflow for making changes to NARO-LIMS (or any large Django platform in the ResLab stack) without breaking production or wasting time. It is designed to enforce predictable edits, fast verification, and clean rollbacks.

## Goals

- Prevent regressions caused by unscoped edits.
- Make every change traceable to the files and layers it touches.
- Ensure tests, permissions, workflows, and deployments remain coherent.
- Keep changes small, reviewable, and reversible.

---

## The golden rules

1. **Do not edit code until you can reproduce the current behavior.**  
   If it is a bug, reproduce it locally or in staging with a minimal failing test or an exact request log.

2. **One change set, one intent.**  
   A single PR or commit series should target one feature or one bugfix. No opportunistic refactors.

3. **Touch the smallest surface area.**  
   Prefer changing one function, one serializer, one permission class, one template block, one endpoint at a time.

4. **Every behavioral change requires tests.**  
   Tests are not optional. They are the insurance policy against re-breakage.

5. **Workflow state transitions are never edited directly unless explicitly bypassed.**  
   If a model has workflow guardrails, transitions must go through the workflow service or API, except for test setup using explicit bypass flags.

6. **Always map the layers before editing.**  
   You must identify the entrypoint, routing, permission enforcement, data model, and response serialization before you change anything.

7. **Rollbacks must be possible.**  
   Every change should have a clear revert path, including database migrations.

---

## The mapping step (mandatory)

Before changing anything, fill this map for the feature/bug. If you cannot fill it, you are not ready to edit.

### 1) Entry point

- UI page URL (if applicable):
- API endpoint path:
- HTTP method(s):
- Required headers (example: `X-LABORATORY`):
- Auth mechanism (session, token, both):
- Expected request payload and response format:

### 2) Routing

- Django URL pattern name:
- URL file(s) involved (usually `urls.py` or `*_urls.py`):
- Reverse names used by frontend:

### 3) View or ViewSet

- View function/class:
- Serializer(s) used:
- Permission classes used:
- Throttle or pagination:

### 4) Domain layer

- Service function(s) invoked:
- Workflow rules module (if workflow-related):
- Validation rules:

### 5) Models and DB

- Model(s) involved:
- Constraints (unique, not null, FK required):
- Signals, `save()` overrides, guards:

### 6) Frontend and templates (if relevant)

- Template file(s):
- JS file(s):
- Forms, serializers, or data adapters used:

### 7) Background jobs (if relevant)

- Celery task(s):
- Queue and schedule:
- Retry policy and idempotency:

### 8) Tests

- Existing tests that should cover this:
- New tests to add:
- Regression test to prevent recurrence:

---

## Change workflow (the safe sequence)

Follow this sequence for every change.

### Step A: Snapshot current state

- Identify current branch and commit:
- Run fast tests:
  - `make test-fast` (or equivalent)
- Capture the failing request if bug-driven:
  - Path, headers, payload, response, status, error message

### Step B: Add or update tests first

- Add a failing test that represents the bug or missing feature.
- Ensure the failure is meaningful (correct reason, not random fixtures).

### Step C: Implement the smallest fix

- Make the minimum code change required for the test to pass.
- Avoid refactors unless they are strictly required.

### Step D: Run verification in layers

Run checks in this order:

1. Unit tests or targeted tests for the changed area  
   Example:
   - `pytest -q lims_core/tests/test_workflow_transitions.py -q`
2. Fast suite  
   - `make test-fast`
3. Lint/format if enforced in repo
4. Manual smoke test of the endpoint or UI path
5. Optional: full test suite before merge

### Step E: Document the change

- Update or add doc note under `docs/`:
  - what changed
  - why it changed
  - how to test it
  - rollback notes

### Step F: Deploy with reversible steps

- Deploy to staging first if available.
- Verify logs and key flows.
- Only then deploy to production.

---

## Files that must be mapped before edits

This section is a practical checklist. If your change touches any of these, map them explicitly.

### 1) Workflow system (high risk)

Map these first when touching workflow behavior.

- `lims_core/workflows/`  
  Workflow rules, allowed transitions, guards, and policy enforcement.
- `lims_core/workflows/guards.py`  
  Often blocks direct status edits and enforces transition APIs.
- Any workflow service module that computes allowed transitions.

Key hazards:
- Direct `.save(update_fields=["status"])` may be blocked by guard logic.
- Test setup may require explicit bypass flags (example: `_workflow_bypass=True`).
- Allowed transitions must align across:
  - backend rules
  - permission matrix endpoints
  - transition endpoints
  - aggregate permission endpoints
  - frontend assumptions

Required tests:
- allowed transitions by role
- transition enforcement by role
- aggregate permission logic across multiple objects
- bulk transition behavior

### 2) Permissions and labs (high risk)

Map these first when you see 401, 403, or inconsistent access.

- Permission classes in API views
- Middleware that binds laboratory context
- Header requirement: `X-LABORATORY` or equivalent
- `UserRole` assignment logic and membership checks

Key hazards:
- Missing laboratory header may cause 401 or 403.
- Fixture roles must match real authorization checks.

### 3) Models with DB constraints (high risk)

Map these when you see IntegrityError, NotNullViolation, UniqueViolation.

- Model fields with `unique=True`
- FK fields with `null=False`
- Any `save()` override
- Signals and automatic field population

Typical examples:
- `Laboratory.institute` required FK  
  Do not create a laboratory fixture without creating an institute first.
- `Sample.sample_id` unique  
  Test fixtures must generate unique sample IDs, not blank strings.

### 4) API serialization (medium to high risk)

Map these when you see 400 Bad Request.

- Serializer required fields
- Serializer input field naming conventions
- View expects `{"to": "STATE"}` vs `{"target": "STATE"}` vs `{"status": "STATE"}`

Rule:
- There must be one canonical payload shape. If tests allow fallbacks, keep the fallbacks temporary and document them.

### 5) URLs and namespacing (medium risk)

Map these before adding endpoints.

- `lims_core/urls.py`
- app-level `urls.py`
- namespace usage: `lims_core:...`
- reverse names used by frontend

Rule:
- Never rename a URL name without a migration plan for frontend references.

### 6) Frontend templates and static assets (medium risk)

Map these before changing UI behavior.

- Templates under `templates/`
- Static JS under `static/`
- Any API adapters or fetch calls
- Any assumptions about payload shape and response keys

Rule:
- If you change an API response, update the frontend and tests in the same change set.

### 7) Celery and async processing (medium risk)

Map these before changing long-running tasks.

- `celery.py` setup and task routing
- task files under app modules
- Redis/broker configuration
- result backend usage

Rule:
- Tasks must be idempotent and retry-safe.

### 8) Deployment layer (high risk in production)

Map these before changing runtime behavior.

- Nginx site config for the domain
- systemd service file for gunicorn
- environment variables and secrets
- Cloudflare tunnel settings if applicable

Rule:
- Do not change production config without a clear rollback plan.

---

## Fixture and test reliability rules

Tests are a frequent source of false failures in large systems. Use these rules to keep them stable.

### Use `get_or_create` where uniqueness is enforced

- For users with fixed usernames used across tests, use `get_or_create`.
- For objects with unique constraints, always generate unique values.

### Always satisfy non-null FK requirements

If a model requires a foreign key, create the parent in a fixture and pass it explicitly.

Example pattern:
- create Institute
- create Laboratory(institute=institute)
- create Project(laboratory=laboratory) if required
- create Sample(laboratory=laboratory, project=project, sample_id=unique)

### Avoid hidden side effects in fixtures

Fixtures should not silently assign roles or mutate global state unless explicitly named for it.

Preferred:
- `laboratory()` returns only a lab
- `user_roles()` returns memberships and roles
- `sample_with_roles()` clearly indicates role wiring

### Do not shadow framework methods in helpers

If you extend DRF APIClient for tests, do not override methods like `logout()` in ways that call themselves.

Preferred:
- name wrappers `logout_user()` or `clear_auth()`
- if overriding, call `super().logout()` carefully

---

## “Stop, verify, then change” commands

Use short, consistent verification commands.

### Targeted tests

```bash
pytest -q lims_core/tests/test_workflow_transitions.py -q
pytest -q lims_core/tests/test_workflow_allowed.py -q
pytest -q lims_core/tests/test_workflow_permission_aggregate.py -q
```

### Fast suite

```bash
make test-fast
```

### Full suite (when preparing merge)

```bash
pytest
```

---

## Logging and observability checklist

When debugging 400, 401, 403, or 500, capture these before changing code:

- Request path and method
- Auth state (session or token)
- Required headers included or missing
- Request payload (sanitized)
- Response body
- Server logs for the request
- Any tracebacks

Rule:
- If you cannot capture the inputs and outputs, you are guessing.

---

## Rollback rules

### Code rollback

- Always keep commits small.
- Use a dedicated branch per change set.
- If a change breaks production, revert the change set, not individual lines.

### Database rollback

- Avoid destructive migrations unless unavoidable.
- If you add a required field, provide a default or a safe backfill plan.
- If you change constraints, document the rollback SQL and data repair steps.

---

## Documentation and change record template

Add a short note for each significant change under `docs/changes/`.

Use this template:

```markdown
# Change: <title>
Date: YYYY-MM-DD
Scope: <module or feature>

## Why
<short rationale>

## What changed
- <file>: <summary>
- <file>: <summary>

## How to test
- <commands>
- <manual steps>

## Rollback
- <git revert ...>
- <migration rollback notes if needed>
```

---

## Definition of done for any feature or bugfix

A change is done only when:

- Mapping step is completed for the touched layers.
- Tests exist and pass:
  - targeted tests
  - fast suite
- Request/response behavior is confirmed in at least one manual smoke test.
- Documentation note is added for non-trivial changes.
- Rollback plan is obvious and realistic.

---

## Quick triage map for common failures

### 401 Unauthorized

- Missing auth (session or token)
- Missing required header (laboratory context)
- Wrong client method (APIClient vs session client)
- Middleware expecting host/secure flags in tests

### 403 Forbidden

- User lacks `UserRole` membership for laboratory
- Role mismatch for transition or allowed list
- Permission class enforcing stricter checks than expected

### 400 Bad Request

- Payload key mismatch (`to` vs `target` vs `status`)
- Serializer required fields missing
- Wrong content type or `format="json"` missing in tests

### IntegrityError / NotNullViolation / UniqueViolation

- Fixture created object without required FK
- Unique field left blank or duplicated
- Model constraint changed but fixture not updated

### Workflow guard PermissionDenied

- Model blocks direct edits to workflow field
- Use workflow transition API or explicit bypass only for setup in tests

---

## Where to place this file

Save as:

- `docs/CHANGE_PROTOCOL.md`

Optionally add:

- `docs/changes/` directory for per-change notes



Paste this full content:

# NARO-LIMS Change Protocol (Engineering Guide)

This document defines the required approach for making changes to NARO-LIMS safely and predictably.
It exists to prevent regressions, reduce time lost in debugging, and make large changes easier to review.

## 1. Operating principles

1. No blind edits.
   Every change must start with mapping: where the behavior lives, how it is called, and how it is tested.

2. Small commits, scoped commits.
   Do not mix workflow, auth, UI, docs, and infra changes in one commit unless they are inseparable.

3. Tests are the contract.
   If you change behavior, you must change or add tests to encode that behavior.

4. Workflow state is protected.
   Direct writes to guarded workflow fields (example: Sample.status) must remain forbidden outside explicit bypass for migrations and test setup.

5. Always preserve rollback paths.
   Every change should have a clear rollback or revert strategy.

## 2. Pre-change mapping checklist (mandatory)

Before editing code, write down answers to these:

- What is the entry point?
  URL route, view, serializer, service function, model method, signal, or Celery task.

- What is the data model involved?
  Models and fields touched, especially constrained fields (NOT NULL, unique, FK).

- What is the permission surface?
  Who can call it, how authentication is enforced, and what lab membership rules apply.

- What tests cover it today?
  Identify existing test modules and fixtures that will break or need updates.

- What are the side effects?
  State transitions, audit logs, notifications, file writes, or background jobs.

If you cannot answer these, do not edit yet. Map first.

## 3. Files that must be mapped before changes

### A) Routing and public API surface
- `lims_core/urls.py`
- `lims_core/views.py`
- `lims_core/views_workflow_permissions.py`
- `lims_core/views_workflow_permission_aggregate.py`
- `lims_core/views_workflow_introspection.py`

Change rules:
- Any new endpoint must have a test that hits the endpoint (status code + payload).
- Any auth change must be validated with both authenticated and unauthenticated requests.

### B) Workflow rules and guardrails (high risk)
- `lims_core/workflows/rules.py`
- `lims_core/workflows/guards.py`
- `lims_core/workflows/__init__.py`
- `lims_core/services/workflow_bulk.py`

Change rules:
- Never weaken guards to “make tests pass”.
- Use `_workflow_bypass=True` only for test setup and controlled operations.
- If transitions change, update:
  - allowed transitions endpoint tests
  - transition endpoint tests
  - bulk transition tests
  - permission matrix tests

### C) Auth, permissions, membership model
- `naro_lims/settings.py` (DRF auth config, middleware assumptions)
- Membership model logic: `UserRole` and lab membership checks (wherever implemented)
- Test client auth harness: `lims_core/tests/conftest.py`

Change rules:
- Do not rely on “default session state” in tests.
- Ensure logout clears authentication without recursion or side effects.

### D) Database constraints and fixtures (frequent failure point)
- Model constraints: NOT NULL, unique fields, FK requirements
- Fixtures:
  - `lims_core/tests/conftest.py`
  - factory helpers inside conftest

Change rules:
- Fixtures must satisfy real constraints:
  - required FK must exist (example: Laboratory requires institute)
  - unique fields must be unique (example: Sample.sample_id must never be empty or repeated)
- Use idempotent patterns:
  - `get_or_create` for roles/memberships
  - generated unique IDs for sample ids, codes, etc

### E) Build and developer workflow
- `Makefile`
- `.github/workflows/*`
- `.github/CODEOWNERS`
- `.gitignore`
- `README.md`

Change rules:
- Only edit these when you are intentionally changing project governance or build behavior.
- Never let them drift as “incidental edits” during feature work.

## 4. Standard change workflow

### Step 1: Baseline verification
Run the smallest fast suite that proves the area is stable:

```bash
make test-fast


If tests are already failing, fix baseline first.
Do not add new features on top of failing baseline.

Step 2: Implement in the correct layer

Prefer this order:

Pure logic in services (easy to test)

Workflow rules and permission checks

Views/controllers

URL routing

UI templates (if any)

Step 3: Update or add tests

Required test types for workflow changes:

Allowed transitions by role

Permission matrix checks

Aggregate permissions for bulk operations

Transition endpoint behavior (403 vs 200)

Bulk transition success and partial failure behavior

Step 4: Run focused tests during development

Examples:

pytest -q lims_core/tests/test_workflow_allowed.py -q
pytest -q lims_core/tests/test_workflow_permission_matrix.py -q
pytest -q lims_core/tests/test_workflow_transitions.py -q
pytest -q lims_core/tests/test_bulk_workflow_transitions.py -q

Step 5: Final gate

Before committing:

make test-fast
git diff
git status

5. Guardrail rules (workflow and state)

Direct modification of guarded workflow fields must remain blocked.

Any test that needs to set a starting state must use explicit bypass:

Example pattern:

set status

save with _workflow_bypass=True

Do not introduce implicit bypasses or broaden bypass scope.

6. Commit and checkpoint rules
Recommended commit structure

Commit 1: workflow logic + endpoints + tests

Commit 2: docs only

Commit 3: build or CI only (if required)

Checkpoint commit message format

Checkpoint: <topic> (<test status>)

Example:
Checkpoint: workflow permissions and bulk transitions (36 tests green)

Tagging rule

Annotated tags for checkpoints.

Signed tags only if your signing key is loaded and working.

7. Definition of done for a change

A change is done only when:

make test-fast passes

new behavior is encoded in tests

fixtures satisfy DB constraints

commit is scoped and reviewable

checkpoint tag is created (optional but recommended for major changes)

8. Quick troubleshooting map
Symptom: 401 in tests

Check:

test client login logic in lims_core/tests/conftest.py

DRF auth settings in naro_lims/settings.py

endpoint permission classes in the workflow views

Symptom: IntegrityError on fixtures

Check:

required FK fields (example: institute_id on Laboratory)

unique fields (example: sample_id)

get_or_create vs create for repeated objects

Symptom: PermissionDenied on status save

This is expected.
Use _workflow_bypass=True for test setup only.
Real transitions must go through transition APIs.
