.PHONY: test-workflows test-fast test

test-workflows:
	pytest -q lims_core/tests/test_workflows_hardening.py

test-fast:
	pytest -q --maxfail=1

test:
	pytest -q
