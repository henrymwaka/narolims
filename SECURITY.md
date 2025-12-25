# Security Policy

## Overview

NARO-LIMS is designed for use in regulated laboratory and research environments.  
Security, data integrity, and access control are core design requirements.

---

## Supported Versions

Only actively maintained branches and tagged releases receive security updates.

| Version | Supported |
|-------|-----------|
| main  | ✅ |
| tagged releases | ✅ |
| feature branches | ❌ |

---

## Reporting a Vulnerability

If you discover a security issue, **do not open a public issue**.

Instead, report responsibly by contacting:

**Maintainer:**  
Henry Mwaka  
GitHub: https://github.com/henrymwaka

Include:
- Description of the vulnerability
- Steps to reproduce
- Affected components
- Suggested mitigation if available

---

## Security Design Guarantees

NARO-LIMS enforces the following security guarantees:

- Role-based access control (RBAC)
- Laboratory-scoped data isolation
- Immutable server-controlled fields
- Workflow state machines with validation
- Audit logging for state-changing operations
- Guardrail tests preventing regression

---

## Authentication & Authorization

- Authentication via Django authentication framework
- Authorization enforced at:
  - Permission class level
  - View level
  - Workflow execution layer
- No trust is placed in client-side state

---

## Data Protection

- No destructive deletes for workflow artifacts
- SLA and alert records are preserved
- Duration and state changes are computed server-side

---

## Dependency Management

Dependencies are monitored via CI.  
Security updates should be applied promptly and tested before release.

---

## Incident Response

In case of confirmed compromise:

1. Revoke affected credentials
2. Audit access logs
3. Patch and test fixes
4. Issue a security release
5. Notify affected stakeholders where applicable

---

Security is not optional in this project.  
It is enforced by design and by tests.
