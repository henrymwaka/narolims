# Security Policy

## Overview

NARO-LIMS is a laboratory information management system designed for regulated research environments.  
Security is treated as a **first-class system requirement**, not an afterthought.

This document defines the **threat model**, **access control architecture**, **audit posture**, and **security responsibilities** governing the platform.

---

## Security Objectives

The primary security objectives of NARO-LIMS are:

1. **Prevent unauthorized data access**
2. **Prevent unauthorized state changes**
3. **Ensure traceability of all critical actions**
4. **Minimize blast radius of compromised accounts**
5. **Support institutional audits and incident response**

---

## Threat Model

### Assets Protected

- Experimental data
- Sample metadata
- Workflow state transitions
- User roles and laboratory affiliations
- Audit records

### Threat Actors

| Actor | Risk |
|-----|-----|
| External attacker | Credential theft, API probing |
| Insider with limited role | Privilege escalation |
| Compromised user account | Unauthorized data manipulation |
| Accidental misuse | Invalid workflow progression |
| Misconfigured client | Silent data corruption |

---

### Threat Scenarios & Mitigations

#### 1. Unauthorized Workflow State Changes
**Threat:** User attempts to skip required workflow steps  
**Mitigation:**  
- Centralized workflow engine
- Explicit transition validation
- Terminal state enforcement

#### 2. Privilege Escalation
**Threat:** User attempts to mutate protected fields (laboratory, institute, creator)  
**Mitigation:**  
- Immutable field guardrails
- Permission-level enforcement (403)
- Serializer-level validation (400)

#### 3. Cross-Laboratory Data Leakage
**Threat:** User accesses data outside permitted laboratory  
**Mitigation:**  
- Mandatory laboratory scoping
- Queryset filtering
- Explicit lab resolution

#### 4. Silent Data Corruption
**Threat:** Client sends unexpected fields  
**Mitigation:**  
- Fail-closed validation
- Explicit error responses
- No implicit coercion

#### 5. Audit Log Tampering
**Threat:** Malicious deletion or modification of logs  
**Mitigation:**  
- Append-only audit model
- Read-only API exposure
- No client-side write access

---

## Access Control Model

### Authentication

- Django authentication framework
- Token-based API access
- No anonymous write access

All write operations require authenticated users.

---

### Authorization

Authorization is enforced at **three levels**:

#### 1. Request-Level Permissions
- Enforced via DRF permission classes
- Blocks unauthorized write attempts early

#### 2. Object-Level Permissions
- Enforced per laboratory and per role
- Prevents cross-scope access

#### 3. Workflow-Level Permissions
- Certain transitions require elevated roles
- Terminal states are immutable regardless of role

---

### Role Model

| Role | Capabilities |
|----|----|
| Technician | Operational data entry |
| Data Manager | Data corrections, oversight |
| Lab Manager | Administrative control |
| PI | Full laboratory authority |
| Superuser | Platform-level administration |

Roles are **laboratory-scoped**.  
There is no global implicit authority.

---

## Guardrails as a Security Control

Guardrails are treated as **security boundaries**, not UX features.

### Guardrail Types

- Immutable field enforcement
- Server-controlled field ownership
- Workflow transition validation
- Permission-first denial semantics

Violations result in **explicit failure**, never silent correction.

---

## Audit & Traceability Posture

### Audit Coverage

The following events are audited:

- Workflow state transitions
- Creation of critical entities
- Permission-sensitive updates
- Administrative actions

### Audit Guarantees

- Audit logs are append-only
- Audit records are immutable
- Audit APIs are read-only
- Each record is attributable to a user and time

### Intended Use

Audit logs support:

- Internal reviews
- Regulatory audits
- Incident investigations
- Forensic reconstruction

---

## Logging & Monitoring

### Application Logs

- Authentication failures
- Permission denials
- Workflow validation failures
- System errors

### Recommendations

Operators should:
- Centralize logs
- Enable alerting on repeated failures
- Monitor privilege-denied patterns

---

## Secure Development Practices

- Centralized business logic
- Explicit error semantics
- No duplicated workflow rules
- Defense-in-depth validation
- Mandatory tests for security-critical behavior

Security-related behavior is covered by automated tests and enforced via CI.

---

## Vulnerability Disclosure

### Reporting a Vulnerability

If you discover a security issue:

- Do **not** open a public issue
- Do **not** exploit the vulnerability

Instead, contact:

developers@reslab.dev

Include:
- Description of the issue
- Steps to reproduce
- Potential impact

---

### Response Commitment

- Issues will be acknowledged within 72 hours
- Fixes will be prioritized based on severity
- Coordinated disclosure will be practiced

---

## Supported Versions

Security fixes are applied to:

- The current stable release
- The latest guardrail-enforced version

Older releases may not receive patches.

---

## Security Status

This security policy applies as of:


v0.6.0-guardrails

All future changes must preserve or strengthen these guarantees.

---

## Security Contract

Any change that:

- Weakens access control
- Bypasses workflow enforcement
- Introduces silent behavior
- Undermines auditability

**Violates the security contract** and must not be merged.
