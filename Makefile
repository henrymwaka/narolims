# ============================
# NARO LIMS – CI-safe Makefile
# ============================

PYTHON ?= python
MANAGE := $(PYTHON) manage.py

.PHONY: guardrails test migrate check

guardrails:
	@echo "Running LIMS guardrail tests..."
	$(MANAGE) test \
		lims_core.tests.test_status_workflows \
		lims_core.tests.test_write_guardrails

migrate:
	@echo "Running database migrations..."
	$(MANAGE) migrate --noinput

test: guardrails

check: migrate guardrails
