NARO-LIMS
UI Template Audit Checklist

Document ID: NARO-LIMS-TAC
Version: 1.0
Status: Enforced
Scope: All Django templates under lims_core/templates/
Authority: UI & Template Contract

1. Purpose

This checklist is used to audit, review, and approve any Django template used in NARO-LIMS before:

Merge to main

Deployment to production

UI refactors

Feature additions touching templates

Failure to pass this checklist must block deployment.

2. Applicability

Applies to:

base.html

All templates extending base.html

All partials included via {% include %}

All templates rendering model data

3. Audit Outcome
Result	Meaning
✅ PASS	Template is compliant
⚠️ CONDITIONAL	Safe but needs cleanup
❌ FAIL	Deployment must stop
4. Structural Integrity Checks
4.1 Template Inheritance

 Template extends lims_core/base.html

 No duplicate <html>, <head>, <body> tags

 Uses only declared blocks:

 title

 page_title

 page_meta

 extra_head

 content

 extra_scripts

Fail if: base structure is redefined or overridden.

4.2 Includes Discipline

 {% include %} statements are valid Django syntax

 Included templates exist on disk

 No literal {% include ... %} text rendered in UI

 All required variables for includes are passed explicitly

Fail if: include syntax leaks into rendered HTML.

5. Data Safety Rules
5.1 Direct Attribute Access

For every object attribute rendered:

 Attribute exists on the model

 Attribute access is guarded:

|default

{% if %} block

Precomputed safe attribute (preferred)

Fail if: raw attribute access can raise AttributeError or NoneType.

5.2 Forbidden Patterns

The following must not appear:

 {{ object.deep.attr.chain }} without guards

 {{ sample._private_attr }}

 {{ obj.related_set.all }} in templates

 ORM logic inside templates

5.3 Computed Runtime Fields

If template uses:

SLA

Workflow state

Derived status

Aggregates

Then:

 Value is computed in view

 Passed explicitly in context

 Template does not compute logic

6. Workflow Widget Compliance

For any page including workflow widget:

 Uses {% include "lims_core/workflow_widget.html" %}

 Supplies:

 workflow_kind

 workflow_object_id

 No inline JS manipulating workflow state

 Widget loads without JS console errors

7. SLA Rendering Rules

If SLA is displayed:

 SLA object exists or is safely absent

 SLA CSS class matches known states:

sla-ok

sla-warning

sla-breached

sla-na

 SLA absence handled gracefully

Fail if: missing SLA causes template crash.

8. Styling & UI Consistency

 Uses existing CSS variables

 No inline layout-breaking styles

 No duplicated global classes

 Section cards follow .section pattern

 No hardcoded colors outside allowed palette

9. Authentication Awareness

 Template assumes authenticated user only if view is protected

 No reliance on user unless guarded

 Admin links shown only when is_staff or is_superuser

10. Error Resilience

 Template renders even if optional relations are missing

 Batch-less samples do not error

 Project-less objects handled safely

 Empty states are explicit, not silent

11. Performance & Load Safety

 No loops over large querysets without limits

 No .count or .all inside template

 No nested includes inside loops unless justified

12. Final Approval Checklist

Before merge:

 Template manually reviewed

 Sample page loaded successfully

 No 500 errors triggered

 Browser console clean

 Journal logs clean

 Checklist archived with commit or PR

13. Enforcement Rule

Any template that fails this checklist must not be deployed, regardless of feature urgency.

14. Maintenance

Update this checklist when:

Base layout changes

Workflow engine evolves

SLA logic changes

Version bump required on update

End of Document
