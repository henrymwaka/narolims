# Contributing to NARO-LIMS

Thank you for your interest in contributing to **NARO-LIMS**.  
This project is developed to support laboratory operations, traceability, and governance in regulated research environments. Contributions are welcome, but must follow strict technical and governance standards.

---

## Scope of Contributions

We welcome contributions in the following areas:

- Core Django application logic (`lims_core`)
- Workflow engines and guardrails
- API extensions and serializers
- Documentation and architecture diagrams
- Tests (unit, integration, guardrails)
- CI/CD improvements
- Performance, reliability, and security hardening

We **do not** accept speculative features that bypass workflow enforcement, auditability, or laboratory scoping.

---

## Development Principles

All contributions must respect the following principles:

1. **Server-authoritative logic**
   - Business rules live on the server, not the client.
2. **Immutability where required**
   - Certain fields must never be modified after creation.
3. **Auditability**
   - All state-changing operations must be traceable.
4. **Least privilege**
   - Permissions must be explicit and role-based.
5. **Test-first guardrails**
   - Guardrails are enforced by tests, not convention.

---

## Local Development Setup

```bash
git clone https://github.com/henrymwaka/narolims.git
cd narolims
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py test
Guardrails Enforcement

This repository enforces pre-commit guardrails.

Before every commit, the following must pass:

Workflow transition tests

Write-guardrail tests

Django system checks

If guardrails fail, the commit is rejected.

Run manually:

make guardrails

Branching Model

main – stable, protected

feature/* – feature development

fix/* – bug fixes

docs/* – documentation only

All changes must go through a Pull Request.

Pull Request Requirements

A PR must include:

Clear description of the change

Tests covering new or modified behavior

Documentation updates if behavior changes

No failing CI checks

PRs that weaken guardrails or bypass permissions will be rejected.

Code Style

Follow Django and DRF best practices

Prefer explicit logic over magic

Avoid hidden side effects

Use meaningful variable and function names

Governance

Final approval of architectural changes rests with the project maintainer.
This is a regulated-environment system, not a generic CRUD app.

Thank you for helping improve NARO-LIMS responsibly.
