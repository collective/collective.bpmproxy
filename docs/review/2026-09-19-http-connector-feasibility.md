# HTTP Connector feasibility: calling Plone from Operaton

**Date:** 2026-09-19
**Branch:** `operaton` · **HEAD:** `117b1da chore: prune examples down to the actively used/tested set`
**Scope:** whether the engine already has a working HTTP Connector, what it
would take to wire one up to call the Plone backend, and whether doing so is
safe given the transaction relationship between Plone and Operaton.
**Method:** read + grep-verified against disk. Investigation only; no code
changed.

## tl;dr

- The engine has the generic Camunda Connect SPI on its classpath, but **not**
  a working HTTP connector — `operaton-connect-http-client` is absent.
  Adding it is a small, mechanical change.
- Getting an environment-variable-backed base URL/secret into a connector
  expression is not yet an established pattern here, but there's a clean way
  to add one (a registered expression bean), reusing the existing env-var
  chain.
- **The bigger issue is safety, not plumbing.** A synchronous HTTP connector
  calling back into Plone from inside an engine transaction that was itself
  started by an open Plone transaction is a real reentrancy hazard — and it
  has already caused a rollback once, with an *unconfigured* connector, in
  the request-for-quote demo. Recommendation below: don't wire a synchronous
  connector into Plone's write path; use the External Task worker pattern
  already proven safe by `examples/renovation-bot/` for anything that needs
  "engine calls Plone."

## 1. Does the engine include the HTTP Connector?

Partially — the generic infrastructure is present, the actual HTTP
implementation is not.

`fixture/operaton/pom.xml` declares:

```xml
<artifactId>operaton-engine-plugin-connect</artifactId>
```

This transitively pulls in `org.operaton.connect:operaton-connect-core`
(confirmed present in `fixture/operaton/mvn2nix-lock.json`, in the local
`.m2` repository, and inside the built fat jar's `BOOT-INF/lib/`). That
artifact only provides the generic `Connector`/SPI machinery — a registry and
interfaces — not an HTTP implementation.

`org.operaton.connect:operaton-connect-http-client` — the artifact that
actually implements `http-connector` (Apache HttpClient5-backed) — **is not
present anywhere**: not in the pom, not in the lock file:

```
$ grep -c operaton-connect-http-client fixture/operaton/mvn2nix-lock.json
0
```

not in `.m2`, and not in the built jar. There's also no `bpm-platform.xml`,
`camunda.cfg.xml`, or custom `Connector` registration anywhere in
`fixture/operaton/` — nothing fills the gap.

There is already a piece of unwired connector syntax in the repo, worth
noting because it's directly relevant to §3 below:
`examples/request-for-quote/request-for-quote.bpmn` has a `bpmn:sendTask`
using

```xml
<camunda:connector>
  <camunda:connectorId>mail-send</camunda:connectorId>
  ...
</camunda:connector>
```

Nothing in `fixture/operaton`'s Java sources implements or registers a
`mail-send` connector. It's illustrative BPMN, not a proven working example.

## 2. What would it take to wire up a real HTTP connector?

Small on the dependency side, more design work on the "reach Plone safely
with config from the environment" side.

**Dependency + build.** Add `operaton-connect-http-client` to
`fixture/operaton/pom.xml`. Because this build is Nix-driven
(`mvn2nix-lock.json`, `flake.nix`/`default.nix` — there's no plain
`mvn install` build), adding a dependency isn't just a pom edit: the
mvn2nix lock file needs regenerating so Nix can fetch the new jar
reproducibly. That's an extra step beyond a normal Maven project, but not a
hard one.

Once the jar is on the classpath, Camunda/Operaton auto-registers the
`http-connector` connector id via its own SPI — no extra Java registration
code is needed just to make `<camunda:connectorId>http-connector</camunda:connectorId>`
resolve.

**Getting env vars into connector expressions.** This is the part with no
existing precedent to lean on. Every scriptTask/connector expression found in
the repo's example BPMN (`renovation-final-review.bpmn`,
`renovation-plan-review.bpmn`, `example-published-lifecycle.bpmn`, etc.) is
plain JUEL against **process variables** — `${execution.setVariable(...)}`,
`${execution.setBusinessKey(...)}` — never an environment variable or secret.
There's nothing today an inline `camunda:inputParameter` expression could
call to reach `PLONE_BASE_URL` or a shared secret.

The idiomatic Camunda fix is to register a small bean on
`processEngineConfiguration.setBeans()` (e.g. `env`) so connector/expression
XML can do `${env.get('PLONE_BASE_URL')}` without ever hardcoding a URL or
secret into a process definition. That bean would sit naturally next to the
existing custom `ProcessEnginePlugin` and BPMN parse listener already
registered in `fixture/operaton/src/main/java/com/example/camunda/ProcessEngineConfig.java`
— the same file that already wires up the JWT identity service and
admin-authorization plugin.

Sourcing the value itself needs no new plumbing: the repo already has a
working chain for exactly this — `devenv.nix`'s top-level `env = { ... }`
block (e.g. `CAMUNDA_API_URL`, `PLONE_PUBLIC_KEY`) is inherited by the
`spring-boot:run` process and picked up in `application.yml` via
`${VAR:default}` placeholders, optionally exposed to Java via `@Value`
(see `ProcessEngineConfig.java` for the existing pattern). A `PLONE_BASE_URL`
/ `PLONE_CONNECTOR_SECRET` pair would follow the identical path.

Net: this is a real but modest implementation task — one dependency, one lock
regeneration, one small Spring bean, no changes to the identity/auth wiring.

## 3. Is it safe to call Plone from a connector?

This is where the real complexity is, and it's already been demonstrated,
not just theorized.

### There is a custom transaction-deferral mechanism — but it only covers half the picture

`backend/src/collective/bpmproxy/utils.py` defines `SideEffectDataManager`, a
`zope.transaction` `IDataManager` that joins Plone's two-phase commit and
defers its callable to `tpc_finish` — i.e. it only runs **after** Plone's own
ZODB transaction has committed, and it runs on a dedicated background thread
pool rather than the request thread.

It's used in exactly three places, confirmed by grep:

```
backend/src/collective/bpmproxy/actions/signal.py:106:    SideEffectDataManager(
backend/src/collective/bpmproxy/subscribers/tasks.py:31:   SideEffectDataManager(
backend/src/collective/bpmproxy/subscribers/tasks.py:59:   SideEffectDataManager(
backend/src/collective/bpmproxy/actions/message.py:150:   SideEffectDataManager(
```

— content-rule signal dispatch, content-rule message dispatch, and
Plone-form-as-task completion. All three are **engine-reacts-to-a-Plone-event**
flows, and all three already document the exact reasoning the user is asking
about:

- `docs/user/07-content-rules.md`: *"Signals are dispatched when the Plone
  transaction commits, not when the rule runs. If the request fails after
  the rule fired, no signal is sent — the engine never learns about work
  that was rolled back."*
- `docs/user/08-plone-forms-as-tasks.md`: *"Both completions are deferred to
  transaction commit, so a failed save leaves the task open."*

But the **primary** "user fills in a Camunda form" path —
`views/bpm_form_view.py`'s `_submit()` (`BpmProxyView`) and
`BpmProxyTaskFormView._submit()`, plus the deployment actions in
`services/deploy.py`/`services/deployments.py` — is synchronous and
**pre-commit**: it calls the engine directly, inside the still-open Plone
request/transaction, with no deferral at all.

And there is today **no existing mechanism, deferred or otherwise, for the
engine to call back into Plone** from within `collective.bpmproxy` itself.
The only reverse-direction interaction anywhere in the repo is
`examples/renovation-bot/`, a separate, out-of-repo-lifecycle Camunda
**External Task worker** (started independently via `make serve`, not part of
the engine process) that polls the engine for locked tasks and only then
calls Plone's `@workflow` REST endpoint with its own static credential. It's
a fundamentally different, decoupled shape from a service task synchronously
invoking an HTTP connector.

### The hazard is not hypothetical — it already happened

`docs/AGENTS.md` (the request-for-quote recording notes) documents that the
demo runner has to actively work around this. Quoting it directly:

> The accepted branch's mail connector extension is removed and its
> `sendTask` is converted to a no-op generic `task`. The fixture has no
> configured connector implementation; leaving the connector in place can
> roll back reviewer completion.

That's the exact failure the user described — a connector task inside the
engine's own transaction failing (here, because nothing implements
`mail-send`) and taking the surrounding process step's commit down with it,
observed in the recorded demo before anyone added an HTTP connector at all.
An HTTP call to a live Plone instance — which can itself fail, time out, or
be slow under load — is a strictly larger version of the same risk, now
aimed at a second, independently-transacted system.

### The specific reentrancy scenario

If a Plone request synchronously calls the engine (the common,
pre-commit path above) and that engine transaction synchronously drives a
service task with an HTTP connector back into Plone, the callback is a
**separate** Plone request/transaction, racing the still-open original one on
whatever content it touches. In the best case that's a ZODB conflict error;
in the worst case — per the user's framing — it can propagate back and roll
back the *original* Plone transaction that triggered the whole chain, for a
reason that has nothing to do with what that original transaction was
actually doing.

The existing `SideEffectDataManager` pattern does not protect against this:
it only defers Plone's *outbound* calls to the engine in three flows, and it
does nothing for calls in the *other* direction (engine → Plone), which is
the direction an HTTP connector would need.

## 4. Recommendation

**Don't wire a synchronous HTTP connector from an Operaton service task
directly into Plone's write-path REST API.** Three independent reasons stack
up:

1. The rollback hazard is not theoretical — an unconfigured connector already
   caused it once in this repo (§3).
2. Nothing in the current transaction model protects an engine-initiated,
   synchronous call into Plone; the one deferral mechanism that exists
   (`SideEffectDataManager`) only covers the opposite direction, and only for
   three flows.
3. HTTP connectors are hard to debug even without the transaction problem —
   failures land as opaque incidents/job retries in Operaton rather than
   surfacing through the engine's own audit log or Plone's logging, so a
   silent rollback caused by a flaky HTTP call would be genuinely hard to
   diagnose from either side.

**If a demo wants "engine calls Plone" for something interactive**, the
pattern already proven safe in this repo is the External Task worker used by
`examples/renovation-bot/`: decoupled from the engine's own transaction,
polling rather than reentrant, with its own retry/backoff, and already
demonstrated not to roll back either system against the other. Extending or
more prominently documenting that pattern is the lower-risk way to get the
same "fancy interactive demo" outcome the user is after.

**If HTTP-connector calls are still wanted for something narrower** (e.g. a
read-only, idempotent lookup against Plone — not a write), scope it tightly:
only from execution paths that are themselves reached post-commit relative to
whatever Plone transaction started the process (i.e., not the synchronous
form-submission path), and treat the env-var/bean design in §2 as the
mechanism to use if this is ever built.
