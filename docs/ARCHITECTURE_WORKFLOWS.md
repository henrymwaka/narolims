# LIMS Workflow Architecture Contract

## Status
**LOCKED**  
Any change to this document requires architectural review.

---

## Purpose

This document defines the **authoritative workflow execution model** for
all workflow-controlled entities in the LIMS system (e.g. Sample, Experiment).

All status transitions MUST flow through the workflow engine.
Any deviation is considered a defect.

---

## Core Principles

1. **Single Source of Truth**
   - All workflow rules live in `lims_core/workflows/`
   - No model, serializer, or view may re-implement workflow logic

2. **Hard Terminal States**
   - Terminal states are immutable
   - No API, admin action, or script may resurrect them

3. **Role-Enforced Transitions**
   - Role checks are enforced centrally
   - UI-level checks are advisory only

4. **Immutable Audit Trail**
   - Every transition is logged
   - Timeline records are append-only

---

## Authoritative Execution Path

### Workflow Engine
lims_core/workflows/executor.py


The function:

```python
execute_transition(...)


is the only permitted mechanism for changing workflow-controlled fields.

Responsibilities:

terminal-state lock

transition legality

role enforcement

atomic persistence

audit logging

API Contract (LOCKED)
Read Current State
GET /lims/workflows/{kind}/{id}/


Returns:

{
  "id": 5,
  "kind": "sample",
  "status": "QC_PENDING"
}

Get Allowed Transitions (Role-Aware)
GET /lims/workflows/{kind}/{id}/allowed/


Returns only transitions the current user is allowed to perform.

Execute Transition (AUTHORITATIVE)
PATCH /lims/workflows/{kind}/{id}/


Payload:

{ "status": "QC_PASSED" }


Rules:

Delegates to execute_transition

Returns:

200 on success

403 on role/access violation

409 on terminal or illegal transition

Read Workflow Timeline
GET /lims/workflows/{kind}/{id}/timeline/


Returns immutable audit history.

Forbidden Patterns (DO NOT DO)

The following are explicitly prohibited:

Updating status via:

Model .save()

Serializers

Bulk updates

Django Admin

Re-implementing workflow logic in:

Views

Serializers

Forms

Allowing UI or clients to bypass the workflow API

Violations must be fixed immediately.

Testing Guarantees

The following test suites must always pass:

test_terminal_lock.py

test_workflow_transitions.py

test_workflow_allowed.py

test_write_guardrails.py

CI must fail if any workflow test fails.

Future Extensions

Permitted extensions:

Admin override endpoint (superuser only, audited)

Additional workflow kinds

UI components consuming the same API

All extensions must reuse the existing engine.

Final Note

This architecture intentionally favors safety over convenience.

Breaking this contract will corrupt auditability and invalidate results.


Save and exit.

---

## 3. Add a guard comment in code (important)

Add this **one-line comment** at the top of these files:

### `lims_core/workflows/executor.py`
```python
# ARCHITECTURE CONTRACT: This is the only legal workflow mutation path.

lims_core/views_workflow_runtime.py
# ARCHITECTURE CONTRACT: This view must delegate to execute_transition.


This stops future “small refactors” from destroying guarantees.



# NARO-LIMS Workflow Architecture Contract

## Purpose
This document is the authoritative contract for the workflow system used by Samples and Experiments.
It defines the execution path, security model, API contracts, and UI embedding rules.

The workflow system is designed with one core principle:

The executor is the only place where workflow transitions are enforced and persisted.

All views, APIs, and UI components must route transitions through the executor.

---

## Components and Responsibilities

### 1. Workflow rules
Location:
- `lims_core/workflows/rules.py` (or equivalent module exporting transition rules)
- `lims_core/workflows/__init__.py` exports:
  - `validate_transition(kind, old, new)`
  - `allowed_next_states(kind, current)`
  - `required_roles(kind, current, target)`

Responsibilities:
- Define the status universe per kind (sample, experiment)
- Define allowed transitions (state machine)
- Define terminal lock behavior via `allowed_next_states` returning empty set for terminal states
- Define role requirements per edge via `required_roles`

No database writes occur here.

---

### 2. Workflow executor (authoritative)
Location:
- `lims_core/workflows/executor.py`

Responsibilities:
- Enforce terminal lock
- Validate transition legality via rules
- Enforce role permissions (lab scoped)
- Persist state change (safe update)
- Write workflow timeline record

All state transitions must go through:
- `execute_transition(instance, kind, new_status, user)`

No other code path may directly update status unless explicitly exempted for migrations.

---

### 3. Runtime workflow view (authoritative single object endpoints)
Location:
- `lims_core/views_workflow_runtime.py`

Endpoints:
- `GET  /lims/workflows/<kind>/<pk>/`
- `PATCH /lims/workflows/<kind>/<pk>/`
- `GET  /lims/workflows/<kind>/<pk>/timeline/`

Responsibilities:
- Resolve object by kind and pk
- Enforce laboratory access control (membership or superuser)
- Accept a requested target status from payload
- Perform UX level role visibility check
- Call the executor for all transitions
- Convert terminal lock and illegal transitions into HTTP 409

This view is the authoritative path for browser widget transitions.

---

### 4. Role aware workflow API endpoints
Location:
- `lims_core/views_workflow_api.py` (or similar)

Endpoints:
- `GET  /lims/workflows/<kind>/<pk>/allowed/`
- `POST /lims/workflows/<kind>/<pk>/transition/` (optional parallel route)

Responsibilities:
- Provide a filtered list of allowed transitions visible to the current user
- Optionally provide a role aware transition route that still calls the executor

Note:
The widget currently uses:
- `GET /allowed/`
- `PATCH /<kind>/<pk>/`

---

### 5. Bulk workflow transitions
Location:
- `lims_core/views_workflow_bulk.py`

Endpoint:
- `POST /lims/workflows/<kind>/bulk/`

Responsibilities:
- Accept a list of object ids and target status
- Execute transitions via the executor in a controlled loop or transaction strategy
- Return per item success or failure

All writes still flow through the executor.

---

### 6. Workflow timeline model
Location:
- `lims_core/models/...` (WorkflowTransition model)

Expected fields (conceptual contract):
- kind (sample, experiment)
- object_id (pk of content)
- from_status
- to_status
- performed_by (User)
- laboratory (Laboratory)
- created_at (timestamp)

The executor writes exactly one record per successful transition.

---

## Security Model

### 1. Laboratory access control
For models that have a `laboratory` field:
- Superusers always pass
- Non superusers must have `UserRole(user, laboratory)` membership

This check is enforced at:
- Runtime views
- Timeline view
- Allowed transitions view

If access fails:
- HTTP 403 is returned

---

### 2. Role enforcement
A workflow edge may require roles.
The rule is defined by:
- `required_roles(kind, current, target)` returning a set of role codes

Enforcement:
- The executor enforces roles definitively
- Runtime view may do an early UX level block before calling executor

If role check fails:
- HTTP 403 is returned with a clear message

---

### 3. Terminal lock
Terminal states are states with no outgoing transitions.
Mechanism:
- `allowed_next_states(kind, current)` returns empty for terminal

Enforcement:
- Executor raises a validation error for any transition attempt from terminal
- Runtime view converts this into:
  - HTTP 409 Conflict

This ensures tests can assert terminal lock behavior without relying on illegal transition semantics.

---

## API Contracts

### 1. Read workflow state
`GET /lims/workflows/<kind>/<pk>/`

Response:
```json
{
  "id": 123,
  "kind": "sample",
  "status": "IN_PROCESS"
}
Error:

404 if not found

403 if no lab access

2. Get allowed transitions

GET /lims/workflows/<kind>/<pk>/allowed/

Response:

{
  "id": 123,
  "kind": "sample",
  "current": "IN_PROCESS",
  "allowed": ["QC_PENDING", "REJECTED"]
}


Allowed is role filtered for the current user.

Error:

404 if not found

403 if no lab access

3. Apply transition

PATCH /lims/workflows/<kind>/<pk>/

Request:

{ "status": "QC_PENDING" }


Success:

{
  "id": 123,
  "kind": "sample",
  "from": "IN_PROCESS",
  "to": "QC_PENDING",
  "status": "QC_PENDING"
}


Errors:

403 if user lacks role or lab access

409 if terminal locked or invalid transition

404 if not found

4. Timeline

GET /lims/workflows/<kind>/<pk>/timeline/

Response:

{
  "id": 123,
  "kind": "sample",
  "timeline": [
    { "at": "...", "user": "qa", "from": "IN_PROCESS", "to": "QC_PENDING" }
  ]
}

UI Embedding Contract

Workflow widget template:

lims_core/templates/lims_core/workflow_widget.html

It requires context:

workflow_kind

workflow_object_id

It expects static assets:

lims_core/static/lims_core/css/workflows.css

The widget calls:

GET /lims/workflows/<kind>/<id>/

GET /lims/workflows/<kind>/<id>/allowed/

GET /lims/workflows/<kind>/<id>/timeline/

PATCH /lims/workflows/<kind>/<id>/

Diagrams
High level flow
flowchart TD
  UI[Browser widget] -->|GET state| RT[WorkflowRuntimeView]
  UI -->|GET allowed| AL[WorkflowAllowedView]
  UI -->|PATCH status| RT
  RT -->|execute_transition| EX[Executor]
  AL -->|rules only| RL[Workflow rules]
  EX -->|validate + roles + lock| RL
  EX -->|update status| DB[(DB)]
  EX -->|write timeline| DB
  UI -->|GET timeline| TL[WorkflowTimelineView]
  TL --> DB

Transition enforcement boundary
flowchart LR
  subgraph NonAuthoritative
    A[UI widget]
    B[Allowed transitions API]
  end

  subgraph Authoritative
    C[Runtime PATCH]
    D[Executor]
    E[DB writes]
  end

  A --> C
  B --> A
  C --> D --> E

Development Guardrails
Do

Always call execute_transition for workflow state changes

Keep the rules pure and deterministic

Keep UI unaware of role logic except for visibility hints

Return 409 for terminal lock and invalid transitions

Do not

Do not change status in CRUD ViewSets for workflow managed objects

Do not create alternate transition logic in views

Do not bypass lab access checks in workflow endpoints

Verification

Run:

pytest

Expected:

All tests pass

Spot check in browser:

Open sample detail page that includes the widget

Confirm status updates and timeline updates

Confirm terminal states disable actions
