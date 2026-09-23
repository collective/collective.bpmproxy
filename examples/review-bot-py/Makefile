.DEFAULT_GOAL := help

.PHONY: help test serve

help:
	@echo "make test|serve"

test:
	uv run --with="operaton-tasks[cli]" python -c "import tasks"

serve:
	uv run --env-file secrets.env --with="operaton-tasks[cli]" operaton-tasks serve tasks.py
