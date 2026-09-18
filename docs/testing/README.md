# Browser test campaign

`scripts/uitest/` drives `collective.bpmproxy` end to end in a headless
browser. It is simultaneously the manual test suite and the generator for the
[end-user guide](../user/README.md): the call that asserts a page is in the
expected state is the same call that writes the screenshot. There is no path
that produces documentation from a failing run.

## Running it

The stack has to be up first — see [Setting up](../user/01-setup.md).

```shell
devenv up -d              # PostgreSQL, Keycloak, Mailpit, Operaton
devenv processes wait
make bootstrap-site       # once, with Plone stopped
make start                # Plone on :8080, in another terminal

make ui-test              # assert only, no images  <- the fix loop
make screenshots          # assert + write docs/user/images + check for drift
```

Useful flags (`ui-test` passes them straight through):

| Flag | Effect |
| --- | --- |
| `--scenario <name>` | Run one area; repeatable |
| `--keep` | Leave created content and deployments in place |
| `--headed` | Watch it happen |
| `--check-docs` | Fail on screenshot/guide drift |

Everything the suite creates is prefixed `uitest-` and swept both before and
after a run, so a crashed run cannot poison the next one. The checked-in
`examples/` assets are never modified; where the local fixture cannot run them
as written, the *deployed copy* is transformed (see `fixtures.TRANSFORMS`).

## How a screenshot stays honest

`shots.py` declares every image once, with the guide page that must reference
it. `--check-docs` fails on either half of the drift:

- an image no page references;
- a page referencing an image no scenario produces.

Adding a screenshot is therefore a three-step move that cannot be done
halfway: declare the `Shot`, take it from a scenario, reference it from the
page.

All images are Full HD (1920x1080), matching the recording convention in
[../AGENTS.md](../AGENTS.md), so stills and the walkthrough videos look like
the same product.

### How stable the images are

Screenshots are taken with animations and the caret disabled, and with every
rendered timestamp hidden -- the toolbar clock is written by JavaScript at page
load, so without that no two runs ever matched. The engine's deployment ids and
times are masked out of the deployments table.

Ten of the seventeen images are byte-identical across consecutive runs. The
remaining seven embed identifiers the engine mints per run -- task ids,
attachment container UUIDs, and the task lists those produce -- so they differ
slightly even when nothing has changed. Review a screenshot diff by looking at
it, not by trusting that an unchanged page produces an unchanged file.

What `--check-docs` does guarantee is structural: every declared screenshot is
taken by a passing scenario, and every image the guide references exists.

## The case matrix

Case ids are stable; they appear in the runner output and in the
[issue log](issue-log.md).

| Area | Cases |
| --- | --- |
| **A** Install and setup | A1 services reachable · A2 add-on installed · A3 modeler add-on · A5 `camunda-admin` group · A7 `tenant_ids` record |
| **B** Modeler control panel | B1 BPMN modeler · B2 DMN modeler · B3 form playground · B4 deploy (and the `Accept` header requirement) · B5 deployment listing · B6 cascading delete · B7 refused below `camunda-admin` |
| **C** Bpm Proxy | C1 definition vocabulary · C2 toggles · C3 `pat-code-editor` widgets · C4 start form renders · C5 substitutions · C6 server-side validation · C7 instance started with the business key · C8 diagram, drawn only when visible · C9 task list tab |
| **D** Task forms | D1 renders with current variables · D2 breadcrumbs · D3 completion · D4 foreign task refused · D5 `@@edit` / `++add++` delegation |
| **E** Attachments | E1 lazy container creation · E2 upload · E3 attachments viewlet · E4 tasks viewlet · E5 dynamic roles · E6 orphan view is manager-only |
| **F** Portlets | F1 submit-plan starts the process · F2 context-filtered task list · F4 `@@redirect-to-bpm-task` · F5 message dispatch |
| **G** Content rules | G1 seven rules installed · G2 signal-started process · G5 dispatch deferred to commit |
| **H** Plone forms as tasks | H1 add · H2 edit |
| **J** Anonymous | J1 public start form · J2 the `token=` round trip |
| **K** Multi-tenancy | K1 registry record writable · K2 restricting tenants never widens the vocabulary |
| **L** Bundles | L2 conditional loading · L3 no console or network errors on any page (enforced globally) |

## What it does not cover

- **Operaton Cockpit and Keycloak's own UI.** Keycloak must be running —
  Operaton waits for its issuer metadata — but neither UI is under test.
- **The RPA example bots** (`examples/editor-bot`, `examples/plone-bot`).
  They need an `OPENAI_API_KEY` and egress to `api.openai.com`.
- **Mail delivery.** The fixture configures no mail connector; see
  [Limitations](../user/11-limitations.md).

## Environment hazards

Several failures during this campaign came from the environment rather than
the product, and they surface far from their cause. They are written up in the
[issue log](issue-log.md) — read E1 to E4 there before debugging a stack that
will not start.

The most important one: **only one devenv stack may use
`.devenv/state/` at a time.** Two stacks sharing that directory (for example
one inside a container and one on the host) will fight over PostgreSQL's
`postmaster.pid` and Keycloak's H2 lock, and the symptoms look like product
bugs three layers away.
