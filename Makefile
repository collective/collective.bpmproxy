.PHONY: all install shell services test lint format i18n start reset-site clean backend-build frontend-build frontend-watch bootstrap-site e2e

all: install

# Enters the devenv shell (toolchain + CAMUNDA_* env, see devenv.nix).
# `make services` and `make start` both expect to be run from inside it.
shell:
	devenv shell

install:
	$(MAKE) -C backend install

# Starts the Operaton stack (Operaton, PostgreSQL, Keycloak, Mailpit)
# defined in devenv.nix. Run in its own terminal (inside `make shell`),
# alongside `make start` in another one.
services:
	devenv up

test:
	$(MAKE) -C backend test

test-offline:
	$(MAKE) -C backend test-offline

lint:
	$(MAKE) -C backend lint

format:
	$(MAKE) -C backend format

i18n:
	$(MAKE) -C backend i18n

start:
	$(MAKE) -C backend start

clean:
	$(MAKE) -C backend clean

backend-build:
	$(MAKE) -C backend all

frontend-build:
	npm --prefix frontend-classic install
	npm --prefix frontend-classic run build

frontend-watch:
	npm --prefix frontend-classic install
	npm --prefix frontend-classic run dev

# Create the Plone site the smoke test runs against (and the "manager" and
# "editor" users it logs in as). Run it with Plone stopped: it opens the ZODB.
bootstrap-site:
	cd backend && uv run zconsole run instance/etc/zope.conf ../scripts/bootstrap_site.py

# Browser smoke test against a running stack: `make services`, `make start`.
e2e:
	e2e-smoke --screenshots var/e2e
