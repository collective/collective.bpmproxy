.DEFAULT_GOAL := help

DEPLOY_FILES = ../empire-insider/FromIdeaToArticle.bpmn

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
	uv run --with=purjo pur operaton deploy $(DEPLOY_FILES)

serve:
	uv run --with=purjo pur serve .

run:
	uv run --with=purjo pur run $(DEPLOY_FILES)
