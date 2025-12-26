.
├── ARCHITECTURE.md
├── ARCHITECTURE_WORKFLOWS.md
├── bootstrap_narolims.sh
├── CHANGELOG.md
├── check_narolims.sh
├── CONTRIBUTING.md
├── db.sqlite3
├── DEPLOYMENT.md
├── directory_structure.md
├── docs
│   ├── ARCHITECTURE.md
│   ├── ARCHITECTURE_WORKFLOWS.md
│   ├── SOP-CHANGE-CONTROL.md
│   └── SOP_CODEOWNERS_CHANGE_CONTROL.md
├── .env
├── .github
│   ├── CODEOWNERS
│   └── workflows
│       ├── ci.yml
│       └── verify-signed-tags.yml
├── .gitignore
├── GUARDRAILS.md
├── lims_core
│   ├── admin.py
│   ├── apps.py
│   ├── filters.py
│   ├── __init__.py
│   ├── management
│   │   └── commands
│   │       └── check_sla_breaches.py
│   ├── middleware.py
│   ├── migrations
│   │   ├── 0001_initial.py
│   │   ├── 0002_alter_auditlog_options_alter_experiment_options_and_more.py
│   │   ├── 0003_institute_alter_sample_sample_type_laboratory_and_more.py
│   │   ├── 0004_backfill_default_laboratory.py
│   │   ├── 0005_staffmember_alter_auditlog_options_and_more.py
│   │   ├── 0006_workflowtransition.py
│   │   ├── 0007_workflowevent.py
│   │   ├── 0008_workflowalert.py
│   │   ├── 0009_alter_experiment_status_alter_sample_status.py
│   │   └── __init__.py
│   ├── mixins.py
│   ├── models
│   │   ├── core.py
│   │   ├── __init__.py
│   │   ├── workflow_alert.py
│   │   └── workflow_event.py
│   ├── models_workflow_alerts.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── serializers_workflow.py
│   ├── services
│   │   ├── workflow_bulk.py
│   │   ├── workflow.py
│   │   └── workflow_service.py
│   ├── signals.py
│   ├── static
│   │   └── lims_core
│   │       ├── css
│   │       ├── js
│   │       ├── workflow.css
│   │       └── workflow.js
│   ├── tasks.py
│   ├── templates
│   │   ├── lims
│   │   │   └── workflow_definition.html
│   │   ├── lims_core
│   │   │   ├── base.html
│   │   │   ├── experiments
│   │   │   ├── samples
│   │   │   └── workflow_widget.html
│   │   └── workflows
│   │       └── workflow_widget.html
│   ├── tests
│   │   ├── conftest.py
│   │   ├── __init__.py
│   │   ├── test_bulk_workflow_transitions.py
│   │   ├── test_status_workflows.py
│   │   ├── test_terminal_lock.py
│   │   ├── test_visibility.py
│   │   ├── test_workflow_allowed.py
│   │   ├── test_workflow_transitions.py
│   │   └── test_write_guardrails.py
│   ├── urls.py
│   ├── views_identity.py
│   ├── views.py
│   ├── views_ui.py
│   ├── views_workflow_api.py
│   ├── views_workflow_bulk.py
│   ├── views_workflow_metrics.py
│   ├── views_workflow_runtime.py
│   ├── views_workflows.py
│   ├── views_workflows_ui.py
│   ├── workflows
│   │   ├── executor.py
│   │   ├── guards.py
│   │   ├── __init__.py
│   │   ├── metrics.py
│   │   ├── rules.py
│   │   ├── sla_monitor.py
│   │   ├── sla.py
│   │   ├── sla_resolver.py
│   │   ├── sla_scanner.py
│   │   ├── transition_rules.py
│   │   └── WORKFLOW_MATRIX.md
│   └── workflows.py
├── Makefile
├── manage.py
├── naro_lims
│   ├── admin.py
│   ├── asgi.py
│   ├── celery.py
│   ├── __init__.py
│   ├── pagination.py
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   └── wsgi.py
├── NARO_LIMS_SYSTEM_CHARTER.md
├── OPERATIONS.md
├── pytest.ini
├── README.md
├── RELEASE_NOTES
│   └── v0.6.0-guardrails.md
├── RELEASE_NOTES.md
├── requirements.txt
├── scripts
│   └── update_revision_history.sh
├── SECURITY.md
├── static
└── .venv
    ├── bin
    │   ├── activate
    │   ├── activate.csh
    │   ├── activate.fish
    │   ├── Activate.ps1
    │   ├── django-admin
    │   ├── gunicorn
    │   ├── jsonschema
    │   ├── pip
    │   ├── pip3
    │   ├── pip3.10
    │   ├── python -> python3
    │   ├── python3 -> /usr/bin/python3
    │   ├── python3.10 -> python3
    │   └── sqlformat
    ├── include
    ├── lib
    │   └── python3.10
    │       └── site-packages
    ├── lib64 -> lib
    └── pyvenv.cfg

32 directories, 121 files
