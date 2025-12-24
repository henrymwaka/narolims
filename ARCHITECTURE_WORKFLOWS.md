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
