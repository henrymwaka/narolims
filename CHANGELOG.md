# Changelog

All notable changes to **NARO-LIMS** are documented in this file.

This project follows:
- Semantic Versioning (SemVer)
- Explicit release tagging
- Audit-first change documentation

Dates are in ISO format (YYYY-MM-DD).

---

## [v0.6.0-guardrails] – 2025-12-25

### Summary

This release establishes **hard, enforceable guardrails** across workflows, permissions, and write paths.

It is the first release where:
- Business rules are treated as contracts
- Violations fail explicitly
- Guardrails are enforced in tests, CI, and pre-commit hooks

This version is considered a **foundational stability milestone**.

---

### Added

#### Workflow Enforcement
- Centralized workflow engine for `Sample` and `Experiment`
- Explicit state machines with allowed transitions
- Terminal state locking
- Role-aware transition enforcement
- Workflow transition timeline persistence
- SLA monitoring hooks per workflow state

#### Guardrails
- Immutable field enforcement for:
  - Project laboratory
  - Project creator
  - Sample project
  - Sample laboratory
  - Staff institute
  - Staff laboratory
- Guardrails implemented at:
  - Serializer level
  - View level
  - Permission level
- Dedicated guardrail test suite

#### Documentation
- `GUARDRAILS.md` defining the system guardrails contract
- `OPERATIONS.md` covering production operations
- Guardrail-focused release tagging

#### Tooling
- `Makefile` target for guardrail validation
- Pre-commit hook enforcing guardrail tests
- CI workflow enforcing guardrails on push and PR

---

### Changed

#### API Behavior
- Invalid workflow transitions now return structured validation errors
- Permission violations return explicit `403 Forbidden`
- Server-controlled fields fail fast when mutated

#### Write Semantics
- Write paths now explicitly differentiate:
  - Validation errors (`400`)
  - Permission violations (`403`)
- Silent mutation prevention removed

#### Internal Architecture
- Workflow logic centralized under `lims_core.workflows`
- Transition execution moved to a single authoritative path
- SLA logic decoupled from views

---

### Fixed

- Silent status mutations bypassing business rules
- Inconsistent permission handling across models
- Serializer-level immutability gaps
- Test instability due to implicit state assumptions

---

### Removed

- Implicit workflow assumptions
- Ad-hoc status updates outside workflow engine
- Silent ignores of invalid transitions

---

### Security

- Prevented unauthorized mutation of institutional ownership
- Enforced role-based access to sensitive transitions
- Ensured audit trail completeness for workflow changes

---

### Migration Notes

No schema-breaking migrations.

Existing data remains valid, but:
- Invalid future transitions are now blocked
- Unauthorized updates will fail explicitly

Operators must ensure users have correct roles assigned.

---

### Operational Impact

- Guardrail tests must pass before deployment
- Pre-commit hooks enforce policy locally
- CI enforces policy remotely

This release increases strictness by design.

---

## [v0.5.x] – Pre-Guardrails Series

### Summary

Early functional releases focusing on:
- Core CRUD operations
- Initial workflow concepts
- Laboratory scoping
- Audit logging

These versions did not enforce guardrails consistently and are **not recommended for production** without backported fixes.

---

## Versioning Policy

- **MAJOR**: Breaking data model or API contracts
- **MINOR**: New features with backward compatibility
- **PATCH / TAGGED**: Enforcement, stability, and policy hardening

Guardrail releases may include tagged suffixes (e.g. `-guardrails`) to signal policy milestones.

---

## Maintenance Policy

- Only tagged releases may be deployed to production
- Hotfixes must reference a tagged base
- Every release must update this changelog

If a change is not documented here, it is not considered released.
