SOURCES = $(shell find . -name "*.java" -or -name "*.xml" -or -name "*.yaml")

NIX_OPTIONS ?= --accept-flake-config

VERSION := 7.19.0-1

.PHONY: all
all: artifact

.PHONY: build
build: $(SOURCES)
	nix build $(NIX_OPTIONS)

.PHONY: clean
clean:
	$(RM) $(ARTIFACT_NAME)-*.tar.*

.PHONY: dist
dist:
	nix build --json .#image|jq -r .[0].outputs.out|sh|podman load -q
	podman tag localhost/plone-camunda-app:latest datakurre/plone-camunda:$(VERSION)
	podman tag localhost/plone-camunda-app:latest datakurre/plone-camunda:latest

.PHONY: push
push: dist
	podman push datakurre/plone-camunda:$(VERSION)
	podman push datakurre/plone-camunda:latest

###

mvn2nix-lock.json: pom.xml
	mvn2nix -vvv > mvn2nix-lock.json

###

.PHONY: nix-%
nix-%:
	@echo "run inside nix devShell: $*"
	nix develop $(NIX_OPTIONS) --command $(MAKE) $*
