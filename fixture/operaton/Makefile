SOURCES = $(shell find . -name "*.java" -or -name "*.xml" -or -name "*.yaml")

NIX_OPTIONS ?= --accept-flake-config

VERSION := 2.1.0

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
	# Cockpit plugins and config
	mkdir -p src/main/resources/META-INF/resources/webjars/operaton/app/cockpit/scripts
	for f in dashboard-favourites.js dashboard-integrations.js definition-historic-activities.js definition-tab-modify.js instance-auto-refresh.js instance-action-unlock.js instance-historic-activities.js instance-route-history.js instance-tab-modify.js cockpit-custom-styles.js robot-module.js cockpit-nologin.js cockpit-nologin-config.js decisions-dashboard.js; do \
		curl -sL https://raw.githubusercontent.com/datakurre/operaton-cockpit-plugins/rewrite/$$f -o src/main/resources/META-INF/resources/webjars/operaton/app/cockpit/scripts/$$f; \
	done
	curl -sL https://raw.githubusercontent.com/datakurre/operaton-cockpit-plugins/rewrite/config.js -o src/main/resources/META-INF/resources/webjars/operaton/app/cockpit/config.js
	# Admin plugins and config
	mkdir -p src/main/resources/META-INF/resources/webjars/operaton/app/admin/scripts
	for f in admin-nologin.js admin-route-authorization.js; do \
		curl -sL https://raw.githubusercontent.com/datakurre/operaton-cockpit-plugins/rewrite/$$f -o src/main/resources/META-INF/resources/webjars/operaton/app/admin/scripts/$$f; \
	done
	curl -sL https://raw.githubusercontent.com/datakurre/operaton-cockpit-plugins/rewrite/admin-config.js -o src/main/resources/META-INF/resources/webjars/operaton/app/admin/scripts/config.js
	# Tasklist plugins and config
	mkdir -p src/main/resources/META-INF/resources/webjars/operaton/app/tasklist/scripts
	for f in tasklist-nologin.js tasklist-audit-log.js; do \
		curl -sL https://raw.githubusercontent.com/datakurre/operaton-cockpit-plugins/rewrite/$$f -o src/main/resources/META-INF/resources/webjars/operaton/app/tasklist/scripts/$$f; \
	done
	curl -sL https://raw.githubusercontent.com/datakurre/operaton-cockpit-plugins/rewrite/tasklist-config.js -o src/main/resources/META-INF/resources/webjars/operaton/app/tasklist/scripts/config.js
	# Welcome plugins and config
	mkdir -p src/main/resources/META-INF/resources/webjars/operaton/app/welcome/scripts
	curl -sL https://raw.githubusercontent.com/datakurre/operaton-cockpit-plugins/rewrite/welcome-nologin.js -o src/main/resources/META-INF/resources/webjars/operaton/app/welcome/scripts/welcome-nologin.js
	curl -sL https://raw.githubusercontent.com/datakurre/operaton-cockpit-plugins/rewrite/welcome-config.js -o src/main/resources/META-INF/resources/webjars/operaton/app/welcome/scripts/config.js
