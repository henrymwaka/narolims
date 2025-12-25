# LIMS Makefile (CI-safe, venv-agnostic)

PYTHON ?= python3
MANAGE := $(PYTHON) manage.py

.PHONY: check migrate guardrails test

check: migrate guardrails

migrate:
	@echo "Running migrations..."
	$(MANAGE) migrate --noinput

guardrails:
	@echo "Running LIMS guardrail tests..."
	$(MANAGE) test \
		lims_core.tests.test_status_workflows \
		lims_core.tests.test_write_guardrails

test: check
