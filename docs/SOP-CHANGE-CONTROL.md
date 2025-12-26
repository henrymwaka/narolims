---
title: SOP for Change Control and Code Ownership
document_id: SOP-CC-001
standard: ISO/IEC 17025:2017
clauses:
  - 4.2 (Impartiality)
  - 7.5 (Technical Records)
  - 7.11 (Control of Data and Information Management)
  - 8.3 (Control of Management System Documents)
  - 8.5 (Actions to Address Risks and Opportunities)
repository: henrymwaka/narolims
effective_date: 2025-12-25
status: Active
---

# Standard Operating Procedure (SOP)
## Change Control, Code Ownership, and Cryptographic Traceability

---

### 1. Purpose

This SOP defines the mandatory process for controlling changes to software, configuration, documentation, and workflows within the **NARO-LIMS** repository.  
It ensures traceability, accountability, integrity, and audit readiness in accordance with **ISO/IEC 17025:2017**.

---

### 2. Scope

This SOP applies to:

- Application source code
- Workflow logic and guardrails
- Configuration files
- CI/CD pipelines
- Security-sensitive documentation
- Release artifacts linked to laboratory operations

---

### 3. Normative References

- ISO/IEC 17025:2017
- Git SCM documentation
- GitHub CODEOWNERS specification
- OpenPGP (RFC 4880)

---

### 4. Definitions

| Term | Definition |
|----|----|
| Change | Any modification to tracked repository content |
| CODEOWNERS | GitHub mechanism assigning mandatory reviewers to paths |
| Signed Commit | Git commit cryptographically signed using OpenPGP |
| Signed Tag | Annotated Git tag signed using OpenPGP |
| SOP-Linked Release | A release explicitly governed by this SOP |

---

### 5. Roles and Responsibilities

| Role | Responsibility |
|----|----|
| Code Owner | Reviews and approves changes affecting owned paths |
| Repository Maintainer | Ensures compliance with this SOP |
| Auditor | Verifies evidence of control and traceability |

---

### 6. Code Ownership Control (ISO 17025:2017 Clause 8.3)

6.1  
The repository **MUST** contain a `CODEOWNERS` file located at:

.github/CODEOWNERS
6.2  
The `CODEOWNERS` file **MUST** define ownership for:

- Core application logic
- Workflow enforcement
- Security-sensitive files
- CI/CD automation
- Database migrations
- SOP and compliance documentation

6.3  
Changes to owned paths **SHALL NOT** be merged without explicit approval from the designated Code Owner.

6.4  
The effective CODEOWNERS configuration is treated as a **controlled document** under this SOP.

---

### 7. Change Authorization and Review

7.1  
All changes **MUST** be introduced via a version-controlled commit.

7.2  
Commits affecting controlled paths **MUST**:

- Be authored by an identified individual
- Be cryptographically signed using OpenPGP
- Pass all mandatory status checks

7.3  
Unsigned commits are considered **non-conforming** for controlled changes.

---

### 8. Cryptographic Commit Signing (ISO 17025:2017 Clause 7.11)

8.1  
All commits linked to laboratory workflows, data handling, or compliance controls **MUST** be GPG-signed.

8.2  
The signing key **MUST**:

- Be uniquely associated with the author
- Have a defined validity period
- Be verifiable using standard Git tooling

8.3  
Verification command:

```bash
git log --show-signature

9. SOP-Linked Releases and Signed Tags

9.1
Releases associated with SOPs MUST be created using signed annotated Git tags.

9.2
Tag naming convention:

sop-<sop-id>-v<major>.<minor>


Example:

git tag -s sop-cc-001-v1.0 -m "ISO 17025 Change Control SOP v1.0"


9.3
Unsigned tags SHALL NOT be used for SOP-linked releases.

9.4
Verification command:

git tag -v sop-cc-001-v1.0

10. CI and Status Check Enforcement (ISO 17025:2017 Clause 8.5)

10.1
Protected branches MUST require successful completion of mandatory CI checks.

10.2
At minimum, the following check is required:

guardrails (GitHub Actions)

10.3
CI checks provide objective evidence that changes were validated prior to acceptance.

11. Technical Records and Audit Evidence (ISO 17025:2017 Clause 7.5)

The following artifacts constitute valid technical records:

Signed Git commits

Signed Git tags

Pull request review history

CI execution logs

CODEOWNERS file history

These records are retained indefinitely within the Git repository.

12. Nonconformities

Any of the following constitute a nonconformity:

Unsigned commit affecting controlled paths

Missing Code Owner approval

Unsigned SOP-linked release tag

Bypassing required CI checks

Nonconformities MUST be documented and corrected prior to release.

13. Revision History (Auto-derived from Signed Git Tags)

This table is derived from signed Git tags matching the SOP tag convention.

Version	Tag	Date	Description
1.0	sop-cc-001-v1.0	2025-12-25	Initial release
14. Approval and Control

This SOP is approved and controlled through:

Signed commits

Signed release tags

Enforced CODEOWNERS review

Protected branch policies

No separate signature page is required.
The Git cryptographic record is the authoritative approval.

End of Document
