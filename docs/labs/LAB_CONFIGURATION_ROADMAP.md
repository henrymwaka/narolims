# NARO-LIMS Laboratory Configuration Roadmap

**Document type:** Authoritative technical roadmap  
**Status:** Active  
**Audience:** Core developers, system architects, lab managers  
**Principle:** Configuration over customization

---

## 1. Purpose

This roadmap defines a **controlled, end-to-end plan** for enabling NARO-LIMS to support **multiple laboratory types** (soils, water quality, fisheries, tissue culture, biotechnology, etc.) using a **single codebase**.

All lab-specific behavior must be expressed through **configuration**, not forks, conditional logic, or duplicated templates.

---

## 2. Core Design Principles (Non-negotiable)

1. **One codebase**
2. **No lab-specific apps**
3. **No hard-coded lab logic**
4. **UI renders from configuration**
5. **Workflows remain generic**
6. **Admin-first, then controlled UI**
7. **Auditability over convenience**

Any change violating these principles must be rejected.

---

## 3. Phase 0 — Guardrails and Scope Lock

### Objective
Prevent architectural drift before implementation begins.

### Deliverables
- `docs/architecture/LAB_CONFIGURATION_PRINCIPLES.md`
- Written agreement that:
  - No lab-specific views
  - No lab-specific templates
  - No `if lab == X` logic

### Exit Criteria
- Principles documented
- Team alignment achieved

---

## 4. Phase 1 — Core Data Model Extensions

### Objective
Introduce configuration primitives without affecting existing UI or workflows.

### Models to Add
- `LaboratoryProfile`
- `LaboratoryModule`
- `MetadataTemplate`
- `WorkflowAssignment`

### Rules
- No business logic
- No UI
- Migrations only

### Exit Criteria
- Migrations applied
- Admin sees models
- No regression in existing pages

---

## 5. Phase 2 — Admin-First Configuration Interface

### Objective
Enable full lab configuration using Django Admin only.

### Admin Components
- Laboratory profiles
- Enabled modules
- Metadata templates (JSON schema)
- Workflow assignments

### Validation
- One active template per scope
- Schema validation enforced
- Versioned templates

### Exit Criteria
- A lab can be fully configured via admin
- No user-facing UI changes

---

## 6. Phase 3 — Metadata Rendering Engine

### Objective
Dynamically render lab-specific fields.

### Components
- Metadata resolver:


resolve_metadata(lab, applies_to, module=None)

### Constraints
- Workflow engine remains unchanged
- Role-based permissions preserved

### Exit Criteria
- Same sample type behaves differently across labs
- No workflow hard-coding

---

## 8. Phase 5 — Lab Configuration Dashboard

### Objective
Reduce reliance on Django Admin.

### Phase 5.1 — Read-only Dashboard
- Enabled modules
- Active workflows
- Metadata templates

### Phase 5.2 — Controlled Editing
- Toggle modules
- Assign workflows
- Schema builder UI

### Exit Criteria
- Lab managers configure without admin access
- Audit trail enforced

---

## 9. Phase 6 — Instrument and Method Registry

### Objective
Meet industry and ISO expectations.

### Components
- Instrument registry
- Method registry
- Versioned methods
- Instrument-method binding

### Workflow Integration
- Capture method and instrument at execution time

### Exit Criteria
- Method traceability
- Audit-ready results

---

## 10. Phase 7 — Role and Permission Refinement

### Objective
Lab-scoped authority boundaries.

### Features
- Lab-specific roles
- Module-based permissions
- Workflow action gating

### Exit Criteria
- Same user behaves differently per lab
- Permissions explainable to auditors

---

## 11. Phase 8 — End-to-End Testing Strategy

### Test Categories
- Configuration resolution
- Metadata rendering
- Workflow transitions
- Permission enforcement
- Audit logging

### Tools
- Django tests
- Curl-based UI smoke tests
- Browser verification

### Exit Criteria
- No regressions
- All critical paths verified

---

## 12. Phase 9 — Pilot Lab Rollout

### Suggested Pilots
1. Water Quality Lab
2. Biotechnology Lab
3. Soils Lab

### Evaluation Criteria
- Configuration effort
- User friction
- Audit readiness

### Exit Criteria
- New lab onboarded without code changes

---

## 13. Phase 10 — Documentation and Freeze

### Deliverables
- Lab onboarding guide
- Configuration handbook
- Anti-patterns guide (“What not to do”)

### Final Step
- Feature freeze
- Stabilization window

---

## 14. Absolute Stop Conditions

If any future change requires:
- Duplicating templates
- Adding lab-specific conditionals
- Creating lab-specific apps

**Stop immediately.**

This is a violation of the roadmap.

---

## 15. Status

This roadmap is the **authoritative execution plan** for laboratory configuration in NARO-LIMS.

Deviation requires explicit architectural review.

---
