# Project Intake Coherence Phase
Document ID: LIMS-PHASE-INTAKE-01  
Status: Authoritative  
Owner: Core platform  
Scope: Project creation, batching, sampling, and collaboration primitives  
Change control: Restricted (requires review)

## 1. Why this phase exists
Project intake currently has multiple creation pathways that can diverge:
- Project wizard creates projects via `wizard/services.py`
- Batch creation UI creates batches via `views_ui.py::batch_create`
- Sample creation occurs via bulk register and other UI routes

When these pathways do not share a canonical service layer, the system becomes inconsistent:
- Projects exist but do not surface in batch workflows
- Batches exist but are not linked to projects
- Samples exist but do not attach cleanly to the project narrative (objectives/tasks)
- Users can be scoped to a lab but have no structured collaboration inside a project

This phase defines the authoritative intake model and implementation steps to enforce it.

## 2. Core domain entities and meaning
The following are the canonical intake entities.

### 2.1 Project
A Project is the top-level container that organizes work within a Laboratory.
A project is not only a name and description. It is a coordination object:
- what work is being done
- why it is being done
- who is responsible
- what activities and milestones exist
- how evidence (samples, batches, results) maps to objectives

Source of truth entity: `lims_core/models/core.py::Project`

### 2.2 SampleBatch
A SampleBatch represents a real-world collection/submission event.
It is the bridge between project planning and physical sample movement:
- collection event metadata (site, collector, client)
- intake time and provenance
- the unit of submission/receipt

Source of truth entity: `lims_core/models/core.py::SampleBatch`

### 2.3 Sample
A Sample is a discrete physical sample unit that will proceed through workflow states.
Samples are the primary workflow objects and the primary unit of SLA tracking.

Source of truth entity: `lims_core/models/core.py::Sample`

## 3. Intake invariants (non-negotiable)
These are hard rules the code must enforce.

### 3.1 Relationship invariants
1. Every Batch must belong to exactly one Project.
2. Every Sample must belong to exactly one Batch.
3. Every Sample must belong to the same Project as its Batch.
4. Every Project belongs to exactly one Laboratory.
5. All objects shown in UI lists are filtered by laboratory scope derived from `UserRole`.

If the current model allows nulls that violate these rules, this phase implements guardrails at:
- service layer (canonical creation functions)
- UI validation (forms)
- database constraints (when safe)

### 3.2 Intake pathway invariants
All creation entry points must call a canonical intake service.
Direct `Model.objects.create(...)` for Project/Batch/Sample in UI views is considered a defect.

## 4. Scope model: lab roles vs project membership
### 4.1 Lab scope (existing)
Lab scope is defined by `UserRole` filtered by labs in `_user_lab_ids(user)`:
- determines which labs a user can see
- determines which projects/batches/samples a user can interact with

Lab scope is a platform-level permission boundary.

### 4.2 Project membership (new, required)
Lab scope alone is not collaboration.
Project membership defines who is working on a project and their responsibilities.

This phase introduces Project membership as a separate concept:
- a user can be in the lab scope but not part of a project team
- a user can be assigned to a project with a role (lead, analyst, reviewer, sampler, client liaison)
- project membership supports auditability and accountability

This must not duplicate `UserRole`. `UserRole` grants lab scope. Membership grants collaboration and project-level permissions.

## 5. Objectives, activities, tasks, milestones (project narrative)
A project must support structured work planning so that samples can be linked to intent.

### 5.1 Objective
An Objective defines a goal such as:
- "Determine NPK status of 10 soil samples from Kiwafu (1 acre plot) for fertilizer planning."

### 5.2 Activity / Task
Tasks define actionable steps:
- sample collection
- sample reception and labeling
- analysis (N, P, K) methods
- QC review
- reporting

### 5.3 Milestone
Milestones define stage boundaries:
- collection complete
- analysis complete
- report delivered

### 5.4 Sample linkage rule
A Sample may be linked to:
- one Objective (recommended)
- optionally one Task (if the workflow requires that granularity)

This keeps reporting coherent without overcomplicating the data model.

## 6. Canonical intake UX (what the UI must mean)
### 6.1 Project creation
Project wizard is the preferred UX for starting a project.
Wizard collects:
- institute + lab (derived from lab scope)
- project name and description
- optional placeholder sample plan (type + count)

On apply:
- Project is created
- if placeholders requested: a Batch is auto-created and Samples created inside it
- user is optionally assigned as project lead (membership)

### 6.2 Batch creation
Batch creation UI exists for real intake events:
- selecting a lab
- selecting an existing project in that lab
- capturing collection metadata

Batch creation must require a Project selection.
Creating a batch without project is prohibited.

### 6.3 Sample creation
Sample creation happens via one of two allowed routes:
1. Wizard placeholders: creates samples under an auto-created batch
2. Bulk register under a batch: adds samples to an existing batch

Direct "create sample with no batch" is prohibited.

## 7. Implementation plan (no gambling)
### 7.1 Step 0: Establish safety
- Create a checkpoint commit before refactor.
- Add a single feature branch for intake refactor.

### 7.2 Step 1: Introduce canonical intake service
Create `lims_core/services/intake.py`:
- create_project_from_draft(...) (if needed)
- create_batch_for_project(...)
- create_samples_for_batch(...)
- create_intake_batch_with_samples(...)

This becomes the only permitted creation pathway.

### 7.3 Step 2: Refactor existing entry points to use the service
Refactor:
- `wizard/services.py` apply_project_draft -> uses intake service
- `views_ui.py::batch_create` -> uses create_batch_for_project
- `views_ui.py::sample_bulk_register` -> uses create_samples_for_batch

### 7.4 Step 3: Enforce invariants in forms and templates
- Batch create form must require project
- Wizard step2 must clearly display project summary and sample plan
- UI lists must show project context (project name/code) consistently across:
  - samples list
  - batches list
  - batch detail

### 7.5 Step 4: Add project membership (minimal viable)
Add models:
- ProjectMember(project, user, role, is_active, created_by)

Add UI:
- basic project team management under a "Project" section
- initial default: project creator becomes lead

### 7.6 Step 5: Add objectives/tasks (minimal viable)
Add models:
- ProjectObjective(project, code, title, description, priority, status)
- ProjectTask(project, objective?, title, status, due_date, assignee?)

Add link:
- Sample.objective nullable FK (or M2M if strictly needed later)

### 7.7 Step 6: Tests (contract tests)
Add tests to prevent regression:
- wizard apply creates project + batch + samples when placeholders enabled
- batch_create rejects missing project
- bulk register creates samples linked to batch and project
- visibility tests: user sees only lab-scoped projects/batches/samples
- membership tests: only project members can edit objectives/tasks (when enforced)

## 8. Acceptance criteria (done means done)
This phase is complete when:
1. A user with lab scope can create a project via wizard and see it immediately in:
   - project dropdown for batch creation
   - batches list after batch creation
   - samples list after placeholder/bulk creation
2. There is exactly one canonical creation path (intake service), used everywhere.
3. A soil scenario works end-to-end:
   - Create project "Kiwafu Entebbe Soil NPK (10 samples)"
   - Choose placeholder sample type "soil", count 10
   - Apply
   - Confirm: one batch exists, 10 samples exist, all linked to project
4. The UI does not expose paths that create orphan batches or orphan samples.
5. Project membership exists (minimal), and project creator is recorded as lead.

## 9. Out of scope (explicitly deferred)
- Full method catalog for analytical chemistry
- Results/assay pipelines and instrument integration
- Full ISO 17025 document control and CAPA workflows
These come after intake coherence is stable.

