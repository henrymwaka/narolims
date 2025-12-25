# Release Notes

## v0.6.0 – Guardrails & Workflow Enforcement

### Release Date
December 2025

---

## Highlights

This release introduces **hard guardrails** for workflow integrity, immutability, and permission enforcement across the LIMS platform.

---

## New Features

### Workflow Guardrails
- Authoritative server-side workflow execution
- Explicit state machines for Sample and Experiment lifecycles
- Validation of legal and illegal transitions
- Role-aware transition enforcement

### Write Guardrails
- Immutable fields enforced post-creation
- Distinct handling of validation errors (400) vs permission violations (403)
- Protection of:
  - Laboratory assignment
  - Institute assignment
  - Project ownership
  - Staff affiliations

### SLA & Alert Handling
- Automatic resolution of stale SLA alerts
- Accurate duration computation
- Non-destructive resolution strategy

---

## Developer Experience

- `make guardrails` command added
- Pre-commit hook enforcing guardrail tests
- CI workflow enforcing the same rules remotely

---

## Breaking Changes

- Direct mutation of protected fields is no longer possible
- Client-side workflow manipulation is ignored or rejected
- Permission escalation attempts now fail explicitly

---

## Tags

This release is tagged as:

```text
v0.6.0-guardrails
Upgrade Notes

Run migrations

Re-run tests

Ensure client applications respect server-controlled fields

This release significantly hardens the system against misuse and regression.
