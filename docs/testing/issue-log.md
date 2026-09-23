# Manual test campaign — issue log

Findings from driving `collective.bpmproxy` end to end in a headless browser
against the `devenv` stack. Each entry says what was seen, what caused it, and
what covers it now.

`P*` are product defects (fixed in the add-on), `E*` environment hazards,
`T*` bugs in the test harness itself.

Test case numbers refer to the matrix in [README.md](README.md).

---

## E1. Keycloak cannot restart after an ungraceful stop

**Seen.** After killing the stack with `kill -9`, `devenv up -d` puts Keycloak
into a crash-restart loop. `.devenv/run/processes/logs/keycloak.stdout.log`
fills with:

```
ERROR: Failed to obtain JDBC connection
ERROR: Database may be already in use: .../keycloak/data/h2/keycloakdb.mv.db
ERROR: The file is locked: .../keycloakdb.mv.db [2.4.240/7]
```

Because the `operaton` process waits on `$KEYCLOAK_ISSUER_URI` before starting,
the whole stack stalls with no obvious cause — Operaton's log stays empty.

**Cause.** `services.keycloak.type` defaults to `dev-file`, an H2 file
database. An ungraceful stop leaves the H2 lock held.

**Remedy.** The realm is re-imported from `devenv/keycloak/realm-plone.json` on
every start, so the state directory is disposable:

```shell
rm -rf .devenv/state/keycloak
```

**Status.** Environment hazard, documented. Worth considering
`services.keycloak.type = "dev-mem"` — note the devenv module warns that the
`keycloak-realm-export-*` script does not work with `dev-mem`, and
`devenv.nix` currently sets `export = true`.

---

## E2. Keycloak silently moves to another port

**Seen.** Keycloak bound `8083` while `devenv.nix` asks for `8082`. The
generated `keycloak.conf` held `http-port=8083` next to
`hostname=http://localhost:8082`. Operaton then waited forever on the issuer
URL, and OIDC would have issued tokens for an address nothing served.

**Cause.** devenv treats `settings.http-port` as a *hint*:
`processes.keycloak.ports.http.allocate` increments until it finds a free port.
8082 was held by a leftover Keycloak at the time of allocation. The result is
cached by the `allocatePort` primop in `.devenv/nix-eval-cache.db`, so it
persists across restarts even after the port frees up.

**Remedy.** Stop everything, confirm the ports are free, then clear the cache:

```shell
rm -f .devenv/nix-eval-cache.db*
```

**Status.** Environment hazard, documented. Note that `hostname` is *not*
reallocated, so a moved port is always an inconsistent configuration rather
than a working one on a different port.

---

## E3. PostgreSQL shuts itself down mid-run

**Seen.** Twice, mid-campaign, every engine call started failing. Operaton
logged `Connection to localhost:5432 refused`, and PostgreSQL had logged:

```
LOG:  lock file "postmaster.pid" contains wrong PID: 90885 instead of 36707
LOG:  performing immediate shutdown because data directory lock file is invalid
```

The damage is delayed and misleading: deployments start returning 500, the
process-definition vocabulary hangs for 30s on the connection pool timeout,
and unrelated scenarios later in the run fail on navigation timeouts.

**Cause.** A second process wrote `postmaster.pid`. The first occurrence was
self-inflicted — running `pg_ctl` by hand against `.devenv/state/postgres` to
inspect the cluster. The second was not: see [E5](#e5-two-devenv-stacks-sharing-one-state-directory),
which is the real root cause.

**Remedy.** Never run `pg_ctl` against `.devenv/state/postgres` while the
stack is up, and make sure no other devenv stack is using it.

**Status.** Root cause is E5.

---

## E4. The cluster's superuser does not match the container user

**Seen.** `devenv up -d` timed out after 120s. PostgreSQL logged
`FATAL: role "user" does not exist` every ten seconds and never became healthy,
so `operaton` (which `depends_on` it) never started.

**Cause.** `.devenv/state/postgres` was initialised on a machine whose OS user
was `datakurre`. devenv's health check connects as the current OS user
(`user`), which the cluster had no role for. `initialScript` does not re-run
against an existing data directory.

**Remedy.** Add the missing role rather than discarding the engine database:

```sql
CREATE ROLE "user" SUPERUSER LOGIN;
CREATE DATABASE "user" OWNER "user";
```

**Status.** Fixed in place; the cluster's Operaton history was preserved.

---

## T1. `sweep` crashed instead of reporting an unreachable engine

**Seen.** `TypeError: string indices must be integers` from
`fixtures.sweep()`.

**Cause.** Harness bug. `GET @bpmproxy-deployments` correctly answers HTTP 500
with `{"error": ...}` when the engine is down, but `sweep()` iterated the
parsed body without checking the status, so an infrastructure outage surfaced
as a type error in the test tooling.

**Fix.** `fixtures.list_deployments()` now raises `EngineUnavailable` with the
status and body, and the runner turns that into a message naming the Operaton
log. Verified against a genuinely down engine (E3).

---

## T2. Cross-origin service checks were blocked by CORS

**Seen.** `Page.evaluate: TypeError: Failed to fetch` when checking Operaton
and Mailpit.

**Cause.** Harness bug. Those checks used an in-page `fetch()`, which is
same-origin only; Operaton (`:8081`) and Mailpit (`:8025`) are different
origins from Plone (`:8080`).

**Fix.** Added `harness.api()`, which uses Playwright's request context and is
not subject to CORS. `harness.rest()` remains for same-origin `plone.restapi`
calls, where the `Accept: application/json` header is what matters.


---

## E5. Two devenv stacks sharing one state directory

**Seen.** After eliminating every in-container cause, PostgreSQL still died,
and `.devenv/state/postgres/postmaster.pid` kept being rewritten with PIDs
that do not exist in this container:

```
$ head -1 .devenv/state/postgres/postmaster.pid
623
$ ls /proc/623
ls: cannot access '/proc/623': No such file or directory
```

The decisive detail was the timestamp: the file was rewritten *after* our
PostgreSQL had already shut down, so something outside this PID namespace was
starting its own PostgreSQL against the same data directory.

**Cause.** Two devenv stacks — one inside the agent container, one on the host
— sharing `/workspace/collective.bpmproxy/.devenv/state/`. They have separate
network namespaces, so neither can see the other's ports, but they share the
filesystem and therefore PostgreSQL's data directory and Keycloak's H2
database.

This single cause explains all of:

- **E1**, the Keycloak H2 lock loop — the other stack held the lock;
- **E2**, Keycloak drifting to port 8083 — 8082 was taken at allocation time
  by the other stack, and the choice was then cached in
  `.devenv/nix-eval-cache.db`;
- **E3**, PostgreSQL's `postmaster.pid` mismatches.

**Remedy.** Only one stack may use `.devenv/state/` at a time. Stop the other
one (`devenv processes down`), or give one of them its own `DEVENV_STATE` and
a distinct set of ports.

**Status.** Environment constraint. Worth a line in the developer
documentation: the symptoms all appear as product failures several layers away
from the actual conflict.


---

# Product defects

## P1. Attachments were unreachable

**Seen.** Case E1. Clicking **Add attachment** on a task produced a
`NotFound`. No attachment could ever be added.

**Cause.** `client.get_available_tasks()` built its business-key query as
`(context_key or "%") + (attachments_key or "%")` — a plain concatenation.
Business keys are written by the form views as
`IUUID(context) + ":" + uuid4().hex`, so the pattern was wrong twice over:

- it omitted the `:` separator, so a query narrowed by both halves matched
  the concatenation of them and never a real key;
- callers pass the attachment container's id, which is the *dashed*
  `str(UUID(...))` form, while the business key holds dash-less hex.

Three call sites depended on it: `@@add-attachment`,
`AttachmentsLocalRoleProvider` (so dynamic upload rights were never granted)
and the attachment tasks viewlet.

**Fix.** Extracted `client.business_key_needle()`, which places the colon and
normalises both halves to hex. `tests/test_client_more.py` asserted the broken
pattern (`"ctx1att1"`); it now asserts `"ctx1:att1"`, plus a new test covering
the dashed-to-hex normalisation.

## P2. "Add attachment" hit a CSRF confirmation

**Seen.** Once P1 was fixed, the button landed on `@@confirm-action` instead
of the add form.

**Cause.** `bpm_attachments_viewlet.pt` submitted a `<form>` with no `method`
— so GET — and no authenticator token, while `@@add-attachment` creates the
attachment container. plone.protect answers a write made by an
unauthenticated GET with a confirmation interstitial.

**Fix.** The form is now `method="post"` and includes
`context/@@authenticator/authenticator`, the same pattern `bpm_form_view.pt`
already used.

## P3. No file could be uploaded at all

**Seen.** Case E2. The attachment was created, then the request failed and the
browser stayed on the add form. The log showed:

```
ZODB.POSException.Unsupported: Storing Blobs in <...> is not supported.
```

**Cause.** `mkwsgiinstance` writes a `zodb_db` section holding a bare
`<filestorage>`. Plone stores every uploaded file as a ZODB blob, which a
FileStorage without a `blob-dir` cannot hold. Because the object is created
before the commit fails, the symptom looked like a redirect that did not
happen rather than a storage problem.

**Fix.** `backend/scripts/configure_blobstorage.py` wraps the generated
filestorage in a `<blobstorage>` pointing at `$INSTANCE/var/blobstorage`, and
`backend/Makefile` runs it as part of creating the instance. It is idempotent,
so it also repairs an instance that already exists. (`make reset-site` already
deleted `instance/var/blobstorage`, so the intent had been there all along.)

## P4. A stale task link returned a 500

**Seen.** Case F4. `@@redirect-to-bpm-task/<unknown id>` raised an unhandled
exception.

**Cause.** `RedirectView.__call__` handled a task with no variables but not a
task the engine does not have: `get_task_variables` raises `ApiException`,
which propagated. Task portlet links go stale the moment somebody else
completes the task, so this is an ordinary occurrence, not an edge case.

**Fix.** The `ApiException` is caught and turned into `NotFound`.

## P5. The deploy service discarded the engine's explanation

**Seen.** A deployment rejected by the engine surfaced as
`500 {"error": "500 Server Error:  for url: .../deployment/create"}`, with no
indication of *why*.

**Cause.** `services/deploy.py` caught bare `Exception` and always answered
500. The engine's own status and body — which say, for example, that a process
has no history time to live — were dropped.

**Fix.** `requests.HTTPError` is now handled separately: the engine's status
is passed through when it is a valid HTTP status, and its JSON (or text) body
is returned under an `engine` key. A modelling error the author can fix is now
distinguishable from an engine outage.

Note the two halves of the client do not share an error type:
`deploy_process()` goes through `requests` and raises `requests.HTTPError`,
while everything else uses the generated client and raises `ApiException`.

## P6. Example process defects

- `examples/request-for-quote/request-for-quote.bpmn` had no
  `historyTimeToLive`, so the engine refused to deploy it. Added `P1D`.
- `examples/published-lifecycle/example-published-lifecycle.bpmn` caught
  `plone-contnet-modified:${uuid}` — a typo, so it never received the
  `plone-content-modified:${uuid}` signal the shipped content rule sends.
- `examples/empire-insider/ReviewAssistant.bpmn` declared its process id as
  `ReviewSupport`, matching neither the file name nor the documentation.

## P7. `make test-live` ran nothing, `make test-offline` did not exist

**Seen.** The root Makefile delegated `test-offline` to a target
`backend/Makefile` did not have, and no test carried the `operaton` marker, so
`make test-live` silently exercised nothing.

**Fix.** Added `test-offline` and `test-live` to both Makefiles, and
`tests/test_live_engine.py` — three tests that exercise what the mocked suite
structurally cannot: that Plone's ed25519-signed JWT is accepted by the
engine, that a deployment round-trips, and that a token without
`camunda-admin` is refused engine rights. `test-live` reports pytest's "no
tests ran" exit code as success rather than a broken build.
