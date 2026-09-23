# Renovation-project browser scenario

This is the reproducible demo scenario for the `collective.bpmproxy:renovation_demo`
profile: a folderish `Renovation Project` type driven by a real five-state
Plone workflow and three chained Operaton processes (Plan Review, Work &
Extra-Work, Final Review), correlated by the project's UUID and closed back
to Plone by the `renovation-bot` purjo worker. It follows the recording
architecture documented in [AGENTS.md](AGENTS.md): isolated Playwright contexts
per actor, a Cockpit observer spanning the whole run, human-paced cursor and
clicks, and a picture-in-picture composite aligned to real wall-clock offsets.

This scenario has **three named personas** (Owner, Contractor, Inspector) who
each act at more than one point in the story, separated by other actors' turns.
Each turn is therefore its own short recorded context, and the PIP composer here
(`compose_recording()` in `scripts/e2e_renovation_project.py`) places this list
of clips onto the Cockpit timeline.

Each turn begins with an 8-second persona interlude, the long form bodies are
pasted at clipboard speed, and the observer holds the active process instance
for six seconds after every persona turn. The final Cockpit segment opens the
completed process instance's **History** view, collapses the left information
panel while keeping the audit panel visible, and remains there for five
seconds.

## Prerequisites

Run the following from the repository root. Start the services, wait for
Operaton, bootstrap the site (with Plone **stopped** — bootstrapping opens
the ZODB directly), then start Plone:

```sh
devenv up -d
until curl -sf http://127.0.0.1:8081/engine-rest/engine >/dev/null; do sleep 5; done
make bootstrap-site
make bootstrap-renovation-demo
make start
until curl -sf http://127.0.0.1:8080/Plone >/dev/null; do sleep 3; done
```

The recording runner also clears every existing Operaton deployment before
deploying this scenario's assets, so each take starts with clean Plone and
clean Operaton state.

`devenv up -d` often prints `Daemon failed to start within 120s` even when
everything comes up — trust the `curl` gate, not that message; see
[devenv-browser-smoke.md](devenv-browser-smoke.md) for the failures that
*are* real.

`make bootstrap-renovation-demo` runs `scripts/bootstrap_renovation_demo.py`
via `zconsole`, on top of `make bootstrap-site`'s Plone site. It:

- installs `collective.bpmproxy:renovation_demo` (which itself creates the
  `Renovation Owners` / `Renovation Contractors` / `Renovation Inspectors`
  groups, the `renovation-bot` service account, and a
  `renovation-project-demo` content item — see
  `backend/src/collective/bpmproxy/renovation_demo.py`);
- creates three named demo users (`owner`, `contractor`, `inspector`) and
  adds each to its matching group;
- sets a known password on `renovation-bot` so `examples/renovation-bot/`
  can authenticate.

The scenario expects these endpoints and users:

| Service | URL |
| --- | --- |
| Plone | `http://localhost:8080/Plone` |
| Operaton REST/Cockpit | `http://localhost:8081` |
| Keycloak | `http://localhost:8082` |
| Mailpit | `http://localhost:8025` |

| User | Password | Role/use |
| --- | --- | --- |
| `owner` | `owner` | Renovation Owners — plan/final approvals, extra-work approval |
| `contractor` | `contractor` | Renovation Contractors — drafts, submits, documents, requests |
| `inspector` | `inspector` | Renovation Inspectors — independent plan/final compliance review |
| `renovation-bot` | `renovation-bot` | Site Administrator — the purjo worker's service account |
| `admin` | `admin` | Keycloak/Operaton Cockpit observer |

Deploy the three BPMN processes and their forms, then start the purjo worker
that drives Plone workflow transitions from Camunda (**the recording will
stall waiting for tasks that never get created if this isn't running**):

```sh
cd examples/renovation-bot
cp secrets.example.json secrets.json   # set PLONE_AUTHORIZATION for renovation-bot
cp secrets.example.env secrets.env     # OAuth2 credentials purjo needs for engine-rest
make deploy
make serve &
cd ../..
```

`examples/renovation-bot-py/` is a pure-Python alternative worker against
the same `Plone Workflow Transition` topic -- interchangeable with the purjo
one above, so only one needs to run at a time. See its README for setup;
`make deploy` above still applies since both workers share the same
deployed BPMN.

Run the recording with the browser skill's headless Playwright wrapper:

```sh
playwright-python scripts/e2e_renovation_project.py
```

## Personas and user stories

| Persona | Story | Expected result |
| --- | --- | --- |
| Contractor | Drafts the plan (adds a plan Document with a short remodel description), then clicks **Submit plan**. | Project state moves to *Plan under review*; a Plan Review process instance starts, correlated to the project's UUID. |
| Owner | Opens **Owner reviews plan** and approves. | The Owner branch of the parallel review completes. |
| Inspector | Opens **Inspector reviews plan** and approves. | Both branches join; `renovation-bot` transitions the project to *Work in progress*. |
| Contractor | Adds a `Document` with a short work-log entry directly into the project (not into a sub-folder; not tagged "Work Log" -- see *Fixture adaptations*). | The **Document completed work** Camunda task auto-completes with no task form ever submitted — `collective.bpmproxy.subscribers.tasks.completeAddTask` matches the add event against the project's own UUID. |
| Contractor | Dispatches the **Request extra work** signal portlet. | The Work & Extra-Work process's non-interrupting event subprocess starts an **Approve extra work** task. |
| Owner | Approves the extra-work request. | The extra-work subprocess instance ends; the main flow is unaffected and still open (demonstrating the loop can repeat). |
| Contractor | Opens and completes **Submit for final review**. | `renovation-bot` transitions the project to *Final review*; the Work & Extra-Work instance ends via its terminate event and a Final Review instance starts. |
| Owner | Opens **Owner reviews final result** and approves. | The Owner branch of the final parallel review completes. |
| Inspector | Opens **Inspector reviews final result** and approves. | Both branches join; `renovation-bot` closes the project (state: *Closed*). |
| Operations observer (`admin`) | Follows all three process instances in Cockpit, in sequence, as they run. | Diagram, variables, and active nodes are visible for each phase; the auto-refreshing state advances as each `renovation-bot` transition lands. |
| Maintainer | Re-run `make bootstrap-renovation-demo` (Plone stopped), then the recording script. | The demo project is recreated fresh -- including from a previous run's terminal *Closed* state, which has no transition back to *Drafting plan* -- and the recording is repeatable. |

## Fixture adaptations

None expected: this example targets Plone groups
(`Renovation Owners`/`Contractors`/`Inspectors`) that the profile itself
creates, and its one external topic (`Plone Workflow Transition`) needs no
Camunda connector or scripting-engine feature the local Operaton fixture
lacks. The checked-in `examples/renovation-project/*.bpmn` and
`examples/renovation-bot/` stay unmodified.

Two known gaps between this doc/the demo profile's own README.rst and what
the recording actually shows, left as-is rather than guessed at blind:

- **Site address / budget**: `IRenovationProjectBehavior` (site address,
  budget) is set once by `renovation_demo.py` when the demo project is
  created and never edited on camera by any persona -- the scenario never
  demonstrates the Renovation Project type's own defining custom fields.
  Having the Contractor edit them during the plan-drafting turn would be
  more realistic, but wiring that into the recording script needs the
  actual `#form-widgets-...` widget ids confirmed against a running
  instance first.
- **"Work Log" tag**: the profile's `README.rst` and (until this pass) this
  doc both described the work-log Document as tagged "Work Log", but the
  Tags widget is `allowNewItems: false` and no such term is seeded anywhere
  in the profile, so it was never actually selectable -- the recording
  script has always skipped it (see its comment in
  `scripts/e2e_renovation_project.py`). Making the claim true would mean
  seeding the keyword in the profile and then selecting it the way
  `scripts/e2e_review_process.py`'s `lead_assigns_reviewers()` drives its
  own tag-like `.fjs-taglist-input`.

## Cockpit observation

Three process definitions run in sequence, so Cockpit's flow is: follow Plan Review from the moment the Contractor
submits the plan; once `renovation-bot` closes that instance and the Work &
Extra-Work signal fires, re-enter the processes list and follow the new
instance the same way; repeat once more for Final Review. Each re-entry uses
in-app navigation (“click Processes, then the definition again”) — a `page.reload()`
re-bootstraps Cockpit's Angular SPA and puts a blank flash in the middle of
the recording; an in-app route change re-queries the table without one.

## Artifacts

Filled in after recording (the `.webm` files are gitignored -- see
`docs/.gitignore` equivalent rule in the repo root `.gitignore` -- so they
are not committed, only regenerated by re-running the script):

| Artifact | Description |
| --- | --- |
| `renovation-project-cockpit.webm` | Full HD (1920x1080) raw Cockpit recording, spanning all three process instances |
| `renovation-project-pip.webm` | Full HD composite with Plone as the main view; Cockpit appears only as an inset during persona turns and the gaps between them |
| `renovation-project-plan-submitted.png` | Plan submitted, state: Plan under review |
| `renovation-project-work-log.png` | Work Log entry auto-completing the documentation task |
| `renovation-project-closed.png` | Final state: Closed |
| `renovation-project-cockpit-plan-review.png` | Cockpit: Plan Review instance |
| `renovation-project-cockpit-work-and-extra-work.png` | Cockpit: Work & Extra-Work instance |
| `renovation-project-cockpit-final-review.png` | Cockpit: Final Review instance |
| `renovation-project-cockpit-completed.png` | Cockpit: the final completed process instance opened in History |

## Verifying a take

The runner exits 0 even on a broken recording, so always check the artifact,
not just the exit status.

```sh
ffprobe -v error -show_entries format=duration \
  -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 \
  docs/renovation-project-pip.webm
ffmpeg -y -i docs/renovation-project-pip.webm \
  -vf 'fps=0.3,scale=480:-1,tile=6x5' -frames:v 1 /tmp/renovation-pip-sheet.png
```

The composite's duration must match the Cockpit clip's. In the contact sheet,
every persona turn must appear in the inset at its right place in the
timeline — no long runs of an identical tile (dead air), and no tile where the
inset is simply missing (a clip placed at the wrong offset, or a negative
hold that `compose_recording()` should have refused to build).

The current take uses nine 8-second `show_actor_slide()` interludes, a 6s
Cockpit hold after every turn, and a longer History ending. The
`tile=6x5` (30 cells) contact sheet covers only the first 100 seconds; use
`fps=(rows * cols) / duration` from the current `ffprobe` output if you need
to cover the complete recording.

## Cleanup

Project state resets live in `scripts/bootstrap_renovation_demo.py`, not the
recording script: re-running `make bootstrap-renovation-demo` (Plone stopped)
deletes and recreates `renovation-project-demo` via the same profile
`install()` code path used the first time, so it comes back at *Drafting
plan* with its groups, roles and portlets intact even after a previous run
closed it. The recording script itself clears all existing Operaton deployments and any Work
Log content the previous run added, then deploys the current
`examples/renovation-project/*.bpmn`/`.form` files; it does not delete
Plone users, groups, or the `renovation-bot` account. To remove
generated recordings and screenshots, delete only the `renovation-project-*`
artifacts in `docs/`. Playwright names a recording `page@<hash>.webm` until
the runner renames it — delete any stray
`docs/page@*.webm` left by a run that died mid-way, before committing.
