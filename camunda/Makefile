SOURCES = $(shell find . -name "*.java" -or -name "*.xml" -or -name "*.yaml")

NIX_OPTIONS ?= --accept-flake-config

.PHONY: all
all: artifact

.PHONY: build
build: $(SOURCES)
	nix build $(NIX_OPTIONS)

.PHONY: clean
clean:
	$(RM) $(ARTIFACT_NAME)-*.tar.*

.PHONY: dist
dist: image

###

mvn2nix-lock.json: pom.xml
	mvn2nix -vvv > mvn2nix-lock.json

###

.PHONY: nix-%
nix-%:
	@echo "run inside nix devShell: $*"
	nix develop $(NIX_OPTIONS) --command $(MAKE) $*
