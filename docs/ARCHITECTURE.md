# NARO-LIMS Architecture

## Overview

NARO-LIMS is a Django-based Laboratory Information Management System designed for regulated research environments.  
The architecture emphasizes correctness, traceability, and governance over convenience.

---

## High-Level Components

Client (UI / API Consumer)
|
v
Django REST API
|
v
Workflow & Guardrails Layer
|
v
Persistence & Audit Layer
---

## Core Modules

### `lims_core`
- Domain models
- Business logic
- Workflow enforcement
- Guardrails
- Audit logging

### `workflows`
- State machines
- Transition rules
- Role enforcement
- SLA monitoring
- Metrics and timelines

### `permissions`
- Role resolution
- Laboratory scoping
- Object-level access control

---

## Workflow Execution Path

1. Client submits request
2. Permissions validated
3. Guardrails evaluated
4. Workflow transition validated
5. State updated atomically
6. Audit log written
7. SLA evaluated

At no point can the client bypass this sequence.

---

## Guardrails Philosophy

Guardrails are:
- Explicit
- Test-enforced
- Non-negotiable

They prevent:
- Silent corruption
- Unauthorized mutation
- Invalid workflow states
- Regression during development

---

## Audit & Traceability

All state-changing operations produce:
- Audit records
- Workflow transition records
- Optional SLA alerts

Nothing critical is silently deleted.

---

## Extensibility

The system is designed to allow:
- New workflow types
- Additional roles
- New SLA rules
- Additional reporting layers

Without weakening core guarantees.

---

For workflow-specific diagrams, see:
`docs/ARCHITECTURE_WORKFLOWS.md`

