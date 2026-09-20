.DEFAULT_GOAL := help

DEPLOY_FILES = ../contact-form/contact-form.bpmn ../contact-form/contact-form-start.form ../contact-form/contact-form-review.form ../contact-form/contact-form-delegated.form

.PHONY: help test deploy serve

help:
	@echo "make test|deploy|serve"

test:
	uv run --with="operaton-tasks[cli]" python -c "import tasks"

deploy:
	uv run --env-file secrets.env --with=purjo pur operaton deploy $(DEPLOY_FILES)

serve:
	uv run --env-file secrets.env --with="operaton-tasks[cli]" operaton-tasks serve tasks.py
