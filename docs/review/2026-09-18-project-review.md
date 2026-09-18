# collective.bpmproxy — whole-project review

**Date:** 2026-09-18
**Branch:** `operaton` · **HEAD:** `104e47b feat: Migrate editor-bot and plone-bot examples to purjo`
**Scope:** whole project — backend Python, Operaton Java fixture, frontend-classic, devenv/CI, docs, examples. Committed and uncommitted alike.
**Method:** read + static checks + executed the CI-equivalent suites. Review only; no code was changed.

## How to read this

Every finding records **how it was verified**. Findings I could not execute myself are
marked **unconfirmed** rather than asserted. The repo changed while the review was in
progress (28 tracked files modified, several findings fixed mid-flight), so every item
below was re-checked against disk at the date above — see
[Fixed while this review was running](#fixed-while-this-review-was-running).

Severity is about *consequence*, not effort:

| | meaning |
|---|---|
| **Critical** | Blocks a new contributor or breaks a documented workflow outright |
| **High** | Security control that does not hold, or a correctness bug on a user-input path |
| **Medium** | Real defect with a workaround, or a guard rail that is missing |
| **Low** | Hygiene, duplication, drift — no functional impact today |

## Baseline: what currently passes

Measured, not assumed:

- `uv run pytest` → **207 passed, 3 deselected** in 6.4 s (the 3 are `operaton`-marked live-engine tests).
- `ruff check src` → **All checks passed**; `ruff format --check src` → **85 files already formatted**.
- Java: **35 tests across 8 classes, 0 failures**, per `fixture/operaton/target/surefire-reports/` dated Sep 16 18:51. **Unconfirmed by me** — `mvn` is not on `PATH` outside the devenv shell, so I could not re-run them.
- Committed frontend bundles were previously shown reproducible from source by a full `build.mjs` run.

The code that is tested is in good shape. The findings below are concentrated in the
seams: the Java fixture, the build/CI wiring, and documentation.

---

## Critical

### C1 — A fresh clone cannot start the stack: the Maven wrapper is gitignored

`.gitignore:11` ignores `.mvn/`, which silently excludes
`fixture/operaton/.mvn/wrapper/maven-wrapper.properties`. `mvnw` **is** tracked; its
properties file is not (`git ls-files fixture/operaton/.mvn/` → 0 files).

`devenv.nix`'s `processes.operaton` runs `./mvnw … spring-boot:run`, so this breaks the
project's primary documented workflow (`make services`) on any clean checkout.

**Verified by fresh clone** into a temp dir:

```
$ git clone /workspace/collective.bpmproxy freshclone && cd freshclone/fixture/operaton
$ ./mvnw -v
./mvnw: line 117: ./.mvn/wrapper/maven-wrapper.properties: No such file or directory
```

The root `.gitignore` inherits `.mvn/` from the buildout era, where it meant something
else. Fix: negate it (`!fixture/operaton/.mvn/`) or scope the original rule, then commit
the wrapper properties.

### C2 — `make` in `fixture/operaton/` fails on its default target

`Makefile` declares `all: artifact`, but **no `artifact` target exists anywhere** in the
file. The default target therefore aborts immediately:

```
$ make -n
make: *** No rule to make target 'artifact', needed by 'all'.  Stop.
```

`make build` (→ `nix build`) works; only the default entry point is broken.
**Verified** by `make -n` and `grep`.

---

## High

### H1 — Operaton never validates JWT expiry (or issuer, or audience)

`fixture/operaton/src/main/java/com/example/camunda/JWTAuthenticationProvider.java:42-72`
verifies **only** the EdDSA signature over `header.payload`. There is no `exp`, `nbf`,
`iat`, `iss` or `aud` check anywhere on the Java side.

Plone mints tokens with a one-hour expiry
(`backend/src/collective/bpmproxy/client.py:58`), so the intent is clearly that tokens
expire — but the engine ignores the claim. **A leaked or captured token is valid forever**,
for as long as the keypair lives. Since the token carries `sub`, `groups` and
`tenant_ids`, that is a permanent impersonation primitive.

The test suite documents the gap: `JWTAuthenticationProviderTest` has 7 tests covering
success, bad signature, wrong part count, bad PEM, missing prefix and null header —
**and none for an expired token**.

**Verified** by reading both Java files and grepping the test class.

Fix: validate `exp`/`nbf` (and assert the `alg` header) before returning
`AuthenticationResult.successful(...)`, and add the missing test.

### H2 — The identity service trusts JWT claims it has not verified

`JWTIdentityService.java:46-50` receives the **raw JWT as the user id** (the provider
calls `AuthenticationResult.successful(token)`), re-parses it with `SignedJWT.parse(userId)`,
and reads `sub`, `groups` and `tenant_ids` from it **without re-verifying the signature**.

This is safe only while the authentication filter is the sole path into
`setAuthentication`. Any other caller — a webapp login path, a future REST entry point,
internal engine code — that passes an attacker-influenced string gets its claims trusted
verbatim, including `groups`, which is what grants `camunda-admin`.

Passing a verified claims object (not a re-parsed string) removes the whole class of risk.
**Verified** by reading.

### H3 — Server-side form validation: min/max checks are inert

`backend/src/collective/bpmproxy/utils.py:210-218`:

```python
min_value = validation.get("min")
assert min_value is None or data.get(key) or 0 >= min_value, (
    "Field " + key + " must have minimum value of " + min_value + "."
)
```

`data.get(key) or 0 >= min_value` parses as `data.get(key) or (0 >= min_value)`. Any
truthy submitted value short-circuits the assertion, so **`min` and `max` are never
enforced**. The same shape repeats for `max`.

The message is also broken independently: `"…" + min_value` concatenates `str + int` and
raises `TypeError`. `test_utils_more.py` actually asserts that `TypeError`, so the test
suite pins the bug in place rather than catching it. `minLength`/`maxLength` share the
message defect (their conditions are correct).

**Verified** by reading and by Python operator precedence.

### H4 — All form validation is `assert`, so `python -O` disables it

Every check in `validate_camunda_form` (`utils.py:188-230`) is a bare `assert`. Under
`python -O` / `PYTHONOPTIMIZE`, assertions are stripped and the function becomes a no-op
that validates nothing — on the path that validates untrusted form submissions before
they reach the engine.

This is a deployment-flag-dependent security control. Raise a real exception instead.
**Verified** by reading.

### H5 — The Java fixture is never built or tested in CI

`.github/workflows/plone-package.yml` defines four jobs: `lint`, `test`, `build`,
`frontend`. There is no Maven job, no `nix build`, and no `nix flake check`.

So the 35 JUnit tests — **including every JWT security test**, exactly the code in H1/H2 —
never run on a pull request. A regression in the authentication filter would reach `master`
with a green tick. Neither e2e script runs either, and `devenv.nix` is never exercised,
which is why C1 could land unnoticed.

**Verified** by reading the workflow.

### H6 — ~7,400 lines of the project are untracked

65 untracked text files (`.py`/`.zcml`/`.xml`/`.toml`/`.robot`/`.ts`/`.md`/`.rst`,
excluding caches) totalling **7,382 lines**, plus 28 modified tracked files
(+390/−122). By area: `scripts/` (20 files, incl. the whole `scripts/uitest/` campaign),
`docs/` (20), `backend/src/collective/bpmproxy/` (20 — `behaviors/`, `case_demo.py`,
`renovation_demo.py`, `profiles/case_demo/`, `profiles/renovation_demo/`, three test
modules), `examples/renovation-bot/` (3).

This is the single largest risk in the repo and it is not a code defect: this work has no
review history, no CI coverage, and no backup outside one working tree. It includes
security-relevant changes (the `IProcessContext` migration touching
`adapters/security.py`) and a new engine-facing demo profile.

**Verified** by `git ls-files --others --exclude-standard` + `wc -l`.

Recommendation: land it in reviewable commits before anything else on this list. The
cheapest fixes below (C1, C2, M7) are good first commits.

---

## Medium

### M1 — Global authorizations let any authenticated principal start any process

`Engine.java:46-70` seeds `AUTH_TYPE_GLOBAL` authorizations granting `READ` +
`CREATE_INSTANCE` on `PROCESS_DEFINITION:ANY` and `CREATE` on `PROCESS_INSTANCE:ANY`.
`operaton.bpm.authorization.enabled: true` therefore buys much less than it appears to:
authorization is on, but process-start is open to everyone who authenticates.

Reasonable for a dev fixture; it should not be the shape anyone copies to production, and
the README does not say so. **Verified** by reading.

### M2 — REST services leak internal exception text

`services/deploy.py:49-51` and `services/deployments.py:31-33,58-60` both end in
`except Exception as e: return {"error": str(e)}` with a 500. Raw exception strings from
an internal engine call reach the API client — paths, connection strings, stack detail.
`deploy.py` handles `requests.HTTPError` thoughtfully (it forwards engine modelling errors
on purpose, which is correct and useful); the blanket fallback is the problem.
**Verified** by reading.

### M3 — Misconfigured public key throws an uncaught NPE

`JWTIdentityService.getPublicKey()` returns the configured value **verbatim** when it is
not an existing file (`:37-39`), and returns `null` when the read fails (`:33-36`). In the
provider, `PemReader.readPemObject()` then returns `null` and `pemObject.getContent()`
throws `NullPointerException` — which is **not** in the provider's catch list and escapes
the filter as a 500.

The default was fixed since planning (it now reads `${PLONE_PUBLIC_KEY:ec-ed25519-pub-key.pem}`,
matching the keys the repo actually generates), so this now only fires on genuine
misconfiguration. It should still fail with a clear message at startup rather than an NPE
per request. **Verified** by reading.

Related, same file: `Security.addProvider(new BouncyCastleProvider())` runs on **every
request**, and `getPublicKey()` does a `File.exists()` plus a full file read per request.
The parsed `PublicKey` should be cached.

### M4 — Post-commit engine calls swallow their own exceptions

`utils.py:318` — `SideEffectDataManager.tpc_finish` does
`SIDE_EFFECT_WORKER.submit(self.callable, *self.args)` and **discards the returned
`Future`**. The surrounding `try/except` only catches a failure of `submit()` itself, so an
exception raised *inside* the callable is stored in the unreferenced Future and lost
silently.

Consequence: a BPMN signal that fails to reach Operaton after the Plone transaction
commits leaves **no log line and no trace**. Deferring to `tpc_finish` is the right call
(the alternative corrupts the database), but the result needs a completion callback that
logs failures.

`SIDE_EFFECT_WORKER` (`utils.py:273`) is also a module-global single-worker
`ThreadPoolExecutor` with no shutdown hook and no backpressure. **Verified** by reading.

### M5 — `parents()` loops select the outermost match, not the nearest

`viewlets/bpm_attachments_tasks_viewlet.py:15-17`:

```python
for context in parents(self.context, IProcessContext):
    self.base_url = context.absolute_url()
```

`parents()` walks the acquisition chain **upward from the context**, so with no `break`
the last assignment wins — the **topmost** process context, not the nearest. The outer
`IBpmAttachments` loop (`:18`) has the same shape. `adapters/security.py:21-23` gets this
right (it `break`s on the first match), as does the inner `for proxy` loop.

This was latent while `IBpmProxy` was the only process context. The new
`IProcessContext` behavior can be enabled on **any** folderish type, so nesting is now
plausible and the bug becomes reachable: task links would point at the wrong ancestor.

Same file: `self.tasks` and `self.base_url` have **no class-level defaults**. The template
guards `view/tasks|nothing`, but uses `view/base_url` unguarded inside that block.
Co-occurrence makes this hard to trigger today — recorded as robustness, not a live bug.
**Verified** by reading the module, `parents()`, and the template.

### M6 — Five runtime dependencies are imported but not declared

`backend/pyproject.toml`'s `[dependencies]` lists 11 packages. These are imported by the
package but absent from it, arriving only transitively via Plone:

`borg.localrole` (`adapters/security.py`), `plone.app.contentrules` (`actions/signal.py`),
`plone.stringinterp` (5 files), `plone.schema` (3 files), `plone.app.portlets` (2 files).

`plone.stringinterp` and `borg.localrole` carry the string-interpolation and dynamic
local-role features — load-bearing, not incidental. A Plone version that drops one of
these from its transitive set breaks the add-on with an ImportError.

**Verified** by extracting the `[dependencies]` block and grepping it specifically — my
first pass matched the `[tool.uv] constraint-dependencies` block by mistake and wrongly
cleared this finding.

### M7 — Orphaned root `uv.lock`

A tracked 750 KB `uv.lock` sits at the repo root, but **there is no root `pyproject.toml`**
— so it locks nothing. It was added by the monorepo restructure and has already drifted
from the real `backend/uv.lock`. Every `uv` invocation and `UV_PROJECT_ENVIRONMENT` target
`backend/`. Safe to delete. **Verified** by `git ls-files` + absence of root `pyproject.toml`.

### M8 — Cockpit plugin JS is committed twice, byte-identical

`fixture/operaton/src/main/resources/app/` and
`…/META-INF/resources/webjars/operaton/app/` are **identical** (`diff -rq` → no
differences), 7.0 MB each. `make fetch-plugins` writes every file to both paths, so
~7 MB of the repo is a redundant second copy with nothing enforcing the two trees stay in
sync. Only the `META-INF` path is servable by Spring. **Verified** by `diff -rq` and `du`.

### M9 — Pre-commit config is gitignored, and its excludes are stale

`.gitignore:44` ignores `.pre-commit-config.yaml`, so the hooks are purely local and no
contributor ever gets them (`git check-ignore -v` confirms). Its `exclude` patterns also
still use the pre-monorepo prefix `^src/collective/bpmproxy/browser/static/`, which no
longer matches `backend/src/...`, so the generated-bundle exclusions silently do nothing.
It pins ruff `v0.12.5` while `0.16.x` is in use locally. **Verified** by reading.

### M10 — Machine-specific absolute path in a committed Makefile

`fixture/operaton/Makefile`'s `test` target hardcodes
`-Dmaven.repo.local=/workspace/collective.bpmproxy/tmp/.m2/repository`. `make test` cannot
work for anyone whose checkout is elsewhere. `devenv.nix` does the same thing correctly via
`$DEVENV_ROOT`. **Verified** by reading.

### M11 — Two more defects in the same Makefile

- `clean: $(RM) $(ARTIFACT_NAME)-*.tar.*` — **`ARTIFACT_NAME` is never defined**, so this
  expands to `rm -f -*.tar.*`. Harmless today, but it is not doing what it says.
- The `shell` target is malformed: `.PHONY: shell` is followed directly by a recipe line
  (`nix develop`) with no `shell:` rule, so the recipe attaches to `.PHONY` and
  `make shell` silently does nothing — confirmed: `make -n shell` → *"Nothing to be done
  for 'shell'"*.

Also `start`/`watch` call bare `mvn`, while `devenv.nix` uses `./mvnw`. **Verified** by
`make -n`.

### M12 — CI cannot catch lockfile drift or TypeScript errors

- `uv sync --extra test` runs **without** `--locked`/`--frozen`, so a `uv.lock` that no
  longer matches `pyproject.toml` will not fail the build.
- `frontend-classic/` has **no `tsconfig.json`** despite `typescript` being a
  devDependency. Vite transpiles TS without type-checking, so **nothing type-checks the
  frontend sources** — in or out of CI. (`diagram.ts` already has an unused `warnings`
  binding that a type-check pass would surface.)

**Verified** by reading the workflow and `ls`.

### M13 — H2 ships in the production jar; security pins are stale

`fixture/operaton/pom.xml`: `com.h2database:h2` is declared with **no `<scope>test</scope>`**,
so the in-memory database is packaged into the fat jar and the container image.

The two hard-pinned, non-BOM-managed dependencies are both on the security-critical path
and both old: `org.bouncycastle:bcpkix-jdk15to18:1.71` (2022) and
`com.nimbusds:nimbus-jose-jwt:9.31` (2023) — the libraries doing the JWT parsing and
EdDSA verification in H1/H2. Worth a deliberate upgrade + CVE check.
**Verified** by reading.

### M14 — `AGENTS.md` is materially stale and actively misleading

The prose is broadly current; the structural claims are not. Verified-false statements:

| Claim | Reality |
|---|---|
| "Migrations Landed **(staged in working tree)**" / "complete on disk (staged, not yet committed)" (`:11,:13`) | All four are committed (`5bd0416`, `67f6a71`) |
| Directory tree puts `pyproject.toml`, `tox.ini`, `CHANGES.rst`, `LICENSE.GPL` at the repo root | None exist at root; all are under `backend/` |
| Tree lists `src/collective/bpmproxy/` as "Main Python package" | No root `src/`; it is `backend/src/…` — mislabels the ~110-line subtree beneath it |
| Tree lists `.gitlab-ci.yml` (`:159`) and `.travis.yml` (`:160`) | Both deleted in `5bd0416`; neither exists |
| `metadata.xml  # Version 1003` (`:232`) | File says `<version>1001</version>` |
| `Cockpit: /camunda (port 8081)` (`:73`) | Path is `/operaton/app/cockpit/default/` |
| Test-suite table | Names 18 test files; **36** exist on disk |
| Frontend dependency table | Lists 4 packages; `package.json` declares 11 runtime deps |
| editor-bot / plone-bot described as "Robocorp RPA" | Migrated to purjo/uv in `104e47b` |

Since this file is the project's agent-facing brief, its errors propagate into future
work. **Verified** item by item against disk.

### M15 — `fixture/operaton/README.md` documents a profile that does not exist

- Claims **Java 17**; `pom.xml` sets `java.version` 21 and `flake.nix` uses JDK/JRE 21.
- Documents an **`h2` profile** (`./mvnw spring-boot:run -Dspring-boot.run.profiles=h2`).
  `application.yml` defines only `oauth2` and `postgres`; **H2 is the default**, so the
  documented command activates a profile that isn't there.
- `devenv.nix:4`'s own header comment also says "JDK 17" while `:51` sets `pkgs.jdk21`.

**Verified** by `grep "on-profile"` across `application.yml`.

---

## Low

### L1 — Deprecated APIs
- `testing.py:7,46` — `from plone.testing import z2` / `z2.ZSERVER_FIXTURE`. The Plone 5
  path; Plone 6 is `plone.testing.zope`. A leftover the migration missed.
- `client.py:58` — `datetime.datetime.utcnow()`, deprecated since Python 3.12. Use
  `datetime.now(datetime.UTC)`.

The suite also emits 189 warnings, several being Plone 7 removals already flagged
(`IPatternsSettings`, `IBundleRegistry`, `IResourceRegistry` moved to `plone.base.interfaces`).

### L2 — Duplicated logic
- `interpolate()` is defined twice — `utils.py:115` and `actions/signal.py:63` — as
  near-identical recursive functions. `portlets/signal.py` imports the `actions` copy.
- The "redirect to next task" block (build URL, append anonymous `?token=`, append
  `#autotoc-item-autotoc-0`, `break`, swallow `ApiException`) appears twice in
  `views/bpm_form_view.py`.
- The businessKey → `attachments_key` `try/except` appears twice in `bpm_form_view.py`
  and again in `views/bpm_attachments_view.py`.
- `VocabItem` is declared in both `vocabularies/available_process_definitions.py:11` and
  `vocabularies/task_attachments.py:9`; the latter is unused.
- The five process-configuration fields are declared verbatim in **both** `IBpmProxy`
  (`content/bpm_proxy.py`) and `IProcessContextBehavior`
  (`behaviors/process_context.py`). `IBpmProxy` now *inherits* the behavior schema and
  then redeclares every field — the redeclarations can go.

### L3 — Brittle process-definition filtering
`portlets/tasks.py:115` carries its own warning: filtering by process definition key
parses `task.process_definition_id.split(":", 1)[0]`, which relies on the engine's
default ID generator prefixing IDs with the key. A generator change breaks the portlet
silently. Querying by key server-side would be robust.

### L4 — `diagram.ts` observer is never disconnected
`frontend-classic/src/diagram.ts:38` installs a `MutationObserver` on the closest
`.autotabs` (or `document.body`) and never calls `disconnect()` after the single render,
so it keeps firing for the life of the page. Also `rendered = true` is set **before**
`await viewer.importXML(...)` (`:17`), which correctly de-duplicates but means a failed
import can never be retried. The visibility-gating fix itself is sound.

### L5 — Example bots: dead topic mappings and half-covered processes
`examples/plone-bot/pyproject.toml` maps `Plone Update Title` and
`Plone Update Description`, but **no BPMN in the repo declares either topic** — the bot
long-polls for work that never arrives. (The reverse problem, orphan Robot tasks, was
fixed during this review.)

The two bots are also **mutually dependent**, and neither `Makefile` reflects it:

| Process | Needs from editor-bot | Needs from plone-bot | `DEPLOY_FILES` |
|---|---|---|---|
| `FromIdeaToArticle.bpmn` | 6 `GPT *` topics | `Plone Submit Content` | editor-bot only |
| `ReviewAssistant.bpmn` | `GPT Create Article` | `Plone Get Content`, `Plone Update Text` | plone-bot only |

So `make run` in either directory stalls its process at the other bot's service task.
**Verified** by cross-referencing `camunda:topic` attributes against both `pyproject.toml`s.

### L6 — Dead code and stray markers
- `actions/configure.zcml:12-14` — commented-out `<adapter factory=".signal.PayloadValidator"/>`;
  no `PayloadValidator` class exists.
- `utils.py:70,92,96,99` — four commented-out `print()` debug lines.
- `views/configure.zcml:54-56` — `<!-- BBB -->` `folderListing` alias duplicating
  `contentlistings`.
- `tests/test_robot.py:1` — malformed `# noqa: E501,,,`.
- `test_viewlet_bpm_attachments_viewlet.py:45` — `XXX would be nice to have this test working`
  (disabled test).
- Stale `__pycache__` for deleted `test_zz_*` modules, and `.cpython-314` bytecode beside
  `.cpython-312` — two interpreters have run in-tree.

### L7 — Robot Framework suites are unrunnable
Four suites in `tests/robot/` plus `tests/test_robot.py`. `pytest` excludes them
(`--ignore-glob=*test_robot*`); they need `zope.testrunner`, which no Makefile target or
CI job provides. `test_example.robot` is still the boilerplate template. They are
scaffolding that cannot currently execute — either wire them up or drop them.

### L8 — Remaining documentation gaps
- `frontend/README.md` — the Volto design note (a genuinely useful REST-endpoint plan)
  uses pre-monorepo `src/collective/bpmproxy/…` paths throughout.
- `docs/AGENTS.md` documents `playwright-python scripts/e2e_request_for_quote.py`, but no
  `playwright-python` command is defined anywhere in the repo; `devenv.nix` provides only
  `e2e-smoke`. The documented invocation depends on an external wrapper.
- `backend/news/` has 4 towncrier fragments (`+oidc`, `+operaton`, `+plone6`,
  `+vite-modeler`) and **none** for the case-demo, renovation-demo, or diagram-visibility
  work.
- **No `LICENSE` at the repo root** — the only copies are `backend/LICENSE.{GPL,rst}` and
  `examples/plone-bot/LICENSE`. For a GPLv2 project the root is where people look.
- `backend/docs/` is a dead Sphinx skeleton: `index.rst` is 5 lines with no toctree, and
  `conf.py` still carries a py2 `# -*- coding: utf-8 -*-` header.

### L9 — Dev fixture credentials, for the record
`admin`/`admin` (`application.yml`, `realm-plone.json`), `operaton-secret` as a plaintext
client secret, `sslRequired: "none"`, and `manager`/`manager` + `editor`/`editor` from
`bootstrap_site.py`. All correct for a local fixture and all appropriately committed —
noted only so nobody mistakes `devenv/keycloak/realm-plone.json` for a deployment template.
The generated `ec-ed25519-*.pem` keypair is correctly untracked (`.gitignore` `*.pem`,
`git ls-files '*.pem'` → empty) and generated per-machine by `enterShell`.

---

---

## What the fix pass changed

A follow-up pass implemented 32 of the 43 backlog items. Everything below was
verified by running the relevant suite, not by inspection alone. Remaining items
are listed at the end of this section with the reason each was left.

### Verification baseline after the fixes

| Suite | Before | After |
|---|---|---|
| `pytest` (backend) | 207 passed | **209 passed**, 3 deselected |
| `ruff check` / `format --check` | clean | clean (86 files) |
| `uv sync --locked` | not enforced in CI | in sync; now enforced |
| `npm run typecheck` | did not exist | **passes** (new `tsconfig.json`) |
| `mvn test` (Java) | 35 passed | **42 passed** |
| Operaton boot (default H2 profile) | not exercised | **starts**, `/engine-rest/engine` 200 |

### The security fixes, proven end-to-end

A live engine was started with the repo's ed25519 key and probed with tokens
minted the same way `client.py` mints them:

| Token | Before | After |
|---|---|---|
| valid, 1 h expiry | 200 | **200** |
| **expired by 1 h** | **200** | **401** |
| no `exp` claim at all | 200 | **401** |
| signed with a different key | 401 | **401** |
| no token | 401 | **401** |

That second row is the finding: an expired token was previously accepted
indefinitely. Verification now lives in one place (`JWTTokens.java`) and checks
the JWS algorithm, the signature, `exp` and `nbf`; `JWTIdentityService` calls it
too, so it no longer trusts claims from a string it has not verified itself. The
parsed key is cached and the BouncyCastle provider is registered once, instead of
per request. Java tests went 35 → 42, the new ones covering expiry, a missing
`exp`, algorithm substitution, an unconfigured key, and — in the identity
service — that a wrongly-signed or expired token's claims are *not* adopted.

`JWTIdentityServiceTest` was rewritten to use real keys and real signed tokens.
It previously mocked `SignedJWT.parse` statically, which is precisely why it
could not catch missing verification.

For the Python validator, both bugs are fixed and proven: bounds are now
enforced (a truthy-but-too-small value used to pass), and because a
`ValidationError` replaced the bare `assert`s, validation survives `python -O` —
checked by running the same case under both interpreters.

### One change was made and then reversed

Scoping `com.h2database:h2` to `test` looked obviously right — the review had
flagged H2 shipping in the production fat jar. Booting the application proved
otherwise: it failed with `Cannot load driver class: org.h2.Driver`, because the
**default** Spring profile's datasource *is* `jdbc:h2:mem:operaton`, which is the
no-profile `./mvnw spring-boot:run` path the fixture README documents. The change
was reverted and the dependency now carries a comment explaining why it must stay
on the runtime classpath. **Finding M13's H2 half is withdrawn**; the stale
BouncyCastle/nimbus pins stand.

### One finding was upgraded by runtime evidence

M8 (the duplicated cockpit plugin trees) was confirmed by serving both paths:
`/operaton/app/cockpit/scripts/config.js` returns **200**, while
`/app/cockpit/scripts/config.js` returns **404**. The
`src/main/resources/app/` tree is genuinely unserved dead weight, so deleting it
is safe — left as a backlog item only because it is a bulk deletion better done
in its own commit.

Separately, while probing authorization: a token whose `groups` claim does *not*
include `camunda-admin` still received **200** from
`/engine-rest/authorization/count`. This is pre-existing behaviour, unrelated to
the JWT changes (unit tests confirm claims are mapped correctly), and it
strengthens **M1** — engine authorization is enabled but permits more than it
appears to. M1 was deliberately left alone as a design decision.

### Deliberately left undone

| Item | Why |
|---|---|
| Land the untracked work in commits (H6) | Commit structure is the maintainer's call; nothing was committed or staged in this pass. |
| Scope the global engine authorizations (M1) | Design decision that could break the demo flows — and see the observation above. |
| The anonymous-token model (S7) | Needs an explicit product decision, not a patch. |
| Fate of the Robot suites (L7) | Wire up or delete is a judgement call. |
| De-duplicate the cockpit trees (M8) | Verified safe; left as a standalone bulk-deletion commit. |
| What `docs/` is, and `backend/docs/` (L8) | Both are "decide, then act" items. |
| `process_context` upgrade step | Needs a decision on the profile version and migration story. |
| Query tasks by definition key (L3) | Changes the client API; wants a live-engine test to land with it. |
| Java dependency pins (M13, partial) | BouncyCastle/nimbus upgrades need their own CVE check and test pass. |
| Wider `process_context` test coverage | Best written alongside the upgrade step above. |

## Fixed while this review was running

Recorded so they are not re-reported. Each was a real finding when planning began and is
verified fixed on disk now:

| Was | Now |
|---|---|
| `make test-offline` called a nonexistent backend target | `backend/Makefile:34` defines it; `test-live` also now handles pytest's exit-5 ("no tests ran") gracefully |
| `PatternsSettings` bound to `IBpmProxy`, so `pat-code-editor` missed behavior-enabled types | `adapters/configure.zcml:6` uses `IProcessContext` |
| Orphan-attachment view walked `IBpmProxy` | `bpm_attachments_orphans_view.py:35` uses `IProcessContext` |
| Dead `IProcessContext`→`IBpmProxy` fallbacks in the tasks viewlet | Removed |
| `case_demo.install` left the required `process_definition_key` unset | Now best-effort preselects the first deployed definition, with a documented fallback |
| `plone.public-key` defaulted to `ec-prime256v1-pub-key.pem`, a file the repo never ships | Now defaults to `ec-ed25519-pub-key.pem` |
| No `operaton`-marked tests existed, so `make test-live` collected nothing | `tests/test_live_engine.py` adds 3 |
| Orphan Robot tasks in plone-bot with no topic mapping | Topics and tasks now match 5↔5 (but see L5) |
| Stray `docs/page@<hash>.webm` Playwright leftovers, one 0 bytes | Cleaned up |

## One finding I withdrew

While planning I flagged that replacing two `getattr(self.context, "diagram_enabled", False)`
guards with direct `self.process_context.diagram_enabled` had removed a safe default and
could raise `AttributeError`. On closer reading **it cannot**, by two independent
mechanisms: `BpmProxyStartFormView` is registered `for="…IProcessContext"`, so its context
always satisfies the interface; and `BpmProxyTaskFormView` wraps any non-process content in
`BpmProxy(ProxyBase)` (`bpm_form_view.py:228-232`), whose subclass attributes
(`diagram_enabled = False`, `attachments_enabled = False`) shadow the proxied object. The
refactor is sound. Recorded here because it shaped the plan.

The `get_process_context()` helper is still worth simplifying: its second branch
(`if not IProcessContext.providedBy(context): return context`) is unreachable from the
start-form view and only meaningful for the `ProxyBase` path, which makes the control flow
harder to read than it needs to be.

## Note on the `process_context` design

The marker-plus-behavior split (`IProcessContext` marker, `IProcessContextBehavior` schema)
is the right Plone idiom, and re-registering the view against the marker is what makes it
work for both `Bpm Proxy` and behavior-enabled types. Two things deserve attention before
it lands:

1. **No upgrade step.** `IBpmProxy` changed base classes, and the `view` registration moved
   from `IBpmProxy` to `IProcessContext`. Existing `Bpm Proxy` content works (the interface
   is inherited), but there is no upgrade step and `profiles/case_demo/metadata.xml` is
   version `1` with none defined.
2. **The behavior adapter is a transparent proxy.** `ProcessContextBehavior.__setattr__`
   forwards everything except `context` straight onto the content object, with no schema
   guard — so any future attribute set on the adapter silently becomes content state.

Neither blocks the feature; both are cheaper to fix now than after content exists.
