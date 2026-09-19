.DEFAULT_GOAL := help

DEPLOY_FILES = ../renovation-project/renovation-plan-review.bpmn ../renovation-project/renovation-work-and-extra-work.bpmn ../renovation-project/renovation-final-review.bpmn

.PHONY: help lock test dist deploy serve run

help:
	@echo "make test|dist|deploy|serve|run"

lock:
	uv lock

test:
	uv run robot --dryrun tasks.robot

dist: test
	uv run --with=purjo pur wrap

deploy:
	uv run --env-file secrets.env --with=purjo pur operaton deploy $(DEPLOY_FILES)

serve:
	uv run --env-file secrets.env --with=purjo pur serve .

run:
	uv run --env-file secrets.env --with=purjo pur run $(DEPLOY_FILES)
