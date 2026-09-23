# collective.bpmproxy

**collective.bpmproxy** is a Plone CMS add-on that integrates Operaton (a Camunda Platform 7 fork) into Plone Classic UI.

This repository is organized as a monorepo:
- **`backend/`**: Contains the Python backend (Plone add-on) and its documentation.
- **`frontend-classic/`**: Contains the Vite-built bundles for the Plone Classic UI (task forms, the diagram viewer, and the BPMN/DMN/Form modelers).
- **`frontend/`**: Placeholder for the future Volto add-on.
- **`scripts/`**: Site bootstrap and the browser smoke test.

## Building the Frontend
Each entry is built as a self-contained classic script, because Plone's resource
registry renders bundles as plain `<script src>` with no `type="module"`. The
output (`form.js`, `diagram.js`, `modeler.js` and their stylesheets) is written
to, and committed from, `backend/src/collective/bpmproxy/browser/static/`.

To compile the classic frontend assets into the backend static folder, run:
```shell
make frontend-build
```
For active development with auto-rebuild:
```shell
make frontend-watch
```

## Getting started

Requires [Nix](https://nixos.org) and [devenv](https://devenv.sh/getting-started/)
installed. From the repo root, open two terminals:

```shell
# Terminal 1: start Operaton, PostgreSQL, Keycloak and Mailpit
make shell
make services

# Terminal 2: build backend/.venv (first run only) and start Plone
make shell
make start
```

Then open Plone at <http://localhost:8080> and the Operaton Cockpit at
<http://localhost:8081/operaton/app/cockpit/default/> (login `admin`/`admin`
via Keycloak).

## End-to-end smoke test

`scripts/e2e_smoke.py` drives a real browser against a running stack and checks
what only a page load can: that the bundles parse and boot, that the modelers
render, and that deploying, listing and deleting a process from the control
panel works. With the services running and Plone stopped:

```shell
make bootstrap-site   # creates the Plone site, the add-on install, and test users
make start            # in the other terminal
make e2e              # screenshots land in var/e2e
```

`make bootstrap-site` is idempotent, and the smoke test removes what it
deploys.

See the [backend documentation](backend/README.md) for detailed installation
and usage instructions, including authentication keys, publishing BPMN
processes, and troubleshooting.
