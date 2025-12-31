# Metadata Renderer Contract (Frozen ABI)

**Document status:** Authoritative  
**Applies to:** NARO-LIMS metadata rendering system  
**Scope:** Template renderers under `lims_core/templates/lims_core/metadata/`

---

## 1. Purpose

Metadata field renderers are treated as a **frozen Application Binary Interface (ABI)**.

This contract exists to guarantee that:

- UI rendering is predictable and stable
- Accreditation and compliance rules cannot be bypassed accidentally
- Template regressions are caught at startup, not at runtime
- Multiple developers can work safely without hidden coupling

Any renderer that violates this contract will cause **Django system checks to fail** and **block server startup**.

This is intentional.

---

## 2. What Is a Renderer

A renderer is a Django template responsible for rendering **exactly one metadata field**, based on its declared `field_type`.

Examples:
- `field_text.html`
- `field_number.html`
- `field_date.html`
- `field_choice.html`
- `field_boolean.html`
- `field_unknown.html`

Renderers are selected dynamically by the metadata UI and **must not assume global context**.

---

## 3. REQUIRED CONTEXT (Strict)

Every renderer **MUST declare** the following REQUIRED contract at the top of the file:

```django
{#
REQUIRES:
- field
- field_code
- field_value
- errors
- schema_error
#}

Meaning of each key
Key	Description
field	MetadataField model instance
field_code	Canonical field identifier (string)
field_value	Current persisted or submitted value
errors	Validation errors dict for the current schema
schema_error	Schema-level error context

If any required key is missing, startup will fail.

4. FORBIDDEN CONTEXT (Strict)

Renderers MUST NOT reference or declare any additional keys.

Examples of forbidden context keys:

values

value

disable_submit

accreditation_mode

request

user

object

laboratory

any undeclared variable

If a renderer references undeclared keys, startup will fail.

This prevents:

Hidden coupling to views

Accidental bypass of accreditation logic

UI logic leaking into templates

5. Allowed Responsibilities

A renderer MAY:

Render the input element for its field type

Display per-field validation messages

Respect field.required

Render read-only or disabled inputs only if explicitly passed via contract in the future

A renderer MUST NOT:

Decide whether saving is allowed

Enforce accreditation rules

Read global UI state

Inspect schema locking state

Perform validation logic

6. field_unknown.html Special Case

field_unknown.html still participates in the contract.

It exists to:

Fail safely

Make schema errors visible

Prevent silent rendering failures

It must still declare the full REQUIRES block.

7. Enforcement Mechanism

This contract is enforced via Django system checks:

Violations raise lims_core.E002

Server startup is blocked

Errors are explicit and non-recoverable

This is not a warning system.
It is a hard safety barrier.

8. Change Policy (IMPORTANT)

This contract is FROZEN.

Any change requires:

Updating all renderers

Updating the system check logic

Updating this document

Do not add context keys casually.

If new behavior is required:

Propose it explicitly

Version the contract if needed

Apply changes atomically

9. Why This Exists (Short Version)

Accredited laboratory systems fail when:

UI logic drifts

Templates quietly change behavior

Validation rules become implicit

This contract ensures:

Deterministic rendering

Auditable behavior

Long-term maintainability

Breaking startup is cheaper than breaking accreditation.

10. Summary

Renderers are ABI components, not loose templates

Context is explicit and minimal

Violations are fatal by design

This protects the system, not the developer

Do not bypass. Do not weaken. Do not silence.
