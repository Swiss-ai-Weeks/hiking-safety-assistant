PY=.venv/bin/python
test:
	$(PY) -m pytest
live:
	LIVE=1 $(PY) -m pytest -m live
coverage-gate:
	$(PY) -m hsa.gate.coverage_gate
run:
	$(PY) -m uvicorn hsa.api.app:app --reload --port 8000
