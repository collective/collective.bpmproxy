SOURCES = $(shell find . -name "*.java" -or -name "*.xml" -or -name "*.yaml")

NIX_OPTIONS ?= --accept-flake-config

VERSION := 2.1.0
PLUGINS_REPO ?= https://github.com/datakurre/operaton-cockpit-plugins
PLUGINS_REF ?= main

.PHONY: all
all: artifact

.PHONY: build
build: $(SOURCES)
	nix build $(NIX_OPTIONS)

.PHONY: test
test:
	mvn -Dmaven.repo.local=/workspace/collective.bpmproxy/tmp/.m2/repository test

.PHONY: start
start:
	mvn spring-boot:run

.PHONY: watch
watch: start

.PHONY: clean
clean:
	$(RM) $(ARTIFACT_NAME)-*.tar.*

.PHONY: dist
dist:
	nix build --json .#image|jq -r .[0].outputs.out|sh|podman load -q
	podman tag localhost/plone-operaton-app:latest datakurre/plone-operaton:$(VERSION)
	podman tag localhost/plone-operaton-app:latest datakurre/plone-operaton:latest

.PHONY: push
push: dist
	podman push datakurre/plone-operaton:$(VERSION)
	podman push datakurre/plone-operaton:latest

.PHONY: shell
	nix develop

###

mvn2nix-lock.json: pom.xml
	mvn2nix -vvv > mvn2nix-lock.json

###

.PHONY: nix-%
nix-%:
	@echo "run inside nix devShell: $*"
	nix develop $(NIX_OPTIONS) --command $(MAKE) $*

.PHONY: fetch-plugins
fetch-plugins:
	set -eu; \
	tmp=$$(mktemp -d); \
	trap 'rm -rf "$$tmp"' EXIT; \
	curl -fsSL --retry 3 $(PLUGINS_REPO)/archive/refs/heads/$(PLUGINS_REF).tar.gz \
		| tar -xz --strip-components=1 -C "$$tmp"; \
	for app in cockpit admin tasklist welcome; do \
		mkdir -p "src/main/resources/META-INF/resources/webjars/operaton/app/$$app/scripts" \
			"src/main/resources/app/$$app/scripts"; \
	done; \
	for file in \
		cockpit-custom-styles.js dashboard-favourites.js dashboard-integrations.js \
		definition-historic-activities.js definition-tab-modify.js \
		instance-auto-refresh.js instance-action-unlock.js \
		instance-historic-activities.js instance-route-history.js \
		instance-tab-modify.js robot-module.js; do \
		cp "$$tmp/$$file" \
			"src/main/resources/META-INF/resources/webjars/operaton/app/cockpit/scripts/$$file"; \
		cp "$$tmp/$$file" "src/main/resources/app/cockpit/scripts/$$file"; \
	done; \
	cp "$$tmp/config.js" \
		src/main/resources/META-INF/resources/webjars/operaton/app/cockpit/scripts/config.js; \
	cp "$$tmp/config.js" src/main/resources/app/cockpit/scripts/config.js; \
	for pair in \
		"admin-route-authorization.js admin" \
		"admin-custom-styles.js admin" \
		"tasklist-audit-log.js tasklist" \
		"tasklist-custom-styles.js tasklist" \
		"welcome-custom-styles.js welcome"; do \
		set -- $$pair; \
		cp "$$tmp/$$1" \
			"src/main/resources/META-INF/resources/webjars/operaton/app/$$2/scripts/$$1"; \
		cp "$$tmp/$$1" "src/main/resources/app/$$2/scripts/$$1"; \
	done; \
	for pair in \
		"admin-config.js admin" \
		"tasklist-config.js tasklist" \
		"welcome-config.js welcome"; do \
		set -- $$pair; \
		cp "$$tmp/$$1" \
			"src/main/resources/META-INF/resources/webjars/operaton/app/$$2/scripts/config.js"; \
		cp "$$tmp/$$1" "src/main/resources/app/$$2/scripts/config.js"; \
	done; \
	find src/main/resources/app src/main/resources/META-INF/resources/webjars/operaton/app \
		-type f -name '*nologin*' -delete; \
	rm -f \
		src/main/resources/META-INF/resources/webjars/operaton/app/cockpit/config.js \
		src/main/resources/META-INF/resources/webjars/operaton/app/cockpit/scripts/decisions-dashboard.js
