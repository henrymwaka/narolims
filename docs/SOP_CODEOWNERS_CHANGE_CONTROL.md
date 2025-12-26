---
document_id: NARO-LIMS-SOP-IT-CC-001
title: Software Change Control and Authorization Using CODEOWNERS
document_type: Standard Operating Procedure
system: NARO Laboratory Information Management System (NARO-LIMS)
version: "1.0"
status: Approved
owner: Software Quality and Systems Governance
approved_by: Laboratory Management
effective_date: YYYY-MM-DD
review_date: YYYY-MM-DD
classification: Controlled Document
confidentiality: Internal
iso_standard: ISO/IEC 17025:2017
related_documents:
  - CODEOWNERS
  - GUARDRAILS.md
  - SECURITY.md
  - OPERATIONS.md
  - DEPLOYMENT.md
keywords:
  - change control
  - software governance
  - code review
  - audit trail
  - ISO 17025
repository: https://github.com/henrymwaka/narolims
---
## Revision History

> This table is auto-generated from Git release tags.
> Each version corresponds to a signed Git tag in the NARO-LIMS repository.
> Manual edits to this table are not permitted.

| Version | Release Date | Git Tag | Description | Approved By |
|--------:|--------------|---------|-------------|-------------|
<!-- REVISION_HISTORY_START -->
<!-- REVISION_HISTORY_END -->


## Release Integrity and Tag Signing Policy

All releases that modify or govern controlled documents, guardrails, workflows,
permissions, or security posture **must be associated with a cryptographically
signed Git tag**.

Unsigned tags are not considered valid releases for SOP-linked changes and are
not permitted for production deployment.

Signed tags provide:
- Authorship verification
- Change non-repudiation
- Tamper evidence
- ISO/IEC 17025 compliant traceability

This requirement applies to:
- SOPs
- Guardrail definitions
- Workflow engines
- Permissions and access control
- CI/CD enforcement logic

# SOP: Software Change Control and Authorization Using CODEOWNERS


**SOP ID:** NARO-LIMS-SOP-IT-CC-001  
**Version:** 1.0  
**Status:** Approved  
**Effective Date:** YYYY-MM-DD  
**Review Date:** YYYY-MM-DD  
**System:** NARO Laboratory Information Management System (NARO-LIMS)

---

## 1. Purpose

This Standard Operating Procedure (SOP) defines the process for controlling,
reviewing, authorizing, and approving software changes within the NARO-LIMS
repository using the CODEOWNERS mechanism.

The objective is to ensure that all changes affecting laboratory operations,
workflows, data integrity, security, and compliance are reviewed and approved
by designated competent personnel, in alignment with ISO/IEC 17025:2017.

---

## 2. Scope

This SOP applies to all software assets maintained within the NARO-LIMS
repository, including:

- Core application logic
- Workflow engines and state transition rules
- Access control and permission logic
- Database schema and migrations
- Continuous integration and deployment configuration
- Security, deployment, and operational documentation
- Automated test suites and guardrail enforcement

This SOP applies to all personnel who develop, review, approve, or deploy changes
to NARO-LIMS.

---

## 3. Normative References

- ISO/IEC 17025:2017  
  - Clause 6.2 — Personnel  
  - Clause 6.4 — Equipment and software  
  - Clause 7.11 — Control of data and information management  
  - Clause 8.3 — Control of management system documents  
  - Clause 8.5 — Actions to address risks and opportunities  

- NARO-LIMS `CODEOWNERS` file  
- NARO-LIMS `GUARDRAILS.md`  
- NARO-LIMS Software Architecture Documentation

---

## 4. Definitions

**CODEOWNERS**  
A repository configuration file that assigns review and approval responsibility
for specific files or directories to designated individuals.

**Code Owner**  
A competent individual designated in the CODEOWNERS file who is responsible for
reviewing and approving changes to assigned components.

**Considered Change**  
Any modification, addition, or deletion of software code, configuration,
documentation, or automation scripts within the NARO-LIMS repository.

**Pull Request (PR)**  
A formal request to merge proposed changes into a protected branch.

---

## 5. Roles and Responsibilities

### 5.1 Code Owner

The Code Owner shall:

- Review proposed changes affecting assigned components
- Verify technical correctness and alignment with laboratory workflows
- Assess risks to data integrity, traceability, and compliance
- Approve or reject changes via the version control system

### 5.2 Developers

Developers shall:

- Submit all changes through pull requests
- Ensure changes are traceable to requirements or corrective actions
- Address review comments raised by Code Owners

### 5.3 System Administrator / Quality Manager

The System Administrator or Quality Manager shall:

- Maintain the CODEOWNERS file
- Ensure enforcement of review and approval rules
- Retain approval records as objective evidence for audits

---

## 6. Procedure

### 6.1 Change Initiation

1. All changes shall be initiated via a pull request.
2. Direct commits to protected branches are prohibited.

---

### 6.2 Change Classification

Changes are classified by risk:

- **High risk:** workflows, permissions, database schema, CI/CD
- **Medium risk:** tests, operational documentation
- **Low risk:** non-functional documentation

Ownership and approval authority are defined in the CODEOWNERS file.

---

### 6.3 Assignment of Review Responsibility

1. Reviewers are automatically assigned based on CODEOWNERS rules.
2. At least one designated Code Owner must approve the change.
3. Where multiple rules apply, the most specific rule takes precedence.

---

### 6.4 Review and Approval

Code Owners shall verify:

- Technical correctness
- Compliance with laboratory processes
- Impact on data integrity and traceability
- Alignment with ISO/IEC 17025 requirements

Approval is recorded electronically and retained as objective evidence.

---

### 6.5 Automated Verification

1. All pull requests shall pass automated checks, including:
   - Guardrail tests
   - Workflow validation
2. Failure of required checks blocks merging.
3. Automated checks do not replace Code Owner approval.

---

### 6.6 Merge and Deployment

1. Only approved pull requests may be merged.
2. Deployment follows the approved CI/CD process.
3. All deployed changes remain traceable to an approved pull request.

---

## 7. Records and Evidence

The following constitute objective evidence:

- Pull request history
- CODEOWNERS file revision history
- Review and approval records
- CI and guardrail test results

Records are retained per the laboratory document control policy.

---

## 8. Risk Management and Nonconformities

Failure to comply with this SOP may result in:

- Unauthorized software changes
- Compromised data integrity
- Nonconformity with ISO/IEC 17025

Such events shall be handled under the corrective action process.

---

## 9. Review and Maintenance

This SOP shall be reviewed:

- Annually
- Following significant system changes
- Following audit findings

Revisions require formal approval.

---

## 10. Approval

| Name | Title | Date |
|-----|------|------|
|     |      |      |

---

**End of Document**
