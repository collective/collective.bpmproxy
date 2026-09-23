# Review-process browser scenario

This is the reproducible demo scenario for the `collective.bpmproxy:review_demo`
profile: Plone's stock Simple Publication Workflow (`submit`/`retract`) wired to
a parallel-review BPMN process (`examples/review-process`) that delegates to
multiple reviewers, collects their feedback, and applies the coordinator's
decision back to Plone as the workflow transition and its comment. It follows
the recording architecture documented in [AGENTS.md](AGENTS.md): isolated
Playwright contexts per actor, a Cockpit observer spanning the whole run,
human-paced cursor and clicks, and a picture-in-picture composite aligned to
real wall-clock offsets.

Unlike [the renovation-project scenario](renovation-project-scenario.md),
this one drives a single BPMN process instance throughout -- one Document,
one message-started process definition -- so Cockpit only ever has to enter one
instance, never re-enter a chained one.

This scenario has **four named personas**: an Author, and three Reviewers,
one of whom (`reviewer3`) acts as the lead/coordinator -- delegating the
review at the start and making the final call at the end, on either side of
the two parallel reviewers' own turns.

## Prerequisites

Run the following from the repository root. Start the services, wait for
Operaton, bootstrap the site (with Plone **stopped** -- bootstrapping opens
the ZODB directly), then start Plone:

```sh
make reset-site
devenv up -d
until curl -sf http://127.0.0.1:8081/engine-rest/engine >/dev/null; do sleep 5; done
make bootstrap-site
make bootstrap-review-demo
make start
until curl -sf http://127.0.0.1:8080/Plone >/dev/null; do sleep 3; done
```

The recording runner also clears every existing Operaton deployment before
deploying this scenario's assets, so each take starts with clean Plone and
clean Operaton state. It writes `docs/review-process-timing.json` alongside
the recordings. That timing manifest records every actor clip, its wall-clock
offset in the Cockpit recording measured when that actor context opens (before
login), and each observer interval's focus, so the final cut can be regenerated
without re-recording:

```sh
playwright-python scripts/cut_review_process.py
```

`devenv up -d` often prints `Daemon failed to start within 120s` even when
everything comes up -- trust the `curl` gate, not that message; see
[devenv-browser-smoke.md](devenv-browser-smoke.md) for the failures that
*are* real.

`make bootstrap-review-demo` runs `scripts/bootstrap_review_demo.py` via
`zconsole`, on top of `make bootstrap-site`'s Plone site. It:

- installs `collective.bpmproxy:review_demo` (which itself creates the
  `Reviewers` group and the `review-bot` service account, grants `Reviewers`
  the `Reviewer` role, puts a Tasks portlet on the site root, and registers
  the `submit`/`retract` content rules -- see
  `backend/src/collective/bpmproxy/review_demo.py`);
- creates the demo users the reviewer-selection form offers
  (`reviewer1`, `reviewer2`, `reviewer3`, `editor`, all in `Reviewers`) plus
  `author`, and adds each to its matching group;
- sets a known password on `review-bot` so `examples/review-bot-py/` can
  authenticate.

> **Warning** (inherited from the profile itself): the `submit`/`retract`
> content rules are assigned to the Plone site root and match Plone's stock
> Simple Publication Workflow, so they fire for *any* content's submit/retract
> site-wide, not just this scenario's demo document. Only run this against a
> throwaway or dedicated demo site.

The scenario expects these endpoints and users:

| Service | URL |
| --- | --- |
| Plone | `http://localhost:8080/Plone` |
| Operaton REST/Cockpit | `http://localhost:8081` |
| Keycloak | `http://localhost:8082` |
| Mailpit | `http://localhost:8025` |

| User | Password | Role/use |
| --- | --- | --- |
| `author` | `author` | Contributor -- drafts and submits the demo document |
| `reviewer1` | `reviewer1` | Reviewers -- one parallel review task |
| `reviewer2` | `reviewer2` | Reviewers -- the other parallel review task |
| `reviewer3` | `reviewer3` | Reviewers -- delegates reviewers, then makes the final decision |
| `review-bot` | `review-bot` | Site Administrator -- the review-bot-py worker's service account |
| `admin` | `admin` | Keycloak/Operaton Cockpit observer |

Start the Python (`operaton-tasks`) worker that applies the coordinator's
decision back to Plone (**the recording will stall waiting for the final
transition if this isn't running**):

```sh
cd examples/review-bot-py
cp secrets.example.env secrets.env   # already holds the review-bot credentials
make serve &
cd ../..
```

Run the recording with the browser skill's headless Playwright wrapper:

```sh
playwright-python scripts/e2e_review_process.py
```

## Personas and user stories

| Persona | Story | Expected result |
| --- | --- | --- |
| Author | Adds a Page ("Plone Conference 2027 unveiled!") with neutral business and advertising copy, then submits it for review. | State moves to *Pending review*; a review-process instance starts, correlated to the document's UUID via its business key. |
| Reviewer3 (lead) | Opens **Choose reviewers** (from the site root's *Review tasks* portlet) and delegates to `reviewer1` and `reviewer2`. | The multi-instance parallel-review sub-process starts two **Submit review** tasks, one per reviewer. |
| Reviewer1 | Opens their own **Submit review** task, recommends the location, and approves. | Their review is recorded into the shared `reviews` variable without naming the location or disturbing Reviewer2's own submission. |
| Reviewer2 | Opens their own **Submit review** task, critiques the location, and requests changes. | Same, from the other parallel branch; both branches join once both are in. |
| Reviewer3 (lead) | Opens **Consolidate review & decide**, sees both reviewers' feedback, and publishes. | `review-bot` applies the `publish` transition, with both reviews and the coordinator's own note as the transition comment. |
| Operations observer (`admin`) | Follows the one process instance in Cockpit from the moment Author submits to the moment it ends. | The parallel-review sub-process's two concurrent tokens are visible on the diagram while both reviewers' tasks are open. |
| Maintainer | Re-run `scripts/e2e_review_process.py` any number of times. | The script deletes and recreates the demo document itself (Author creates it on camera, so it -- not the site manager -- owns it and can submit it), and clears this example's own stale Operaton deployments first, so Cockpit's process list does not accumulate one version per run. |

Each Plone actor turn begins with a short title slide identifying the current
persona and action. The body text is pasted at clipboard speed, and the final
Cockpit segment opens the completed process's **History** view, drags the
left information-panel sash left so the panel remains visible at roughly
two thirds of its original width, and remains there for five seconds.

## Fixture adaptations

None expected: this example targets a Plone group (`Reviewers`) and content
rules the profile itself creates, and its one external topic (`Plone Workflow
Transition`) needs no Camunda connector or scripting-engine feature the local
Operaton fixture lacks -- see *Implementation notes* in
`examples/review-process/README.md` for how the BPMN itself was adapted to
that constraint (the fixture has no scripting engine, only JUEL). The
checked-in `examples/review-process/*.bpmn`/`.form` and
`examples/review-bot-py/` stay unmodified by the recording script.

## Cockpit observation

One process definition runs for the whole recording, so Cockpit's flow is
simpler than the renovation-project scenario's: enter the process definition
once before Author's turn, navigate back through **Processes** after the Author
submits, and then stay on that instance's own auto-refreshing view for the rest
of the run -- there is no process-definition-list detour and no second or third
process to re-enter. The finished cut keeps Plone as the main view during each
persona turn, then switches Operaton to the main view during observer intervals
where the process state is the action being shown. The parallel-review
sub-process is the visual payload: once Reviewer3 delegates, the diagram shows
two concurrent tokens sitting on **Submit review**, one per reviewer, until both
branches join.

## Artifacts

Filled in after recording (the `.webm` files are gitignored -- see
`docs/.gitignore` equivalent rule in the repo root `.gitignore` -- so they are
not committed, only regenerated by re-running the script):

| Artifact | Description |
| --- | --- |
| `review-process-cockpit.webm` | Full HD (1920x1080) raw Cockpit recording, spanning the whole instance |
| `review-process-pip.webm` | Full HD composite switching focus between Plone actor turns and Operaton observer intervals |
| `review-process-timing.json` | Wall-clock clip offsets, durations, source paths, and focus states used to generate the composite |
| `review-process-submitted.png` | Draft submitted, state: Pending review |
| `review-process-published.png` | Final state: Published |
| `review-process-cockpit-choose-reviewers.png` | Cockpit: the instance right after it starts, at the delegation task |
| `review-process-cockpit-parallel-review.png` | Cockpit: two concurrent tokens on the parallel-review sub-process |
| `review-process-cockpit-completed.png` | Cockpit: the completed process instance opened in History |

## Verifying a take

The runner exits 0 even on a broken recording, so always check the artifact,
not just the exit status.

```sh
ffprobe -v error -show_entries format=duration \
  -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 \
  docs/review-process-pip.webm
ffmpeg -y -i docs/review-process-pip.webm \
  -vf 'fps=0.24,scale=480:-1,tile=5x8' -frames:v 1 /tmp/review-pip-sheet.png
```

`tile=5x8` buffers 40 sampled frames before `-frames:v 1` emits the single
composite, so those 40 frames must span the *whole* clip: `fps` needs to be
at least `(rows * cols) / duration`. An actual take on 2026-09-22 measured
164.24s; `fps=0.4` (an earlier, shorter take's value) only covers the first
40 / 0.4 = 100s of that -- the back half, including the final History
segment this sheet exists to verify, silently never made it into the tiles.
`fps=0.24` covers ~167s. Recompute this whenever the clip's length changes
materially (e.g. after adding turns, slides, or end-of-recording holds).

The composite's duration is *shorter* than the raw Cockpit clip's by roughly
`VIDEO_TRIM` (0.8s) times the number of persona turns plus one -- every
segment (the initial Cockpit-alone gap, and each of the five persona clips)
has its own blank opening frame trimmed before it is spliced in, so with five
turns the composite runs about four seconds short of the raw Cockpit
recording. That is expected, not truncation; a difference much larger than
that, or a composite shorter than roughly half the Cockpit clip, is not. In
the contact sheet, every persona turn must appear in the inset at its right
place in the timeline -- no long runs of an identical tile (dead air), and no
tile where the inset is simply missing (a clip placed at the wrong offset, or
a negative hold that `compose_recording()` should have refused to build).

The timing manifest is the source of truth for later cuts. Keep the raw
`review-process-cockpit.webm` and the `page@*.webm` actor clips; change the
manifest's `gaps[].focus` values or trim boundaries as needed, then run
`playwright-python scripts/cut_review_process.py`.

## Cleanup

The recording script deletes and recreates its own demo document
(`plone-conference-2027-unveiled`, the slug of "Plone Conference 2027 unveiled!") at the start
of every run, and clears all existing Operaton deployments before deploying
its four assets. It
does not delete Plone users, groups, or the `review-bot` account. To remove generated recordings
and screenshots, delete only the `review-process-*` artifacts in `docs/`.
Playwright names a recording `page@<hash>.webm` until the runner consumes it
as one of `compose_recording()`'s inputs; these per-persona clips are kept
(not renamed) after a successful run, same as the raw Cockpit clip is renamed
but the persona ones are not -- delete any stray `docs/page@*.webm` only if a
run died mid-way, before committing.
