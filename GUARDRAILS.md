lims_core/workflows/rules.py


### Principles
- Models do not enforce transitions
- Serializers allow status writes
- Views validate transitions explicitly
- Invalid transitions return field-scoped errors

### Sample Workflow
- REGISTERED → IN_PROCESS → QC_PENDING → QC_PASSED / QC_FAILED → ARCHIVED

### Experiment Workflow
- PLANNED → RUNNING → PAUSED → COMPLETED / CANCELLED

### Error Contract
Invalid transitions must return:

```json
{
  "status": "Invalid <entity> status transition: OLD → NEW"
}

3. Permission Model
Write Access

Requires authenticated user

Requires active laboratory resolution

Requires role in laboratory

Role Definitions

WRITE: Technician, Data Manager, Lab Manager, PI

ADMIN: Lab Manager, PI

StaffMember Special Case

Only ADMIN roles may modify staff

Guardrails enforced before serializer validation

4. Testing Contract

All guardrails are enforced by tests:

test_status_workflows.py

test_write_guardrails.py

Rules

No guardrail change without test change

Green tests are required for merge

Test failure means contract violation

5. Change Discipline

Do not:

Bypass guardrails in views

Make fields writable “temporarily”

Add silent coercion logic

Any exception must be:

Documented here

Covered by tests

Reviewed explicitly
