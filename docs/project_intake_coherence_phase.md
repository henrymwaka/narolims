# Project Intake Coherence Phase
Document ID: NAROLIMS-INTAKE-PHASE-1  
Status: Authoritative (implementation guide)  
Branch: feature/project-intake-coherence  
Scope: Project creation, intake batches, sample creation pathways, and team scoping  
Non-goals: Full ISO package, full task management suite, full client billing module (these come later)

## 1) Why this phase exists
Right now, the system can create samples via multiple paths (wizard placeholders, batch bulk register, ad hoc sample create patterns). Those paths are not coordinated, so users experience:
- duplicated concepts (project vs batch vs sample creation flows that do not agree)
- unclear “source of truth” for how samples should enter a project
- no consistent place to capture intake details (site, collector, client, chain-of-custody-lite)
- confusion around user scope (lab role exists, but project collaboration is not modeled)

This phase makes one clear intake path that everything else can build on, without breaking what already works.

## 2) Concrete target behavior
### 2.1 Canonical intake model
- A Project is the umbrella.
- A SampleBatch is the canonical intake container for sample registration events.
- Samples are created inside a batch.
- The wizard creates a Project and (optionally) creates an intake batch and a set of samples for that batch.
- The batches UI remains valid, but it becomes aligned with the wizard and the intake service.

### 2.2 The Soil NPK example as the acceptance test
Use case: “Find NPK content of 10 soil samples collected from Kiwafu, Entebbe, 1-acre plot.”

Target flow:
1. User selects laboratory: Soils Laboratory (already in scope via UserRole).
2. User creates a Project: “Kiwafu Entebbe Soil NPK (10 samples)”.
3. System creates a default INTAKE SampleBatch for that project (or user confirms intake details on step 2).
4. User enters intake batch details:
   - collection_site: Kiwafu, Entebbe (with optional GPS later)
   - collected_by: name
   - collected_at: date/time
   - notes: plot size 1 acre, sampling pattern, depth, composite vs replicate
5. User specifies sample plan:
   - count = 10
   - sample_type = soil
   - optional external_id pattern (for field labels)
6. System creates 10 samples in that batch with system-generated Sample.sample_id.
7. User goes to batch detail and sees the 10 samples.
8. Metadata entry (schema-driven) and workflow transitions happen per sample.

If we can do this cleanly with a non-staff lab user, the intake layer is coherent.

## 3) Non-negotiable design rules
### Rule A: One source of truth for sample creation
All creation of samples for a batch must go through a single service layer:
- `lims_core/services/intake.py`

No other view should generate sample IDs or decide statuses.

### Rule B: Samples are not created “floating”
A sample must belong to:
- a Project, and
- a SampleBatch (for intake-created samples)

Ad hoc creation can still exist later, but it must still attach to a batch (even if the UI calls it “Quick Intake”).

### Rule C: Lab role controls lab scope, not collaboration
`UserRole` remains the authoritative lab scope mechanism.
Project collaboration is modeled separately (ProjectMembership) later, but it must never expand scope beyond lab role.

## 4) Implementation plan (no gambling)
This is deliberately staged. Each stage ends with a working system and a small, testable surface.

### Stage 0: Stabilize the working tree
Goal: avoid mixing UI polish, wizard edits, and intake refactor in one unreviewable chunk.

Steps:
1. Commit current progress on `feature/project-intake-coherence` (or split into small commits).
2. Ensure you can run:
   - `python manage.py check`
   - `python manage.py test lims_core` (even if minimal)

Deliverable:
- Clean, buildable branch state.

### Stage 1: Lock in the canonical intake service
Goal: create a single backend API for:
- creating a project
- creating its intake batch
- creating N samples in that batch using the model’s own sample_id generation

Target functions (minimum viable):
- `create_project_with_intake_batch(...)`
- `create_intake_batch_for_project(...)`
- `create_samples_for_batch(batch, count, sample_type, created_by=None, external_ids=None)`

Implementation notes:
- Do not use `bulk_create` for sample creation if you depend on `Sample.save()` to generate IDs and freeze schemas.
- Use a transaction and looped `.save()` for now. For typical lab intake sizes (10 to 200) this is acceptable and much safer.
- Never set `Sample.status` in intake creation unless you have a documented workflow reason. Default is already `REGISTERED` in the model.

Deliverables:
- `lims_core/services/intake.py` with the above functions
- clear docstrings stating “all sample creation must go through this”

### Stage 2: Refactor wizard to call intake service
Goal: the wizard becomes a thin UI wrapper. No logic duplication.

Changes:
1. `lims_core/wizard/services.py`
   - Replace direct `Project.objects.create(...)` and `Sample.objects.bulk_create(...)`
   - Call `create_project_with_intake_batch(...)`
2. `lims_core/wizard/views.py`
   - Keep draft flow and scope checks intact
   - On POST in step2, call the wizard service which delegates to intake
3. `lims_core/templates/lims_core/wizard/step2.html`
   - Ensure the template always renders even if samples count is 0
   - Provide a visible “You will create an intake batch” confirmation line
   - On success redirect to either:
     - project workspace, or
     - batch detail page (preferred for coherence)

Recommendation:
- Redirect to the created batch detail page because it reinforces the intake model immediately.

Deliverable:
- Wizard creates project and an intake batch consistently for lab users.

### Stage 3: Harmonize UI batch creation with intake
Goal: remove conceptual duplication between “Batches” UI and the wizard.

Minimum change:
- Make `/lims/ui/batches/create/` optionally support:
  - selecting an existing project, then creating an INTAKE batch for it
  - generating N samples server-side using the same intake service

This makes batch creation usable even without the wizard, but still consistent.

Deliverables:
- `views_ui.batch_create` uses `create_intake_batch_for_project` and `create_samples_for_batch`
- Batch create page includes:
  - “Create as intake batch” checkbox (default on)
  - “Generate sample count” numeric input

### Stage 4: Project organization (lightweight, not a full PM system)
Goal: give projects a structured place to describe objectives and organize samples.

Do not build a big Jira clone.
Start with the minimum that makes lab projects readable:

Add model (Phase 1.5 or Phase 2 depending on time):
- `ProjectObjective`
  - project FK
  - code (OBJ-01)
  - title
  - description
  - is_active
- Then allow Sample to reference an objective (optional) instead of free text.

But for this phase, the system can use `Experiment.objective` as a temporary internal grouping for samples. That is already in your model.

Deliverable:
- Document the plan, do not implement unless intake is stable.

### Stage 5: Project team membership (after intake is stable)
Goal: support collaboration without breaking lab scoping.

Add model:
- `ProjectMembership`
  - project FK
  - user FK
  - role_in_project (PI, Analyst, Technician, Reviewer)
  - is_active

Rule:
- membership never expands scope beyond lab role.
- effective access = user has lab role for project.laboratory AND membership is present (optional enforcement later).

Deliverable:
- Implement after intake is stable and tested.

## 5) Required tests (must exist before expanding scope)
Even if you currently have few tests, this phase needs at least these.

Create: `lims_core/tests/test_intake_service.py`

Minimum tests:
1. `test_create_project_with_intake_batch_creates_project_and_batch`
   - asserts project.laboratory matches
   - asserts one batch exists and is linked
2. `test_create_samples_for_batch_generates_unique_sample_ids`
   - create 10 samples
   - assert count = 10
   - assert all sample_id unique
3. `test_intake_respects_lab_scope_assumptions`
   - service should raise if project lab mismatches batch lab
4. `test_wizard_apply_project_draft_uses_intake`
   - given a ProjectDraft payload with count = 10
   - apply
   - assert batch and samples exist

You do not need to over-test templates.
You do need to prove the object graph is created correctly.

## 6) Data model alignment decisions
### 6.1 SampleBatch additions (recommended)
Add fields only if they improve intake clarity without forcing migrations that break old data.

Recommended additions:
- `batch_kind` (choices: INTAKE, PROCESSING, SHIPMENT, OTHER) default INTAKE
- `intake_method` (optional text: composite, replicate, transect)
- `chain_of_custody_ref` (optional short string)

If you do not want migrations now, you can defer these fields and still use existing columns:
- collection_site, collected_at, collected_by, client_name, notes

### 6.2 Sample creation strategy
Use `Sample.save()` based generation for now.
It guarantees:
- consistent prefixing logic
- schema freezing logic
- no accidental empty sample_id persisted

If performance becomes an issue later, optimize with a dedicated allocator table or a database sequence, but not in this phase.

## 7) UI contract changes
This phase should make UI navigation logically consistent:

- Project creation always results in:
  - Project created
  - Intake batch created (default)
  - Optional N samples created
- After creation, the user lands on:
  - Batch detail page, with immediate visibility of the samples and the “Bulk add more” actions

Add left menu link (later, once page exists):
- “Projects” (lists projects in lab scope)
- Keep “Batches” as a first-class intake view
- Samples list remains as a cross-project operational queue

## 8) Migration and rollout checklist
Do this in order:
1. Create intake service and tests.
2. Refactor wizard apply to use intake service.
3. Fix batch_create to use intake service (optional but recommended).
4. Deploy to staging or your own server branch.
5. Test with a non-staff account:
   - quietstevens in Soils lab
   - create project
   - create 10 samples
   - verify batch detail shows them
   - verify sample list shows them
6. Only after this is stable, proceed to project membership and objectives.

## 9) Definition of Done (Phase complete)
Phase is complete when:
- A lab user can create a project and intake batch cleanly without staff privileges.
- Sample creation happens in one coherent place (intake service).
- Wizard and batch UI do not contradict each other.
- The Soil NPK example works end-to-end.

## 10) Next phase preview (do not implement until Phase complete)
Phase 2 (Project structure):
- Project list and project detail UI
- Objectives and tasks (lightweight)
- Project membership and collaboration controls
- Linking samples to objectives
- Better reporting (per project, per objective, per batch)

This is where the system becomes “top notch” for real lab operations, but it must sit on a coherent intake foundation first.
