📋 NARO-LIMS — UI / Template Pull Request Review

PR Type (check all that apply):

 UI Template change

 New template

 Partial / include update

 Workflow or SLA UI

 Styling / layout only

 Refactor (no functional change)

1. Scope Declaration (Mandatory)

Files touched (templates only):

lims_core/templates/...

Primary page(s) affected:

 Sample list

 Sample detail

 Batch list

 Batch detail

 Workflow widget

 Other: ___________________

2. Structural Compliance
Template inheritance

 Template extends lims_core/base.html

 No duplicate <html>, <head>, <body> tags

 Uses only approved blocks:

 title

 page_title

 page_meta

 extra_head

 content

 extra_scripts

❌ Fail if base structure is redefined

3. Include Safety

 All {% include %} statements render correctly

 Included templates exist on disk

 No literal {% include ... %} text visible in UI

 All required include variables are explicitly passed

4. Data Safety & Guards
Attribute access

For every model field rendered:

 Field exists on model

 Access is guarded using:

 |default

 {% if %}

 View-computed safe attribute

❌ Fail if raw attribute access can raise AttributeError

Forbidden template patterns (must all be unchecked)

 {{ obj.deep.attr.chain }} without guards

 ORM calls inside templates

 Access to _private attributes

 Business logic in templates

5. Workflow Widget Rules (if applicable)

 Uses lims_core/workflow_widget.html

 Passes:

 workflow_kind

 workflow_object_id

 No inline JS manipulating workflow state

 Workflow loads without console errors

6. SLA Rendering Rules (if applicable)

 SLA computed in view, not template

 SLA absence handled gracefully

 CSS class matches known states:

 sla-ok

 sla-warning

 sla-breached

 sla-na

❌ Fail if SLA absence causes template error

7. UI Consistency

 Uses existing CSS variables

 No hardcoded colors outside palette

 Section cards use .section pattern

 No layout regression on mobile

8. Authentication Awareness

 Page assumes authentication only if view enforces it

 Admin links guarded by role checks

 No unguarded use of user object

9. Error Resilience

Manually verified:

 Object without batch renders safely

 Missing optional fields do not crash page

 Empty states are explicit and readable

 No 500 errors triggered

10. Performance & Load Safety

 No .all, .count, or heavy loops in template

 Querysets are pre-limited in view

 No nested includes inside loops unless justified

11. Verification Evidence (Required)

Checked on:

 Local dev

 Staging

 Production

Verification notes (brief):

12. Reviewer Decision

Outcome:

 ✅ APPROVE

 ⚠️ REQUEST CHANGES

 ❌ BLOCK (explain below)

Reviewer comments:

Enforcement Statement

This PR must not be merged unless all applicable sections are satisfied.
UI correctness and template safety take precedence over feature delivery speed.
