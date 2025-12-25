# NARO-LIMS (narolims)

NARO-LIMS is a laboratory information management system designed for structured, auditable, and role-aware laboratory operations in agricultural and bioscience research environments.

The system is built to support multi-laboratory institutions, enforce workflow correctness, and prevent accidental or unauthorized data mutation through explicit guardrails enforced at the API, workflow, and permission layers.

This repository contains the backend implementation of NARO-LIMS.

---

## Core Design Principles

NARO-LIMS is intentionally opinionated and is built around the following principles:

1. Workflow correctness is enforced server-side.
2. Critical fields are immutable after creation.
3. All write operations are role-aware and laboratory-scoped.
4. Tests define contractual behavior, not optional checks.
5. CI and pre-commit hooks enforce correctness before merge.

---

## Key Features

### 1. Workflow Engine with Guardrails

NARO-LIMS implements explicit state-machine workflows for core entities such as:

- Samples
- Experiments

Each workflow defines:
- Valid states
- Allowed transitions
- Terminal states
- Transition legality rules

Invalid transitions are rejected deterministically with validation errors.

Examples:

REGISTERED → QC_PASSED   invalid  
REGISTERED → IN_PROCESS valid  

Workflow logic lives in:


---

### 2. Immutable Field Protection

Certain fields are server-controlled and cannot be modified after object creation.

Examples include:
- Project.laboratory
- Project.created_by
- Sample.project
- StaffMember.institute
- StaffMember.laboratory

Violations are blocked with:
- 400 Bad Request for validation-level immutability
- 403 Forbidden for permission-level enforcement

This behavior is enforced both at serializer and view levels.

---

### 3. Role-Aware Access Control

All write operations are restricted by:
- Active laboratory context
- User role within that laboratory

Laboratory resolution supports:
- ?lab=<id> query parameter
- X-Laboratory request header
- Automatic single-laboratory resolution

Permissions are enforced consistently across:
- Viewsets
- Object-level access
- Workflow transitions

---

### 4. Auditability and Traceability

The system is designed for traceability in regulated environments.

It includes:
- Workflow transition tracking
- SLA monitoring hooks
- Audit log infrastructure

This ensures accountability and reproducibility of actions.

---

## Guardrails Contract

This repository treats tests as a contract.

Two test suites define non-negotiable system behavior:

- lims_core/tests/test_status_workflows.py
- lims_core/tests/test_write_guardrails.py

These tests guarantee that:
- Invalid workflow transitions are impossible
- Immutable fields cannot be modified
- Permission boundaries are respected

The contract is documented in:

GUARDRAILS.md


Any change that breaks these tests is considered a breaking change.

---

## Development Setup

### Requirements

- Python 3.10 or later
- PostgreSQL recommended for production
- Python virtual environment

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txtRunning Tests
Guardrail Tests Only
make guardrails

Full Test Suite
python manage.py test

Pre-Commit Enforcement

This repository includes a pre-commit hook that blocks commits if guardrail tests fail.

Location:

.git/hooks/pre-commit


What it enforces:

Workflow tests must pass

Guardrail tests must pass

Environment must be correctly configured

Broken logic is prevented from entering version control.

Continuous Integration

GitHub Actions CI is configured under:

.github/workflows/ci.yml


CI enforces:

Clean environment test execution

Guardrail compliance

Reproducibility independent of developer machines

Versioning and Releases

The project uses semantic versioning with explicit tags for behavioral milestones.

Example:

v0.6.0-guardrails


Tags represent stable contractual states of the system.

Repository Structure
narolims/
├── lims_core/
│   ├── workflows/
│   ├── serializers.py
│   ├── views.py
│   └── tests/
├── naro_lims/
├── .github/
├── Makefile
├── GUARDRAILS.md
└── manage.py

Intended Audience

NARO-LIMS is designed for:

National research institutes

Agricultural biotechnology laboratories

Multi-laboratory research facilities

Environments requiring strict traceability and role separation

It is not intended to be a lightweight CRUD system.

Project Status

Active development.

Current focus areas include:

Workflow hardening

UI integration readiness

SLA enforcement

Production deployment patterns

Maintainer

Developed and maintained by Henry Mwaka
GitHub: https://github.com/henrymwaka
