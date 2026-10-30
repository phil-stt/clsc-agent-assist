PY := .venv/bin/python
PYTHON ?= python3.12

.PHONY: setup dev test graph extract scrub

setup: .venv/.installed

.venv/.installed: requirements.txt
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -q -r requirements.txt
	touch $@

dev: setup graph
	$(PY) -m uvicorn app.main:app --reload --port 8000

test: setup
	$(PY) -m pytest -q

graph: setup
	$(PY) -m knowledge.graph

extract: setup
	$(PY) -m knowledge.extract

scrub:
	scripts/scrub.sh
