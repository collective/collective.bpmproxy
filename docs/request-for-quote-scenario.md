# Request-for-quote browser scenario

This is the reproducible demo scenario for the Plone proxy and the Operaton
Cockpit. It uses isolated Playwright contexts for the requester, reviewer, and
Cockpit. Setup and authentication use separate unrecorded contexts; the three
process walkthrough contexts record headless Chromium WebM video.

## Prerequisites

Run the following from the repository root. Start the services, wait for
Operaton, bootstrap the site while Plone is **stopped** (bootstrapping opens the
ZODB directly), then start Plone:

```sh
devenv up -d
until curl -sf http://127.0.0.1:8081/engine-rest/engine >/dev/null; do sleep 5; done
make bootstrap-site
make start
until curl -sf http://127.0.0.1:8080/Plone >/dev/null; do sleep 3; done
```

`devenv up -d` often prints `Daemon failed to start within 120s` even when
everything comes up — Operaton boots through Maven and overruns that window.
Trust the `curl` gates above, not that message; see
[devenv-browser-smoke.md](devenv-browser-smoke.md) for the failures that *are*
real (a stale postgres `postmaster.pid`, or orphaned services holding ports).

Running the recorder before Operaton is ready fails in a confusing way: the
proxy renders, but no process definition is deployable.

The scenario expects these endpoints:

| Service | URL |
| --- | --- |
| Plone | `http://localhost:8080/Plone` |
| Operaton REST/Cockpit | `http://localhost:8081` |
| Keycloak | `http://localhost:8082` |
| Mailpit | `http://localhost:8025` |

`make bootstrap-site` creates the seeded users used by the runner:

| User | Password | Role/use |
| --- | --- | --- |
| `manager` | `manager` | Plone reviewer and `Administrators` member |
| `admin` | `admin` | Keycloak/Operaton Cockpit observer |
| anonymous | — | Visitor/requester process role |

Run the recording with the browser skill's headless Playwright wrapper:

```sh
playwright-python scripts/e2e_request_for_quote.py
```

The script is intentionally self-contained. It removes the previous demo page
and deployments, deploys the example assets, creates and publishes a `Bpm
Proxy`, runs the anonymous requester flow, follows the process definition and
instance in Cockpit as `admin`, and completes the reviewer flow as `manager`.
The browser contexts record only the process walkthrough at Full HD (1920x1080),
with a visible cursor and click markers. Pointer movement, clicks, typing, and
the pauses around each action are deliberately human-paced.

Each recorded context is created immediately before its flow and closed
immediately after, because a Playwright context records in real time from
`new_page()` to `close()` — anything else becomes blank or frozen video. The
Cockpit context opens first and closes last, so its recording spans the whole
scenario.

The final `request-for-quote-pip.webm` uses Cockpit as the main view and places
the Plone role flows at 40% width in the bottom right, each at the wall-clock
offset where it actually happened, with the gaps between them filled by holding
the adjacent frame. The inset is therefore continuous and the composite is
exactly as long as the Cockpit recording, so the reviewer's approval is visible
alongside the Cockpit auto-refresh that reflects it. See
[AGENTS.md](AGENTS.md) for why `overlay=...:shortest=1` must not be used here.

## Personas and user stories

| Persona | Story | Expected result |
| --- | --- | --- |
| Visitor | Choose category A, select an option, and provide contact details. | The visitor reaches **View thank you page**. |
| Reviewer (`manager`) | Open the pending **Review request** task and accept it. | The request follows the accepted branch and the next visitor task is **View thank you page**. |
| Operations observer (`admin`) | Open the same process instance in Cockpit. | The instance view shows the BPMN diagram, variables, and active nodes. |
| Maintainer | Re-run the script after a clean service restart. | Existing demo data is removed first and the run is repeatable. |

## Fixture adaptations

The checked-in example remains unchanged. For this demo, the runner applies
three runtime-only substitutions before deployment:

1. `Site Administrators` becomes `Administrators`, matching the group created by
   `scripts/bootstrap_site.py`.
2. The Python script used to format `optionsChosenString` is removed because
   the Operaton fixture does not install a Python scripting engine. The mail
   text uses `${options}` directly.
3. The mail connector extension is removed from the accepted branch because
   the fixture does not configure a connector implementation; the send task
   remains as a no-op so reviewer completion is observable in Plone.

These substitutions are kept in the runner so the example remains suitable for
Camunda installations that provide the original scripting engine.

## Cockpit observation

Cockpit follows the run live rather than inspecting it afterwards. The category
form is the process start form (`StartEvent_1` carries
`formRef="request-for-quote-start"`), so the instance is created the moment the
visitor submits it. The runner then, **before the visitor fills the first task
form**:

1. re-enters the process definition view through the Processes list, so its
   running-instance count ticks to 1 — Cockpit loads that table once and does
   not poll, so without a refresh a new instance never shows up (navigating
   rather than calling `reload()` avoids a white SPA re-bootstrap on screen);
2. follows the instance into `#/process-instance/<id>/runtime`;
3. turns on auto-refresh and sequence-flow highlighting.

Everything after that — the visitor choosing options and submitting, then the
reviewer approving — is watched with the token advancing on screen. The runner
captures the instance at that point and again after reviewer completion. With
the current Operaton fixture, both controls are present:

```text
Cockpit controls: {'auto_refresh': 1, 'sequence_flow': 1}
```

The process-instance page, BPMN visualization, variables, and active nodes
remain visible while the Plone role flows are performed.

## Diagram rendering

The Plone form includes the BPMN diagram container in the page even when the
Process diagram tab is not selected. Previously, `diagram.js` initialized
`bpmn-js` as soon as the page loaded, so the hidden container could briefly
paint during tab setup and navigation. The bundle now waits until the
container is visible before importing BPMN XML, preventing those flashes while
keeping the diagram available when its tab is selected.

## Artifacts

| Artifact | Description |
| --- | --- |
| [request-for-quote-requester.webm](request-for-quote-requester.webm) | Visitor context recording |
| [request-for-quote-plone.webm](request-for-quote-plone.webm) | Reviewer/Plone recording |
| [request-for-quote-cockpit.webm](request-for-quote-cockpit.webm) | Full HD Cockpit recording |
| [request-for-quote-pip.webm](request-for-quote-pip.webm) | Operaton main view with Plone picture-in-picture |
| [request-for-quote-plone-published.png](request-for-quote-plone-published.png) | Published proxy |
| [request-for-quote-plone-thank-you.png](request-for-quote-plone-thank-you.png) | Visitor task |
| [request-for-quote-plone-reviewed.png](request-for-quote-plone-reviewed.png) | Post-review Plone state |
| [request-for-quote-cockpit-instance.png](request-for-quote-cockpit-instance.png) | Cockpit instance state |
| [request-for-quote-cockpit-completed.png](request-for-quote-cockpit-completed.png) | Cockpit after review |

Mailpit is queried at the end as an observable SMTP check. Because the local
runner removes the unconfigured mail connector, zero messages is expected. The
visitor remains on the thank-you task so the recording ends on the visitor
result; the runner also verifies that the reviewer response does not produce an
internal-server-error page.

## Verifying a take

The runner exits 0 on recordings that are badly broken, so check the output
before trusting it. It prints the timeline it built:

```text
PIP timeline: {'cockpit': 52.4, 'requester': 17.2, 'manager': 16.8,
               'requester_at': 12.6, 'manager_at': 33.1}
```

`cockpit` must be the largest, and `requester_at + requester` must not exceed
`manager_at` — otherwise the contexts overlapped and `compose_recording()`
raises rather than producing a misaligned inset.

Then confirm the composite is the full length and look at it:

```sh
ffprobe -v error -show_entries format=duration \
  -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 \
  docs/request-for-quote-pip.webm
ffmpeg -y -i docs/request-for-quote-pip.webm \
  -vf 'fps=0.4,scale=480:-1,tile=5x4' -frames:v 1 /tmp/pip-sheet.png
```

The duration must match the `cockpit` value above. In the contact sheet the
inset must be visible in every tile, must not repeat one frozen frame for long
stretches, and the reviewer flow must appear before the end.

## Cleanup

The runner deletes the demo page and all deployments it finds before starting.
It does not delete the seeded Plone users or alter the checked-in example
files. To remove generated recordings and screenshots, delete only the
`request-for-quote-*` artifacts in `docs/`.

Playwright names a recording `page@<hash>.webm` until the runner renames it. If
a run dies mid-way, those stray files are left in `docs/`; delete any
`docs/page@*.webm` before committing.
