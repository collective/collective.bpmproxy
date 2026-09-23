.PHONY: all install shell services test lint format i18n start reset-site clean backend-build frontend-build frontend-watch test-offline test-live bootstrap-site bootstrap-renovation-demo bootstrap-review-demo bootstrap-contact-form-demo e2e ui-test screenshots services-reset

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

# Throw away the services' generated state when the stack will not start.
# Fixes, in one step, the three failure modes that otherwise look like
# product bugs (see docs/testing/issue-log.md):
#
#   * Keycloak crash-looping on an H2 lock left by an ungraceful stop;
#   * Keycloak silently bound to 8083 because devenv cached a port
#     allocation made while 8082 was busy;
#   * a PostgreSQL cluster whose superuser does not match this machine's
#     user, which never passes its health check.
#
# Stop the stack first. The Keycloak realm is re-imported from
# devenv/keycloak/realm-plone.json on the next start, so nothing you have in
# version control is lost -- but the engine's process history is in
# PostgreSQL, so this does discard running process instances.
services-reset:
	@echo "This deletes .devenv/state/{keycloak,postgres} and the devenv eval cache."
	@echo "Running process instances will be lost. Ctrl-C now to abort."
	@sleep 5
	rm -rf .devenv/state/keycloak .devenv/state/postgres
	rm -f .devenv/nix-eval-cache.db .devenv/nix-eval-cache.db-shm .devenv/nix-eval-cache.db-wal
	@echo "Done. Start again with: devenv up -d"

test:
	$(MAKE) -C backend test

test-offline:
	$(MAKE) -C backend test-offline

# The tests that need a live engine (`devenv up -d` first).
test-live:
	$(MAKE) -C backend test-live

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

reset-site:
	$(MAKE) -C backend reset-site

# Install the renovation-project demo profile and its recording-only demo
# users (owner/contractor/inspector). Run after bootstrap-site, with Plone
# stopped: it opens the ZODB.
bootstrap-renovation-demo:
	cd backend && uv run zconsole run instance/etc/zope.conf ../scripts/bootstrap_renovation_demo.py

bootstrap-review-demo:
	cd backend && uv run zconsole run instance/etc/zope.conf ../scripts/bootstrap_review_demo.py

bootstrap-contact-form-demo:
	cd backend && uv run zconsole run instance/etc/zope.conf ../scripts/bootstrap_contact_form_demo.py

# Browser smoke test against a running stack: `make services`, `make start`.
e2e:
	e2e-smoke --screenshots var/e2e

# The browser test campaign (scripts/uitest/). Assert-only and quiet: this is
# the one to run in the fix loop.
ui-test:
	ui-test --no-shots

# Regenerate the end-user guide's screenshots. Same code path as `ui-test`,
# so images are only written by a run in which every check passed; also fails
# if docs/user/ and the shot registry have drifted apart.
screenshots:
	ui-test --check-docs
