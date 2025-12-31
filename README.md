# LIMS Platform (narolims)
A workflow-enforced, configurable Laboratory Information Management System for research and testing laboratories.

This project is a laboratory information management system designed for laboratories that require strong traceability, controlled workflows, and clear role boundaries. It targets multi-laboratory institutions and regulated or audit-sensitive environments where record integrity must be preserved over time.

This repository contains the backend implementation.

---

## What this system is
This platform provides a sample-centric system of record where:
- samples are registered with durable identifiers
- sample lineage (parent and derived samples) remains explicit
- lifecycle states are enforced server-side
- critical records cannot be silently mutated
- roles and laboratory context determine what a user can do
- decisions and transitions are captured in a way that supports audit and reproducibility

The design favors correctness and traceability over ad hoc editing.

---

## Governance and controlled evolution
This repository is governed by an authoritative system charter:

- `NARO_LIMS_SYSTEM_CHARTER.md`

The charter defines non-negotiable system principles and change boundaries. It exists to prevent long-term drift into a permissive CRUD tracker that cannot support real laboratory accountability.

For lab-to-lab adaptability without hardcoding discipline behavior, the platform uses a configurable approach described in:

- `NARO_LIMS_LAB_PROFILE_FRAMEWORK.md`

This framework defines how laboratory profiles, analysis contexts, and metadata schemas shape what the system requires at each phase of work.

---

## The problem it solves
Laboratory records often fragment across spreadsheets, notebooks, emails, and personal databases. That fragmentation creates predictable failures:
- sample lineage becomes unclear
- repeats and deviations are hard to justify
- handovers break continuity
- audit trails are incomplete
- cross-team work becomes reconciliation work

This platform addresses those issues by providing a single, traceable backbone where the sample is the unit of truth and every meaningful action remains attributable.

---

## Core design philosophy
### 1) Sample-centric truth
The sample is the primary unit of truth. Assays, results, QC decisions, attachments, and reports are tied to the sample or derived samples, preserving lineage.

### 2) Canonical lifecycle enforcement
Key objects move through defined lifecycle states. State changes are controlled events and illegal transitions are rejected server-side.

### 3) Guardrails before convenience
Silent mutation is a major integrity failure mode in laboratory systems. The platform prevents casual edits of critical records and favors explicit, reviewable change.

### 4) Multi-lab by design
Users operate within a laboratory context. Access and write operations are laboratory-scoped and role-aware, supporting separation of duties.

### 5) Incremental extensibility
New laboratory disciplines and workflows are expected. The platform grows through configuration and versioned templates rather than repeated core rewrites.

---

## How it works in practice (end-to-end)
A typical workflow is represented consistently, while still allowing lab-specific variation through profiles and schemas.

1. **Receive and register**
   - Create a sample with durable identity and intake metadata.

2. **Prepare and derive**
   - Sub-sampling, extraction, plating, or other preparation steps can produce derived samples with explicit parent-child lineage.

3. **Execute analysis**
   - Work is performed as controlled activities (runs, batches, sessions depending on domain).
   - Outputs are recorded as results tied to the sample or derived sample.

4. **QC evaluation and decision**
   - QC is treated as a decision process.
   - Acceptance, repeats, deviations, and justification are captured explicitly.

5. **Review and release**
   - Where required, technical review and authorization occur before release.
   - This supports role separation and prevents unreviewed outputs from becoming institutional truth.

6. **Archive or close**
   - Completed work is retained in a way that preserves interpretability and traceability.

---

## Configurability: laboratory profiles, contexts, and metadata schemas
The platform is designed to support many laboratory disciplines without embedding discipline logic into core code.

It does this using versioned configuration concepts:

### Laboratory profiles
A Laboratory Profile represents how a specific lab operates, including which workflows apply, what roles exist, and what policies must be enforced.

### Analysis contexts
An Analysis Context represents a structured domain area within a lab, for example:
- soil fertility testing
- plant disease diagnostics
- nematode or pest identification
- molecular screening workflows
- food safety testing

### Metadata schemas
Metadata Schemas define the required fields and validation rules for a given object type under:
- a specific laboratory profile
- an optional analysis context
- sometimes a lifecycle phase or step

This ensures that:
- requirements are explicit, versioned, and reviewable
- onboarding a new lab does not require rewriting core logic
- schema evolution becomes a controlled change, not a casual UI form edit

---

## Workflow engine and record integrity
A central feature of the platform is server-side lifecycle enforcement.

- Lifecycles exist to represent real constraints in lab operations.
- Transitions are validated deterministically.
- Transition events are designed to be attributable and auditable.
- Terminal states can be protected boundaries, not labels.

This prevents “status drift”, where records claim outcomes that were never achieved through valid steps.

---

## Roles, permissions, and lab scoping
This platform is designed for multi-lab institutions where access boundaries must be meaningful.

Key expectations:
- users operate inside an active laboratory context
- write operations are restricted by role and lab scope
- object-level access should not leak across labs
- actions that change record meaning are explicitly permissioned

---

## Quality gates: tests as contract
This repository treats tests as a contract, not optional checks.

Two test suites define non-negotiable behavior:
- `lims_core/tests/test_status_workflows.py`
- `lims_core/tests/test_write_guardrails.py`

These tests guarantee:
- invalid workflow transitions are impossible
- immutable fields cannot be modified
- permission boundaries are respected

If a change breaks these tests, it is treated as a breaking change.

---

## Development setup
### Requirements
- Python 3.10+
- PostgreSQL recommended for production deployments
- Python virtual environment

### Install
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
