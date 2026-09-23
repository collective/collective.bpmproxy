.DEFAULT_GOAL := help

DEPLOY_FILES = \
	renovation-case.bpmn \
	renovation-page-review.bpmn \
	renovation-owner-approval.form \
	renovation-inspector-approval.form

.PHONY: help lock test dist deploy serve run

help:
	@echo "make test|dist|deploy|serve|run"

lock:
	uv lock

test: $(DEPLOY_FILES)
	@echo "All renovation process assets are present."

dist: test
	uv run --with=purjo pur wrap

deploy:
	uv run --env-file secrets.env --with=purjo pur operaton deploy $(DEPLOY_FILES)

serve:
	uv run --env-file secrets.env --with=purjo pur serve .

run:
	uv run --env-file secrets.env --with=purjo pur run $(DEPLOY_FILES)
