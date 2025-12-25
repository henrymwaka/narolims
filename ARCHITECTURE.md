# NARO-LIMS Architecture

## Purpose

This document describes the **system architecture** of NARO-LIMS, with emphasis on:

- Layered design
- Workflow execution model
- Guardrail enforcement
- Responsibility boundaries between components

The architecture is intentionally conservative, explicit, and enforcement-driven to support institutional research operations, auditability, and long-term maintainability.

---

## High-Level Architecture Overview

NARO-LIMS follows a **layered architecture** with strict separation of concerns:

Client (Web / API Consumer)
↓
Django REST Framework (Views)
↓
Validation & Guardrails
↓
Workflow Engine (Authoritative)
↓
Domain Models (ORM)
↓
Database

Each layer has **clearly defined responsibilities** and **limited authority**.

---

## Core Architectural Principles

1. **Single Source of Truth**
   - Workflow rules live in one place
   - Guardrails are not duplicated or implied

2. **Fail Closed**
   - Invalid actions are rejected explicitly
   - No silent corrections or implicit coercion

3. **Defense in Depth**
   - Validation at serializer, view, and workflow layers
   - Permissions enforced both globally and per object

4. **Auditability by Design**
   - All critical state changes are recorded
   - Mutations are intentional and attributable

---

## System Layers in Detail

---

### 1. API Layer (Views)

**Location:** `lims_core/views.py`, `views_workflow_*`

**Responsibilities:**
- Accept and parse requests
- Enforce authentication
- Apply request-level guardrails
- Route state changes to the workflow engine
- Return explicit HTTP responses

**Explicitly NOT responsible for:**
- Business rule definition
- Workflow legality decisions
- Role interpretation logic

The API layer acts as a **controlled gateway**, not a decision maker.

---

### 2. Serializer Layer

**Location:** `lims_core/serializers.py`

**Responsibilities:**
- Field validation
- Data shape enforcement
- Immutable field detection
- Controlled exposure of model fields

**Key pattern:**
- Immutable fields raise `400 Bad Request`
- Serializer validation never mutates state

Serializers enforce **data integrity**, not **process logic**.

---

### 3. Guardrail Layer

**Locations:**
- `ImmutableFieldsMixin`
- View-level `_deny_if_payload_has(...)`
- Permission checks
- Workflow validation hooks

**Responsibilities:**
- Prevent illegal mutations
- Ensure server-controlled fields remain authoritative
- Fail early and explicitly

Guardrails exist at multiple layers to prevent bypasses.

---

### 4. Workflow Engine (Authoritative Layer)

**Location:** `lims_core/workflows/`

This is the **heart of the system**.

#### Components

| File | Responsibility |
|----|----|
| `rules.py` | Defines valid states and transitions |
| `executor.py` | Executes transitions atomically |
| `guards.py` | Terminal state and safety checks |
| `sla_*` | SLA monitoring hooks |
| `metrics.py` | Time-in-state tracking |

#### Responsibilities

- Validate transition legality
- Enforce terminal state locks
- Enforce role-based transition permissions
- Persist transition history
- Trigger SLA monitoring

**No other part of the system is allowed to change workflow state directly.**

---

### 5. Permission System

**Location:** `lims_core/permissions.py`

**Key concepts:**
- Laboratory-scoped access
- Role-based write permissions
- Elevated privileges for administrative roles

Permissions are enforced at:
- Request level
- Object level
- Workflow execution level

This ensures consistent behavior regardless of entry point.

---

### 6. Domain Models

**Location:** `lims_core/models.py`

**Responsibilities:**
- Represent persistent domain entities
- Store current state
- Maintain relational integrity

**Important constraint:**
Models do **not** encode workflow logic.

All workflow decisions occur above the model layer.

---

### 7. Audit & Traceability

**Components:**
- `AuditLog`
- `WorkflowTransition`
- `WorkflowAlert`

**Capabilities:**
- Track who changed what and when
- Reconstruct state history
- Support regulatory and operational audits

Audit records are **append-only**.

---

## Workflow Execution Path (Example)

**Sample status change:**

PATCH /lims/samples/{id}/ { "status": "IN_PROCESS" }
↓
ViewSet.perform_update
↓
validate_transition("sample", current, target)
↓
Workflow executor
↓
Permission checks
↓
Atomic state update
↓
WorkflowTransition record
↓
SLA hooks
Any failure aborts the operation with an explicit error.

---

## Error Semantics

| Condition | HTTP Status |
|---------|------------|
| Invalid transition | 400 |
| Immutable field mutation | 400 |
| Missing role | 403 |
| Missing lab context | 403 |
| Unauthenticated | 401 |

Errors are **intentional signals**, not user experience artifacts.

---

## Why This Architecture Matters

This design ensures:

- Predictable behavior
- Enforceable governance
- Safe multi-user operations
- Long-term maintainability
- Confidence during audits

It explicitly avoids:
- Implicit magic
- Hidden side effects
- Distributed business logic
- Permission ambiguity

---

## Future Extensions

The architecture supports:

- Additional workflow kinds
- Policy-driven transitions
- Advanced SLA enforcement
- External integrations
- Event-driven automation

All without breaking existing guarantees.

---

## Architectural Contract

Any change that:
- Bypasses the workflow engine
- Mutates protected fields
- Weakens guardrails
- Introduces silent behavior

**Violates the architectural contract** and must not be merged.

---

## Status

This architecture is **active and enforced** as of:

v0.6.0-guardrails


All future development builds upon these guarantees.
