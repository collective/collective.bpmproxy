.PHONY: all install lock test test-offline test-live lint format i18n start reset-site clean

all: install

# `uv sync` is already fast and idempotent on its own (no-ops quickly when
# nothing changed), so there's no need for a marker file here. devenv.nix
# pins UV_PROJECT_ENVIRONMENT to this project's backend/.venv, so the venv
# is a normal stable local directory (not a devenv-internal shared location
# that gets reprovisioned between shell sessions). The verify-and-repair
# step below is defense in depth for that class of bug regardless: if a
# console-script (mkwsgiinstance, runwsgi, ...) ever goes missing while
# package metadata still looks satisfied, uv's fast sync path won't notice
# on its own. Verify with the *exact* invocation used below (not e.g.
# shutil.which, which searches the whole inherited PATH and can
# false-positive on a stale copy elsewhere) and force a repair if missing.
install:
	uv sync --extra test
	@uv run --no-sync mkwsgiinstance --help > /dev/null 2>&1 \
		|| uv sync --extra test --reinstall

# Refresh the [tool.uv] constraint-dependencies pins in pyproject.toml from
# Plone's official 6.1 constraints (uv lock/sync have no mechanism to
# reference a remote constraints file directly), then regenerate uv.lock.
lock:
	python3 scripts/update_plone_constraints.py
	uv lock

test: install
	uv run pytest

# The default addopts in pyproject.toml already exclude the "operaton" marker,
# so this is what `test` does. It exists because the root Makefile offers
# `test-offline` as the explicit counterpart to `test-live`.
test-offline: install
	uv run pytest -m "not operaton"

# Needs the engine: `devenv up -d` first. Exits 5 ("no tests ran") if nothing
# carries the marker, which is not a failure -- say so rather than looking
# like a broken build.
test-live: install
	@uv run pytest -m "operaton"; status=$$?; \
		if [ $$status -eq 5 ]; then \
			echo "no tests are marked 'operaton'"; exit 0; \
		else exit $$status; fi

lint: install
	uv run ruff check src
	uv run ruff format --check src

format: install
	uv run ruff format src
	uv run ruff check --fix src

i18n: install
	uv run update_locale

# Expects CAMUNDA_API_URL and CAMUNDA_API_PRIVATE_KEY in the environment
# (provided by the devenv shell, see devenv.nix) and the services from
# `devenv up` (Operaton, Keycloak, PostgreSQL, Mailpit) to be running.
# Order-only prerequisite: run `install` first, but don't force
# mkwsgiinstance to rerun (and fail on an already-existing instance/) just
# because `install` is phony and always "changed".
instance/etc/zope.ini: | install
	uv run mkwsgiinstance -d instance -u admin:admin
	# mkwsgiinstance writes a bare <filestorage>, which cannot store the ZODB
	# blobs every Plone file upload becomes. Without this, the first upload
	# fails at commit with "Storing Blobs ... is not supported".
	uv run python scripts/configure_blobstorage.py instance/etc/zope.conf

start: instance/etc/zope.ini
	uv run runwsgi -v instance/etc/zope.ini

# Wipe the Plone/Zope site database (ZODB Data.fs + blobstorage) so the next
# `make start` boots a fresh, empty Zope root. Keeps the instance config
# (instance/etc/, created by mkwsgiinstance) and the venv, so it's much
# faster than `make clean` when e.g. an old site's content/catalog doesn't
# match the current dependency versions anymore. Stop `make start` first:
# Zope holds a lock on Data.fs while running.
reset-site:
	rm -f instance/var/Data.fs*
	rm -rf instance/var/blobstorage
	mkdir -p instance/var/log instance/var/cache

clean:
	rm -rf "$${UV_PROJECT_ENVIRONMENT:-.venv}" instance dist .pytest_cache .ruff_cache
