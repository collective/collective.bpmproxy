# devenv + headless browser smoke test

Date: 2026-09-16

The project was exercised using its declared `devenv.nix` environment and the
headless Chromium browser supplied by the browser skill.

## Result

The existing `scripts/e2e_smoke.py` completed successfully with **24 checks
passed** against a clean temporary Plone instance:

- PostgreSQL, Keycloak, Mailpit, and Operaton responded successfully.
- The Plone front page and BPMN/DMN/Form modeler control panel loaded.
- BPMN and DMN modelers, the form playground, icon fonts, and frontend bundles
  booted without browser errors.
- Deployment, listing, and deletion through the REST API worked.
- A BPM Proxy content item rendered its Camunda form and BPMN diagram.
- The deployment endpoint correctly rejected the lower-privileged user.
- The smoke test removed its temporary content and deployments.

## Screenshots

| Page | Screenshot |
| --- | --- |
| BPMN modeler | [controlpanel-bpmn.png](e2e/controlpanel-bpmn.png) |
| DMN modeler | [controlpanel-dmn.png](e2e/controlpanel-dmn.png) |
| Form playground | [controlpanel-form.png](e2e/controlpanel-form.png) |
| Deployment list | [controlpanel-deployments.png](e2e/controlpanel-deployments.png) |
| BPM Proxy form and diagram tabs | [bpm-proxy-view.png](e2e/bpm-proxy-view.png) |

## Headless recording

A headless Chromium walkthrough of the Plone modeler tabs, deployment view, and
site front page is available as [renovation-project-pip.webm](renovation-project-pip.webm).

The reproducible end-to-end scenario is documented in
[renovation-project-scenario.md](renovation-project-scenario.md). It records the
case personas and Cockpit, composing them into a single focus-flipping
picture-in-picture walkthrough.

## Environment notes

Re-verified 2026-09-17 on a clean checkout.

`backend/instance/` is generated, not checked in (`backend/.gitignore` ignores
`instance/`), and `mkwsgiinstance` bakes **absolute** paths into
`instance/etc/zope.ini`:

```ini
args = (r'/home/<someone-else>/.../backend/instance/var/log/Z4.log','a')
```

A copy carried over from another machine therefore fails to start. Delete it
and regenerate rather than working around it with an instance under `/tmp`:

```sh
rm -rf backend/instance
devenv shell -- bash -c "cd backend && uv run mkwsgiinstance -d instance -u admin:admin"
```

Then bootstrap with Plone **stopped** (it opens the ZODB directly), and only
then start Plone:

```sh
make bootstrap-site
make start
```

### `devenv up -d` reports a timeout that is usually cosmetic

`devenv up -d` frequently prints:

```
× Daemon failed to start within 120s. Check logs at: /tmp/devenv-<hash>/processes/daemon.log
```

That message is not conclusive, and `daemon.log` is often empty. Operaton boots
through Maven and can take minutes, which is what overruns the 120 s window.
Check the endpoints, not the exit message:

```sh
curl -sf http://127.0.0.1:8081/engine-rest/engine   # Operaton (slowest)
curl -sf http://127.0.0.1:8082/realms/plone         # Keycloak
curl -sf http://127.0.0.1:8025/api/v1/messages      # Mailpit
```

`devenv processes list` can *also* claim "No process manager is running" while
the daemon and every service are alive — confirm with
`ps -ef | grep daemon-processes` before concluding anything is broken.

Two failures behind that message are real:

- **Stale `postmaster.pid`.** After an unclean shutdown, postgres logs
  `FATAL: lock file "postmaster.pid" already exists` and never binds 5432,
  which takes Operaton down with it. Fix:
  `rm -f .devenv/state/postgres/postmaster.pid` once no postgres is running.
- **Orphaned services from a previous run.** They survive `devenv processes
  down` and hold the ports. Check with
  `pgrep -af 'mailpit|QuarkusEntryPoint|spring-boot:run|bin/postgres$'` and kill
  what remains before restarting.

Do not run `devenv processes up` to probe whether it is a valid subcommand: it
starts a **second** process manager, which brings up duplicate services on
shifted ports (Mailpit on 8026, a second Keycloak and Operaton) that compete
with the stack under test. Use `devenv processes --help`, and `devenv up -d` to
start.
