.DEFAULT_GOAL := help

DEPLOY_FILES = review-process.bpmn review-select-reviewers.form review-submit.form review-decision.form

.PHONY: help lock test dist deploy serve run

help:
	@echo "make test|dist|deploy|serve|run"

lock:
	uv lock

test: $(DEPLOY_FILES)
	@echo "All review process assets are present."

dist: test
	uv run --with=purjo pur wrap

deploy:
	uv run --env-file secrets.env --with=purjo pur operaton deploy $(DEPLOY_FILES)

serve:
	uv run --env-file secrets.env --with=purjo pur serve .

run:
	uv run --env-file secrets.env --with=purjo pur run $(DEPLOY_FILES)
