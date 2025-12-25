# Deployment Guide (Secure Deployment Checklist)

This document defines the **secure deployment requirements** for NARO-LIMS.
It is intended for system administrators, DevOps engineers, and auditors.

The goal is to ensure **confidentiality, integrity, availability, and auditability**
of laboratory data in production environments.

---

## Deployment Principles

All deployments MUST follow these principles:

1. Production is immutable except via versioned releases
2. Secrets are never committed to source control
3. All write paths are authenticated and authorized
4. Workflow and guardrails are enforced server-side
5. Audit logs are preserved and protected

---

## Supported Environments

| Environment | Purpose |
|------------|--------|
| Development | Local testing only |
| Staging | Pre-production validation |
| Production | Live laboratory operations |

⚠️ Production must never share credentials or databases with non-production systems.

---

## System Requirements

### Operating System
- Ubuntu LTS (20.04 or newer)
- Hardened kernel defaults
- Automatic security updates enabled

### Runtime
- Python 3.10 or newer
- Virtual environment isolation required
- Gunicorn or equivalent WSGI server

### Database
- PostgreSQL (recommended)
- SQLite allowed for development only

---

## Network Security Checklist

### Required Controls

- [ ] HTTPS enforced at all entry points
- [ ] TLS certificates from trusted CA
- [ ] HTTP redirected to HTTPS
- [ ] Reverse proxy configured (Nginx recommended)
- [ ] Firewall restricts inbound traffic to required ports only
- [ ] Database not publicly exposed

### Recommended Controls

- [ ] Private subnet for database
- [ ] Bastion host or VPN for admin access
- [ ] Rate limiting at reverse proxy
- [ ] IP allow-listing for admin interfaces

---

## Application Configuration

### Environment Variables

All sensitive configuration MUST be supplied via environment variables.

Required variables:

```bash
DJANGO_SECRET_KEY
DJANGO_SETTINGS_MODULE
DATABASE_URL
ALLOWED_HOSTS
Optional but recommended:

bash
Copy code
SECURE_PROXY_SSL_HEADER
CSRF_TRUSTED_ORIGINS
LOG_LEVEL
❌ .env files must not be committed.

Django Security Settings
Ensure the following are enabled in production:

python
Copy code
DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
Authentication & Authorization
Authentication
Token-based authentication enforced

No anonymous write access

Admin access restricted to trusted users

Authorization
Role-based access control enabled

Laboratory scoping enforced

Guardrails enforced server-side

Object-level permissions active

Workflow & Guardrails Enforcement
Before deploying to production, verify:

 Workflow transitions validated centrally

 Terminal states immutable

 Server-controlled fields protected

 Guardrail tests pass locally

 Guardrail tests enforced in CI

Run:

bash
Copy code
make guardrails
Deployment must fail if guardrails fail.

Database Security
Required
 Database user uses least privilege

 Separate roles for migration vs runtime

 SSL enabled for database connections

 Backups encrypted at rest

Recommended
 Point-in-time recovery enabled

 Backup retention policy defined

 Restore procedure tested

Audit & Logging
Audit Logs
 Audit logging enabled

 Audit APIs read-only

 Logs retained according to policy

 Logs protected from modification

Application Logs
 Authentication failures logged

 Permission denials logged

 Workflow violations logged

 Logs centralized (recommended)

Background Tasks (if enabled)
If using Celery or scheduled jobs:

 Separate worker processes

 Dedicated credentials

 Restricted permissions

 Task retries bounded

 Task logs captured

CI/CD Requirements
A deployment pipeline MUST include:

 Unit tests

 Guardrail tests

 Migration checks

 Linting (optional but recommended)

Guardrails are blocking checks, not advisory.

Deployment Procedure (Recommended)
Pull tagged release

Create isolated virtual environment

Install dependencies

Apply migrations

Run guardrail tests

Restart application services

Verify health endpoint

Verify audit logging

Post-Deployment Verification
After deployment:

 Health endpoint returns OK

 Authenticated access works

 Unauthorized access denied

 Workflow transitions validated

 Audit entries created

Rollback Strategy
A rollback plan MUST exist:

Tagged releases retained

Database backup before deployment

One-command rollback documented

Rollback tested periodically

Incident Readiness
Operators must be able to:

Disable write access if required

Rotate credentials

Revoke compromised users

Preserve audit evidence

Deployment Contract
Any deployment that:

Disables guardrails

Weakens access control

Skips audit logging

Uses DEBUG mode

Exposes secrets

Violates the deployment contract and must not proceed.

Applicability
This deployment guide applies to:

Copy code
v0.6.0-guardrails and later
All future releases must preserve these guarantees.
