# NARO-LIMS SYSTEM CHARTER  
**National Agricultural Research Organisation – Laboratory Information Management System**

**Document ID:** NARO-LIMS-SC  
**Version:** 1.0  
**Status:** Authoritative  
**Scope:** System-wide  
**Change Control:** Restricted  

---

## 1. Mandate and Authority

NARO-LIMS is the official laboratory information management platform intended to serve laboratories operating under the National Agricultural Research Organisation (NARO), beginning with the National Agricultural Research Laboratories (NARL).

This charter defines the non-negotiable principles, scope, and governance rules of NARO-LIMS. It constitutes the highest-level technical and conceptual authority for the system.

All implementation decisions, present and future, must align with this document.

---

## 2. Purpose of the System

The purpose of NARO-LIMS is to provide a single, authoritative, and auditable digital system of record for laboratory samples and associated laboratory activities within NARO.

The system exists to:
- Preserve scientific traceability  
- Protect sample integrity  
- Support institutional accountability  
- Enable reproducibility of laboratory work  
- Strengthen long-term institutional memory  

NARO-LIMS is not designed for short-term project tracking or informal laboratory note-taking. It is designed for institutional permanence.

---

## 3. Problem Statement

Laboratories within NARO currently rely on fragmented information systems, including spreadsheets, notebooks, emails, and personal databases. This fragmentation results in:
- Loss of sample lineage  
- Inconsistent record keeping  
- Weak auditability  
- Difficulty in cross-laboratory collaboration  
- Institutional knowledge loss during staff transitions  

NARO-LIMS addresses these challenges by establishing a shared, controlled, and enforceable digital backbone for laboratory information.

---

## 4. Core Design Philosophy

### 4.1 Sample-centric truth

The sample is the primary unit of truth in NARO-LIMS.

All other entities, including assays, results, reagents, instruments, workflows, and reports, exist only in relation to a sample.

There is no concept of a result, activity, or record that is not traceable to a sample.

---

### 4.2 Canonical lifecycle enforcement

Every sample in NARO-LIMS must follow a defined and explicit lifecycle.

Lifecycle transitions:
- Are intentional  
- Are forward-only  
- Are governed by explicit rules  
- Cannot be bypassed silently  

Terminal lifecycle states are immutable by design.

---

### 4.3 Guardrails before convenience

System integrity takes precedence over user convenience.

NARO-LIMS prioritizes:
- Write protection  
- State validation  
- Explicit state transitions  
- Test-verified enforcement  

User interfaces, automation, and bulk operations are layered only after guardrails are proven.

---

### 4.4 Institutional longevity

NARO-LIMS is designed to remain valid across:
- Decades of laboratory work  
- Changes in personnel  
- Shifts in research priorities  
- Gradual expansion of institutional scope  

Short-term optimizations must never compromise long-term validity.

---

### 4.5 Incremental extensibility

New functional domains may be added only if they:
- Respect the sample-centric model  
- Preserve lifecycle guarantees  
- Do not weaken auditability or traceability  

Feature completeness is not a prerequisite for initial deployment.

---

## 5. System Scope

### 5.1 In scope

NARO-LIMS is responsible for:
- Sample registration and unique identification  
- Sample lifecycle management  
- Controlled and validated status transitions  
- User authentication and role-based access control  
- Institutional traceability  
- Audit-ready data structures  
- Long-term data retention  

---

### 5.2 Explicitly out of scope (initially)

The following are not core requirements of NARO-LIMS v1.x:
- Direct laboratory instrument control  
- High-throughput automation engines  
- Financial billing or accounting systems  
- Full electronic laboratory notebook replacement  

These capabilities may be integrated later but are not foundational.

---

## 6. Canonical Sample Lifecycle (Conceptual)

NARO-LIMS recognizes a single authoritative sample lifecycle, conceptually comprising:

1. Registered  
2. Received  
3. Prepared  
4. In analysis  
5. Completed  
6. Archived (immutable)  
7. Disposed or destroyed (immutable)  

Lifecycle rules:
- Lifecycle states are explicit and enumerable  
- Transitions are controlled and validated  
- Terminal states are write-locked  
- Historical states remain traceable  

Implementation details are defined outside this charter, but the conceptual lifecycle is fixed.

---

## 7. Governance Principles

### 7.1 Single system of record

For any sample tracked in NARO-LIMS, the system constitutes the authoritative source of truth.

External records may exist but do not supersede NARO-LIMS.

---

### 7.2 Controlled change

Changes to:
- Core lifecycle rules  
- Sample immutability guarantees  
- Audit and traceability principles  

Require:
- Explicit versioning  
- Documented justification  
- Formal alignment with this charter  

---

### 7.3 No silent mutation

Data that affects scientific interpretation, traceability, or institutional accountability must never be silently altered.

Corrections must be:
- Explicit  
- Attributable  
- Fully traceable  

---

## 8. Relationship to Standards and Compliance

NARO-LIMS is designed to be compatible with, but not limited to:
- ISO/IEC 17025 principles  
- Research data integrity best practices  
- FAIR data concepts where applicable  

Formal certification or compliance alignment is considered an extension, not a prerequisite.

---

## 9. Intended Users

Primary users of NARO-LIMS include:
- Laboratory technicians  
- Laboratory scientists  
- Laboratory managers  
- Institutional administrators  

User interfaces may vary by role, but data integrity rules apply uniformly.

---

## 10. Success Criteria

NARO-LIMS is considered successful when:
- Samples cannot be lost digitally  
- Sample histories are reconstructable years later  
- Illegal data states are technically impossible  
- Institutional audits are supported by system design  
- New laboratories can be onboarded without system redesign  

---

## 11. Relationship to Other Documents

This charter is supported by:
- Technical baseline documentation  
- Status and roadmap documentation  
- Domain-specific appendices  

No supporting document may contradict this charter.

---

## 12. Change Management

This document changes rarely.

Revisions require:
- A version increment  
- Clear technical and institutional rationale  
- Explicit acknowledgment of downstream impact  

---

**End of Charter – Version 1.0**
