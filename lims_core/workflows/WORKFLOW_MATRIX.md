# NARO-LIMS Sample Workflow Transition Matrix

This document is the authoritative specification for all allowed
Sample status transitions in NARO-LIMS.

Code, API behavior, and tests MUST conform to this matrix.
Any deviation is a defect.

---

## States

| State        | Meaning                                      | Terminal |
|--------------|----------------------------------------------|----------|
| RECEIVED     | Sample registered and awaiting processing    | No       |
| QC_PENDING   | Awaiting quality control decision            | No       |
| QC_PASSED    | QC passed, sample cleared for downstream use | No       |
| QC_FAILED    | QC failed, sample rejected                   | No       |
| ARCHIVED     | Sample locked and permanently closed         | Yes      |

---

## Role Definitions

| Role      | Description                                   |
|-----------|-----------------------------------------------|
| LAB_TECH  | Performs routine lab operations               |
| QA        | Performs quality control decisions            |
| ADMIN     | System authority, final override              |

---

## Allowed Transitions by Role

### From `RECEIVED`

| Role     | Allowed Transitions |
|----------|---------------------|
| LAB_TECH | QC_PENDING          |
| QA       | —                   |
| ADMIN    | QC_PENDING          |

---

### From `QC_PENDING`

| Role     | Allowed Transitions            |
|----------|--------------------------------|
| LAB_TECH | —                              |
| QA       | QC_PASSED, QC_FAILED           |
| ADMIN    | QC_PASSED, QC_FAILED, ARCHIVED |

---

### From `QC_PASSED`

| Role     | Allowed Transitions |
|----------|---------------------|
| LAB_TECH | —                   |
| QA       | —                   |
| ADMIN    | ARCHIVED            |

---

### From `QC_FAILED`

| Role     | Allowed Transitions |
|----------|---------------------|
| LAB_TECH | —                   |
| QA       | —                   |
| ADMIN    | ARCHIVED            |

---

### From `ARCHIVED`

| Role     | Allowed Transitions |
|----------|---------------------|
| ALL      | — (terminal state)  |

---

## Enforcement Rules

- `ARCHIVED` is irreversible
- Visibility ≠ Authority
- Absence from this matrix means **forbidden**
- ADMIN authority does not bypass terminal state locks

---

## Change Control

Any modification requires:
1. Update to this document
2. Matching code change
3. Updated tests
4. Version bump

