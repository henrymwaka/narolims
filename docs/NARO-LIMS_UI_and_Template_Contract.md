docs/NARO-LIMS_UI_and_Template_Contract.md

# NARO-LIMS UI and Template Contract
**Document ID:** NARO-LIMS-UI-CONTRACT  
**Version:** 1.0  
**Status:** Authoritative  
**Scope:** All Django UI views and templates under `lims_core/`  
**Applies to:** Developers, maintainers, reviewers  

---

## 1. Purpose

This document defines the **binding contract** between:
- Django views
- Django templates
- UI widgets
- Runtime services (Gunicorn, Nginx)

Its purpose is to prevent:
- Production 500 errors
- Silent UI corruption
- Template-driven crashes
- Divergence between backend state and UI representation

This document supersedes ad-hoc conventions and informal practices.

---

## 2. Core Architectural Principle

> Templates are passive renderers.  
> Views are the sole authority for logic and state.

A template must render correctly using **only explicit context variables** supplied by its view.

If a value is not guaranteed, it must be handled **before rendering**, not inside the template.

---

## 3. View–Template Contract

### 3.1 Explicit context only

Every variable used in a template must appear explicitly in the `render()` call.

**Required pattern:**
```python
return render(
    request,
    "lims_core/samples/detail.html",
    {
        "sample": sample,
        "sla": sla,
    }
)


Templates must not infer, compute, or reconstruct values.

3.2 No implicit attributes

Templates must never rely on:

Transient attributes

Runtime-only attributes

Attributes added conditionally in views

If it is not part of the model or explicitly passed, it does not exist.

4. Template Safety Rules (Hard Rules)
4.1 Underscore-prefixed attributes are forbidden

❌ Forbidden:

{{ sample._safe_status }}
{{ sample._sla }}


Reason:
Underscore-prefixed attributes are internal implementation details and not part of a stable interface.

✅ Correct:

{{ sample.status }}
{{ sla }}

4.2 No business logic in templates

❌ Forbidden:

{% if sample.status == "REGISTERED" and sample.batch %}


All business logic must be computed in the view.

Templates may only:

Display values

Check simple existence

Iterate collections

4.3 Safe access to relations is mandatory

❌ Forbidden:

{{ sample.batch.batch_code }}


✅ Required:

{% if sample.batch %}
  {{ sample.batch.batch_code }}
{% endif %}


or precomputed in the view.

4.4 Static includes only

❌ Forbidden:

{% include template_name %}


✅ Required:

{% include "lims_core/workflow_widget.html" %}


This ensures traceability and static analysis.

5. Workflow Widget Contract
5.1 Canonical include syntax

The workflow widget must always be included as:

{% include "lims_core/workflow_widget.html" with
   workflow_kind="sample"
   workflow_object_id=sample.id
%}


No alternative patterns are allowed.

5.2 Widget isolation guarantee

The workflow widget:

Must render without errors on first load

Must not assume JavaScript availability

Must not depend on external template context

Must fail silently and visibly, never catastrophically

All dynamic behavior must be handled via API calls.

6. SLA Rendering Contract

SLA is optional

SLA must be passed as a top-level context variable

Templates must degrade gracefully

Canonical pattern:

{% if sla %}
  <span class="sla-pill sla-{{ sla.status }}">
    {{ sla.status|upper }}
  </span>
{% else %}
  <span class="muted">No SLA defined for this state.</span>
{% endif %}


Templates must never attempt to compute SLA status.

7. Template Structure Standard

All UI templates must follow this structure:

{% extends %}

{% load %}

block title

block page_title

block page_meta

block extra_head

block content

block extra_scripts (optional)

Deviation is not permitted for core UI pages.

8. Restart and Runtime Rules
8.1 Template changes require service restart

After any change to:

Templates

Static assets

View files affecting templates

You must run:

sudo systemctl restart narolims


Gunicorn workers cache templates.
Browser refresh alone is insufficient.

8.2 Debugging discipline

If a page renders incorrectly:

Check journalctl -u narolims -f

Confirm service restart occurred

Confirm the correct template file is being loaded

Confirm context variables exist

Do not debug templates without log confirmation.

9. UI Wiring Expectations

Navigation links may exist before full wiring, but must:

Resolve to valid routes

Never raise 404 or 500 errors

Render placeholder pages if incomplete

Broken links are acceptable during development. Broken renders are not.

10. Mandatory Review Checklist

Before committing UI or template changes, verify:

No underscore-prefixed attributes used

No business logic in templates

All variables are passed explicitly

All includes are static

Page renders with missing optional data

Page renders with JavaScript disabled

Service restart performed

Failure on any item blocks merge.

11. Enforcement

Violations of this contract are classified as:

Production safety issues

Architectural regressions

They must be fixed immediately before feature work continues.

12. Closing Statement

NARO-LIMS UI is an operational system, not a prototype.

Templates are treated as regulated surfaces.
Predictability, auditability, and stability take precedence over convenience.

This contract exists to keep the system correct under pressure.
