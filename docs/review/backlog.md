# Review backlog

> **Status (2026-09-18):** the items marked `[x]` below were implemented and
> verified in the fix pass. See
> [What the fix pass changed](2026-09-18-project-review.md#what-the-fix-pass-changed).
> Everything still marked `[ ]` is either a decision for the maintainer or was
> deliberately left alone -- the reasons are recorded in the report.

Derived from [2026-09-18-project-review.md](2026-09-18-project-review.md). Ordered so
that cheap, high-impact work comes first. Finding IDs in brackets.

**Sizing:** ▪ quick (minutes) · ▪▪ small (under an hour) · ▪▪▪ needs design/discussion

---

## 0. Do this first

- [ ] ▪▪▪ **Land the untracked work in reviewable commits** [H6]
      7,382 lines across 65 untracked files, plus 28 modified tracked files. No review
      history, no CI, no backup outside this working tree — and it includes
      security-relevant changes (`adapters/security.py`) and two new engine-facing demo
      profiles. Suggested split: (1) `process_context` behavior + `case_demo`,
      (2) `renovation_demo` + its bot + example BPMN, (3) `scripts/uitest/` campaign,
      (4) `docs/` (see the `.gitignore` question in §4), (5) the `.agents/` skill.
      Everything below is easier once this is in git.

## 1. Unblock a fresh clone (both quick, both break documented workflows)

- [x] ▪ **Track the Maven wrapper properties** [C1]
      `.gitignore:11`'s `.mvn/` is a buildout-era rule that now hides
      `fixture/operaton/.mvn/wrapper/maven-wrapper.properties`. Negate it
      (`!fixture/operaton/.mvn/`) or scope the original, then commit the file. Verify by
      cloning to a temp dir and running `./mvnw -v`.
- [x] ▪ **Fix the fixture Makefile's default target** [C2]
      `all: artifact` references a target that does not exist, so plain `make` aborts.
      Point `all` at `build` (or define `artifact`).

## 2. Close the JWT authentication gaps

Group these — they touch the same two files and want one test pass.

- [x] ▪▪ **Validate `exp`/`nbf` before accepting a token** [H1]
      `JWTAuthenticationProvider.java:42-72` checks only the signature, so a leaked token
      never expires even though Plone sets a 1-hour `exp`. Assert the `alg` header while
      you are there. **Add the missing expired-token test** — the existing 7 tests cover
      every other rejection path.
- [x] ▪▪ **Stop trusting unverified claims** [H2]
      Pass a verified claims object into `JWTIdentityService` instead of handing it the raw
      JWT string to re-parse (`JWTIdentityService.java:46-50`).
- [x] ▪▪ **Add a Maven job to CI** [H5]
      The 35 JUnit tests — including every test above — never run on a PR. This is what
      makes the two fixes durable, so do it in the same batch. Consider `nix flake check`
      too, which would have caught C1.
- [x] ▪ **Fail cleanly on a missing public key** [M3]
      Validate at startup instead of throwing an uncaught NPE per request; cache the parsed
      `PublicKey` and hoist `Security.addProvider` out of the request path.

## 3. Fix the form-validation bugs

- [x] ▪ **Fix the `min`/`max` precedence bug** [H3]
      `data.get(key) or 0 >= min_value` parses as `data.get(key) or (0 >= min_value)`, so
      neither bound is ever enforced (`utils.py:210-218`). Fix the `str + int` message
      concatenation in the same pass (`min`, `max`, `minLength`, `maxLength`).
      **Note:** `test_utils_more.py` currently asserts the resulting `TypeError` — that
      test pins the bug and must be updated alongside.
- [x] ▪▪ **Replace the bare `assert`s with real exceptions** [H4]
      Every check in `validate_camunda_form` is an `assert`, so `python -O` silently
      disables validation of untrusted submissions.

## 4. Repo hygiene (all quick, all independent)

- [x] ▪ **Delete the orphaned root `uv.lock`** [M7] — 750 KB locking nothing; no root `pyproject.toml`.
- [x] ▪ **Un-ignore `.pre-commit-config.yaml` and fix its excludes** [M9]
      Currently gitignored so nobody gets the hooks; its `^src/collective/…` excludes no
      longer match `backend/src/…`; ruff pin is 0.12.5 vs 0.16.x in use.
- [ ] ▪ **De-duplicate the cockpit plugin trees** [M8]
      `diff -rq` shows the two 7 MB trees are identical. Keep the servable `META-INF` path;
      make `fetch-plugins` write once.
- [x] ▪ **Drop the hardcoded absolute path** [M10] — use `$(DEVENV_ROOT)` or a variable in
      the fixture Makefile's `test` target.
- [x] ▪ **Fix the malformed `shell` target and undefined `ARTIFACT_NAME`** [M11]
      `make shell` silently does nothing; `clean` expands to `rm -f -*.tar.*`.
- [ ] ▪ **Decide what `docs/` is** [L8, H6]
      14 MB, entirely untracked, now mixing deliverable guides (`docs/user/`,
      `docs/testing/`) with large `.webm` recordings. Either track the docs and gitignore
      the recordings, or gitignore the tree deliberately — right now a stray `git add .`
      would commit ~14 MB of video.
- [x] ▪ **Add a root `LICENSE`** [L8] — GPLv2 project with no licence file where people look.

## 5. Tighten CI

- [x] ▪ **Add `--locked` to `uv sync`** [M12] — lockfile drift currently cannot fail a build.
- [x] ▪▪ **Add a `tsconfig.json` and a type-check step** [M12]
      `typescript` is a devDependency but nothing type-checks the frontend; Vite only
      transpiles. Would surface e.g. the unused `warnings` binding in `diagram.ts`.
- [ ] ▪▪ **Decide the fate of the Robot suites** [L7]
      Excluded from pytest, need `zope.testrunner`, wired to no target, and
      `test_example.robot` is still boilerplate. Wire them up or delete them.

## 6. Correctness follow-ups

- [x] ▪▪ **Log failures from post-commit engine calls** [M4]
      `tpc_finish` discards the `Future`, so exceptions inside the callable vanish — a
      signal that fails to reach Operaton leaves no trace. Add a completion callback that
      logs. Consider a shutdown hook for the module-global executor.
- [x] ▪▪ **Take the nearest process context, not the outermost** [M5]
      `bpm_attachments_tasks_viewlet.py:15-18` assigns in the loop body with no `break`, so
      the topmost ancestor wins. Latent until now; the new behavior makes nesting
      plausible. `adapters/security.py` already does this correctly — match it. Add
      class-level defaults for `tasks`/`base_url` while you are in the file.
- [x] ▪▪ **Declare the five undeclared runtime dependencies** [M6]
      `borg.localrole`, `plone.app.contentrules`, `plone.stringinterp`, `plone.schema`,
      `plone.app.portlets` are imported but only arrive transitively via Plone.
- [x] ▪▪ **Stop returning raw exception text from the REST services** [M2]
      Keep `deploy.py`'s deliberate `HTTPError` forwarding (it surfaces useful modelling
      errors); replace the blanket `except Exception → str(e)` fallbacks.
- [ ] ▪▪▪ **Scope the global engine authorizations** [M1]
      `PROCESS_DEFINITION:ANY` + `CREATE_INSTANCE` for everyone makes
      `authorization.enabled` mostly decorative. Needs a decision on the intended model;
      at minimum document that the fixture is not a production shape.
- [ ] ▪▪ **Query tasks by process definition key** [L3]
      `portlets/tasks.py:115` parses `process_definition_id` and depends on the engine's
      ID-generator format, as its own `XXX` notes.

## 7. Finish the `process_context` feature

- [ ] ▪▪ **Add an upgrade step** [design note]
      `IBpmProxy` changed base classes and the `view` registration moved to
      `IProcessContext`. Existing content works by inheritance, but nothing is versioned:
      `profiles/case_demo/metadata.xml` is version `1` with no upgrade steps.
- [x] ▪▪ **Guard `ProcessContextBehavior.__setattr__`** [design note]
      It forwards every attribute onto the content object with no schema check, so any
      attribute set on the adapter silently becomes content state.
- [x] ▪ **Drop the duplicated field declarations** [L2]
      `IBpmProxy` inherits `IProcessContextBehavior` and then redeclares all five fields.
- [x] ▪ **Simplify `get_process_context()`** [withdrawn finding]
      Its `not IProcessContext.providedBy(context)` branch is unreachable from the
      start-form view and meaningful only for the `ProxyBase` path.
- [ ] ▪▪ **Widen the test coverage** — one 35-line test today; nothing renders a start form
      on a behavior-enabled type, and nothing covers the behavior adapter's `__setattr__`.

## 8. Documentation

- [x] ▪▪ **Rewrite `AGENTS.md`'s structural sections** [M14]
      Nine verified-false claims, including a pre-monorepo directory tree, a "staged, not
      yet committed" status line for committed work, CI files that no longer exist, and a
      test table naming 18 of 36 modules. This is the agent-facing brief, so its errors
      propagate. Consider generating the tree rather than hand-maintaining it.
- [x] ▪ **Fix `fixture/operaton/README.md`** [M15]
      Java 17 → 21; remove the documented `h2` profile (H2 is the *default*; only `oauth2`
      and `postgres` exist); correct the key filename. Also `devenv.nix:4` says "JDK 17"
      while `:51` sets `jdk21`.
- [x] ▪ **Update `frontend/README.md` paths** [L8] — pre-monorepo `src/collective/…` throughout.
- [x] ▪ **Define `playwright-python` or fix the docs** [L8]
      `docs/AGENTS.md` documents it as the runner for `e2e_request_for_quote.py`; no such
      command exists in the repo.
- [x] ▪ **Add the missing towncrier fragments** [L8] — nothing for case-demo,
      renovation-demo, or the diagram-visibility fix.
- [ ] ▪▪ **Decide whether `backend/docs/` lives or dies** [L8]
      A dead Sphinx skeleton: 5-line `index.rst`, no toctree, py2 header in `conf.py`.

## 9. Low priority

- [x] ▪ **Modernise deprecated APIs** [L1] — `plone.testing.z2` → `plone.testing.zope`;
      `datetime.utcnow()` → `datetime.now(datetime.UTC)`. Optionally clear the
      `plone.base.interfaces` import warnings ahead of Plone 7.
- [x] ▪▪ **Consolidate duplicated logic** [L2] — one `interpolate()`; extract the
      twice-repeated redirect and businessKey blocks; delete the unused second `VocabItem`.
- [x] ▪ **Disconnect the diagram `MutationObserver`** [L4] — never disconnected after the
      single render; a failed `importXML` can never retry.
- [x] ▪ **Fix the example bots** [L5] — remove the two topic mappings no BPMN declares, and
      make `DEPLOY_FILES` reflect that the two bots are mutually dependent (neither
      `make run` can complete its process alone).
- [x] ▪ **Sweep dead code** [L6] — commented-out `PayloadValidator` adapter (class does not
      exist), four commented `print()`s, BBB `folderListing` alias, malformed
      `# noqa: E501,,,`, stale `test_zz_*` bytecode.
- [ ] ▪▪▪ **Review the Java dependency pins** [M13] — `h2` needs `<scope>test</scope>`
      (it currently ships in the fat jar); BouncyCastle 1.71 and nimbus-jose-jwt 9.31 are
      the JWT/EdDSA path and both predate 2024.
- [ ] ▪▪▪ **Decide on the anonymous token model** [S7, review §Medium]
      `client.py:70-72` accepts a caller-supplied `request.form["token"]` as the anonymous
      identity. Guessing a v4 UUID is impractical, so this is likely fine by design — but
      it is undocumented and deserves an explicit comment either way.

---

## Coverage check

Every Critical/High finding appears above: C1 §1, C2 §1, H1/H2 §2, H3/H4 §3, H5 §2, H6 §0.
Medium: M1 §6, M2 §6, M3 §2, M4 §6, M5 §6, M6 §6, M7 §4, M8 §4, M9 §4, M10 §4, M11 §4,
M12 §5, M13 §9, M14 §8, M15 §8. Low: L1–L9 across §4, §5, §8, §9.
