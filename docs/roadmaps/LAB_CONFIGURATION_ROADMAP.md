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
- Dynamic form renderer
- JSON-backed storage

### Integration Points
- Sample detail page
- Batch detail page

### Exit Criteria
- Different labs see different fields
- No template duplication
- Validation enforced

---

## 7. Phase 4 — Workflow Binding Per Lab

### Objective
Bind workflows dynamically per lab and sample type.

### Mechanism
Replace static calls with:
