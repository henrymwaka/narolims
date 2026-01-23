# PHASE 2: Project Intake Coherence and Project Workspace

Document: PHASE_2_PROJECT_INTAKE.md  
Status: Authoritative (implementation guide)  
Scope: NARO-LIMS core intake and project organization  
Owner: LIMS Core  
Last updated: 2026-01-21

## 1. Purpose

This phase establishes a single coherent intake model so that:
- Projects, batches, and samples are created in a predictable way.
- UI entry points do not duplicate or contradict each other.
- Samples can be organized under project objectives, activities, and tasks.
- Users can collaborate inside a project with clear membership and permissions.
- Future labs (soils, tissue culture, diagnostics, food safety) can adopt the same patterns without hardcoding.

The goal is to move from “screens that work” to “a system that cannot drift.”

---

## 2. Current pain points observed

### 2.1 Competing sample creation paths
There are at least two paths that create samples:
- Wizard placeholder creation in `lims_core/wizard/services.py`
- Batch bulk registration in `lims_core/views_ui.py`

They diverge in:
- How sample IDs are generated
- What status is set
- Whether a batch exists at all
- Where the user is guided next

### 2.2 Batch creation is not canonical
`batch_create()` currently accepts a user-posted laboratory, but the batch is tied to a project.
This enables mismatches and later validation errors.

### 2.3 Project has no workspace model
Projects exist, but the platform lacks a consistent concept of:
- project members
- project objectives
- activities, tasks, milestones
- assignment and responsibility

Experiments exist and already support `objective` and `narrative`. That is a strong foundation but needs to be integrated deliberately, not left as a side feature.

### 2.4 Wizard Step 2 can fail silently or render confusingly
When Step 2 becomes a catch-all “Apply draft” step, any misalignment in the draft payload, permissions, or creation logic yields a confusing experience.

---

## 3. Non negotiable system invariants

These rules define coherence. All UI and API paths must respect them.

### 3.1 Ownership and containment
1. A `Sample` must belong to exactly one `Project`.
2. A `SampleBatch` is the canonical container for creating samples in bulk.
3. A `SampleBatch` may optionally represent an intake event or shipment, but it must still be tied to a project.

### 3.2 Lab consistency
4. `Project.laboratory_id` is the source of truth for project scope.
5. If `SampleBatch.project_id` is set, then `SampleBatch.laboratory_id` must equal `Project.laboratory_id`.
6. If `Sample.batch_id` is set, then `Sample.laboratory_id` must equal `SampleBatch.laboratory_id`.

### 3.3 Scope enforcement
7. Non staff users can only operate within labs assigned via `UserRole`.
8. Project membership expands what a user can do inside a project, but never expands lab scope.

### 3.4 One service layer
9. All intake creation routes must call a shared service, not replicate object creation logic in views.
10. Sample IDs and default statuses are assigned by models and services, not by templates or ad hoc view logic.

---

## 4. Target canonical flow

This becomes the standard workflow across all laboratories.

### 4.1 Canonical intake flow (default)
1. Create Project
2. Create Intake Batch under the Project
3. Create Samples under the Batch (bulk or individual)
4. Optionally assign samples to objectives (Experiments) and tasks

### 4.2 Allowed variants
- Variant A: Create Project only, with zero samples initially.
- Variant B: Create Project and automatically create one intake batch, then create N placeholder samples.
- Variant C: Create Project, create intake batch, import sample list from CSV.

All variants still obey:
Project first, batch second, samples last.

---

## 5. Data model alignment and extensions

### 5.1 Existing models (current state)
- `Project`: container for work and samples
- `SampleBatch`: grouping of samples, optionally tied to a project
- `Sample`: work unit, tied to project, optional batch
- `Experiment`: already has objective and narrative, tied to project

### 5.2 Project objectives and tasks

#### Option 1 (recommended, minimal schema changes)
Use `Experiment` as the “objective container” and extend its UI semantics:
- `Experiment.objective` becomes a first class field in project planning
- `Experiment.name` becomes the visible objective or activity name
- `Experiment.narrative` holds description, methods, or justification
- samples can be linked to an experiment via `Sample.experiment`

Advantages:
- No new models required
- Already integrated with metadata schema freezing
- Aligns with scientific reality: objectives drive experiments, experiments produce samples and results

Tradeoff:
- The word “Experiment” may not fit all labs. This can be solved at UI level by labeling it “Objective” or “Activity” per lab profile or config pack.

#### Option 2 (later, if needed)
Introduce `ProjectObjective`, `ProjectTask`, and `Milestone` models.
Only do this after Option 1 is stable, to avoid unnecessary complexity.

### 5.3 Project membership

Add a new model:

**ProjectMember**
- project (FK)
- user (FK)
- role (text, project-scoped role like “Project Lead”, “Analyst”, “Reviewer”)
- is_active
- added_by, added_at

Rules:
- Membership grants project access within the same laboratory.
- Lab scope still controls which projects are visible by default.
- Staff can manage membership globally.

---

## 6. UI coherence contract

This section defines what each UI surface is allowed to do.

### 6.1 Wizard
Wizard is only responsible for:
- collecting project basics
- optionally setting up initial intake batch and placeholders
- applying through the canonical intake service

Wizard must not:
- invent a separate sample ID format
- set nonstandard sample statuses
- bypass batch creation if sample placeholders are requested

### 6.2 Project pages
The Project workspace should provide:
- project summary
- members
- objectives (using Experiment UI semantics)
- intake batches list
- sample list filtered by batch, objective, or status
- action buttons to create batch, bulk register, import CSV

### 6.3 Batch pages
Batch detail should be the canonical entry point for:
- bulk sample registration
- sample listing for that batch
- metadata completion view per sample (later)

### 6.4 Samples pages
Sample pages are for:
- tracking workflow and metadata completion
- linking sample to experiment and batch
- audit history

---

## 7. Service layer design

### 7.1 Single entry service
Create or use a single service as the source of truth:

`lims_core/services/intake.py`
- `create_project_with_intake_batch(...)`
- `create_intake_batch_for_project(...)`
- `bulk_create_samples_for_batch(...)`
- `import_samples_csv(...)` (later)

All existing creation code must route here:
- `wizard/services.py`
- `views_ui.py` (batch_create, sample_bulk_register)
- future API endpoints

### 7.2 ID generation and status assignment
- Sample IDs should be generated by `Sample.save()` unless there is a validated external ID.
- For bulk creation, allow blank `sample_id` so the model generates it.
- Default `Sample.status` remains `"REGISTERED"`.
- Remove or avoid `"new"` unless it is a real workflow status defined in workflow config.

### 7.3 Audit logging
Audit should be emitted in services:
- project created
- batch created
- samples bulk created
- membership changes

Views should not create audit logs directly.

---

## 8. Permissions and access rules

### 8.1 Lab scope
A user can see and operate in labs assigned via `UserRole`.

### 8.2 Project access (recommended rule)
A user can access a project if:
- project.laboratory is in their lab scope
OR
- they are staff/superuser

Project membership is still required for certain actions:
- editing project documentation
- adding objectives
- bulk operations

This gives a practical approach:
- lab staff can see what exists in their lab
- project members control what gets modified

---

## 9. Implementation plan (no gambling)

This plan minimizes risk by making small, verifiable changes in the correct order.

### Step 0: Freeze the baseline
- Create branch: `feature/project-intake-coherence`
- Ensure current DB migrations are applied
- Confirm current wizard step2 resolves correct template
- Capture a short screen recording or screenshots of current flow for reference

Verification:
- Existing project creation still works for an admin user.

### Step 1: Make batch creation lab-derived
Change `batch_create()` so:
- It never trusts `laboratory` from POST
- It derives `laboratory_id` from selected project
- It enforces scope using project.laboratory

Verification:
- Attempt to post a mismatching lab id and confirm it is ignored.
- Confirm batch.clean() never fails due to lab mismatch.

### Step 2: Make bulk sample registration model-driven
Change `sample_bulk_register()` so:
- It allows blank `sample_id`
- It sets `status="REGISTERED"` consistently
- It enforces lab scope via batch.laboratory

Verification:
- Register samples with blank IDs and confirm IDs are generated via Sample.save().
- Confirm sample IDs include lab and project codes as expected.

### Step 3: Align wizard sample creation with canonical intake
Update `apply_project_draft()` so that when placeholders are requested:
- Create the project
- Create one intake batch (system-generated batch_code)
- Bulk create N samples under that batch using the same path as bulk register

Remove:
- custom `_new_sample_id()` generation
- setting status to `"new"`

Verification:
- Wizard creates a project, a batch, and samples that show up on batch detail page.
- No sample ID collisions.
- No nonstandard statuses.

### Step 4: Introduce Project workspace pages (minimal)
Create UI pages:
- project list (scoped)
- project detail (summary, batches, samples, objectives)
- project members (basic list and add/remove for staff first)

Verification:
- Lab user can open project detail for projects in scope.
- Staff can add a project member.

### Step 5: Objectives and activities using Experiment semantics
Implement:
- “Objectives” tab that creates and lists `Experiment` entries
- Provide fields: name, objective, narrative, analysis_context if needed
- Allow linking samples to an objective (assign sample.experiment)

Verification:
- Create objective, assign a sample, view it in sample detail.

### Step 6: Consolidate navigation and remove duplication
- Ensure the UI consistently funnels users into Project → Batch → Samples
- De-emphasize direct “samples create” except via batch
- Keep sample list as a read and track surface

Verification:
- There is one obvious path and it is consistent for soils lab smoke tests.

---

## 10. Testing strategy

Minimum tests to avoid regression:
1. Batch creation derives lab from project even when POST includes a different lab.
2. Non staff user cannot create a batch for a project outside their lab scope.
3. Bulk sample registration generates IDs when blank.
4. Wizard placeholder path creates batch + samples using the canonical service.
5. SampleBatch.clean() never fails for wizard-created objects.

Add tests under:
- `lims_core/tests/test_intake_coherence.py`

---

## 11. Rollout strategy

1. Deploy behind a feature flag if needed (optional).
2. First enable for a single lab profile (soils lab smoke test).
3. Verify with the `quietstevens` account.
4. Expand to other labs after the coherence contract is stable.

---

## 12. Definition of done

This phase is done when:
- Wizard, batch UI, and sample bulk register all produce the same outcomes.
- Batch lab cannot mismatch project lab through UI.
- Sample ID generation is consistent and handled by the model/service.
- Project has a clear workspace with objectives and membership.
- A sample can be linked to an objective within a project, and users can navigate that structure cleanly.

---

## 13. Immediate refactor targets in the current repo

### Must change
- `lims_core/views_ui.py`
  - `batch_create()` derive lab from project
  - `sample_bulk_register()` allow blank ID, enforce scope, set status REGISTERED
- `lims_core/wizard/services.py`
  - remove `_new_sample_id()` path
  - create batch when placeholders requested
  - standardize status and creation route through intake service

### Should change
- `lims_core/services/intake.py`
  - become the single source of truth for batch and bulk sample creation

---

## 14. Notes on terminology

The system should support different lab language without model fragmentation:
- “Experiment” can be labeled as Objective, Activity, Work Package, or Assay in the UI per lab profile.
- The underlying model remains stable and reduces schema churn.

End of document.
