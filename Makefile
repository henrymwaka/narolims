PYTHON ?= python3
MANAGE := $(PYTHON) manage.py

.PHONY: guardrails test

guardrails:
	@echo "Running LIMS guardrail tests..."
	$(MANAGE) test \
		lims_core.tests.test_status_workflows \
		lims_core.tests.test_write_guardrails

test: guardrails
