# Backend test/dev shortcuts. Run from backend/ (or `make -C backend <target>`).
PY := .venv/bin/python

.PHONY: test smoketest3 test-v cov smoke install-dev

## install-dev: install test/dev dependencies into the venv
install-dev:
	$(PY) -m pip install -r requirements-dev.txt

## test: run the full pytest suite (offline, no API spend)
test:
	$(PY) -m pytest

## smoketest3: run the named canonical collection (== the full suite)
smoketest3:
	$(PY) -m pytest -m smoketest3

## test-v: verbose run (lists each test)
test-v:
	$(PY) -m pytest -v

## cov: coverage report (requires `pip install pytest-cov`)
cov:
	$(PY) -m pytest --cov=app --cov-report=term-missing

## smoke: the standalone offline smoke script (parse→render→commit→review)
smoke:
	PYTHONPATH=. $(PY) tests/smoke.py
