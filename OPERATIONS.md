# Operations Manual – NARO-LIMS

This document defines **day-to-day operational procedures** for running NARO-LIMS in production.

It covers:
- Backups
- Monitoring
- Log management
- Routine checks
- Incident response
- Safe upgrades
- Guardrails enforcement in operations

This is an **operations contract**, not developer documentation.

---

## Operational Principles

NARO-LIMS operations follow five non-negotiable principles:

1. **Data integrity over convenience**
2. **Auditability over silent recovery**
3. **Fail fast on violations**
4. **Explicit ownership of actions**
5. **Repeatable, documented procedures**

If an operation cannot be explained, reproduced, and audited, it is invalid.

---

## Service Overview

Core services:

- Django application (Gunicorn)
- PostgreSQL database
- Nginx reverse proxy
- systemd service manager

Optional:
- Celery + Redis (if enabled)
- External monitoring (Prometheus, UptimeRobot)

---

## Health Monitoring

### Application Health Endpoint

```bash
curl https://narolims.example.org/lims/health/
Expected response:

{
  "status": "ok",
  "service": "NARO-LIMS",
  "laboratory": {
    "id": 1,
    "code": "LAB1",
    "name": "Central Lab",
    "institute": "NARO"
  }
}


If this endpoint fails, do not assume partial availability.
Systemd Service Status
sudo systemctl status narolims
Indicators:

active (running) is mandatory

Any restart loop indicates misconfiguration

Logging Strategy
Log Locations

Recommended structure:

/opt/narolims/logs/
├── django.log
├── gunicorn.log
├── audit.log
└── nginx/


Django logs must include:

Timestamp

User

Laboratory

Action

Object ID

Viewing Logs
sudo journalctl -u narolims -n 100


For live tail:

sudo journalctl -u narolims -f

Log Rotation

Use logrotate:

sudo nano /etc/logrotate.d/narolims

/opt/narolims/logs/*.log {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    copytruncate
}

Database Operations
Backup Strategy (Mandatory)

Backups must be:

Automated

Verified

Stored off-server

Daily Backup (Recommended)
pg_dump narolims | gzip > narolims_$(date +%F).sql.gz


Automate via cron:

crontab -e

0 2 * * * pg_dump narolims | gzip > /backups/narolims_$(date +\%F).sql.gz

Backup Verification

At least once per month:

gunzip -c narolims_YYYY-MM-DD.sql.gz | psql test_restore


An untested backup is not a backup.

Guardrails in Operations
Mandatory Before Any Change

Before any of the following:

Code deployment

Configuration change

Migration

Permission adjustment

Run:

make guardrails


If guardrails fail:

Do not restart

Do not deploy

Do not hot-fix

Guardrails Scope

Guardrails protect:

Workflow transitions

Immutable fields

Permission boundaries

Status machines

If guardrails fail in production, treat it as a severity-1 incident.

Incident Response
Severity Levels
Level	Description
S1	Data integrity at risk
S2	Workflow blocked
S3	Partial service degradation
S4	Cosmetic / non-blocking
S1 Incident Procedure

Freeze write access

Preserve logs

Identify offending request

Roll back to last tagged release

Document incident

Never “fix forward” silently.

User & Permission Audits
Monthly Audit

Run:

python manage.py shell


Review:

Users without roles

Roles across multiple laboratories

Staff without institutes

Every role assignment must be justifiable.

Workflow Integrity Checks

Periodically validate workflow history:

SELECT kind, from_status, to_status, COUNT(*)
FROM lims_core_workflowtransition
GROUP BY kind, from_status, to_status;


Any unexpected transition indicates a breach.

Disk & Resource Monitoring

Monitor:

Disk usage (df -h)

Database size

Log growth

CPU saturation

Django slowdown is often disk or DB related, not application logic.

Safe Restart Procedure
sudo systemctl stop narolims
sudo systemctl start narolims
sudo systemctl status narolims


Never restart repeatedly without diagnosis.

Emergency Read-Only Mode

If integrity is in question:

Disable write routes at Nginx level

Or revoke write roles temporarily

Protect data first, explain later.

Upgrade Validation Checklist

Before upgrade:

Database backup verified

Guardrails passing

Release tag exists

After upgrade:

Health check OK

Guardrails still passing

Sample workflow tested

Operational Ownership

Every deployment must have:

Named operator

Timestamp

Git commit hash

Outcome recorded

Undocumented operations are treated as failures.


Final Statement

NARO-LIMS is national research infrastructure.

Operations discipline is not optional.
