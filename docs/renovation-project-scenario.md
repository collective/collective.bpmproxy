# Renovation case-management scenario

This is the reproducible case-management example for the
`collective.bpmproxy:renovation_demo` profile. A folderish Renovation Project
is a Plone case. Creating the case starts one Operaton process with a signal;
the case UUID correlates all later messages and task queries.

The example demonstrates both directions of synchronization:

- Plone workflow transitions notify the running case process with correlated
  BPMN messages.
- The manager's workflow transition closes the case and the case process
  receives the correlated close message.
- A BPMN `++add++Document` task opens the native Plone creation form and is
  completed by the existing add-task subscriber.
- Direct Document creation during work emits a case-correlated message and
  starts a non-interrupting document-review subprocess.
- The case Message portlet starts a repeatable extra-work approval subprocess.

## Assets

The case coordinator process is:

```text
examples/renovation-project/renovation-case.bpmn
```

The called page-review process is:

```text
examples/renovation-project/renovation-page-review.bpmn
```

Forms are:

```text
renovation-owner-approval.form
renovation-inspector-approval.form
```

## Prerequisites

Run from the repository root:

```sh
devenv up -d
until curl -sf http://127.0.0.1:8081/engine-rest/engine >/dev/null; do sleep 5; done
make bootstrap-site
make start
until curl -sf http://127.0.0.1:8080/Plone >/dev/null; do sleep 3; done
```

Deploy the case process:

```sh
cd examples/renovation-project
cp secrets.example.env secrets.env
make deploy
cd ../..
```

Stop the Plone process, install the demo profile so its creation signal starts the
deployed process, and start Plone again:

```sh
make bootstrap-renovation-demo
make start
until curl -sf http://127.0.0.1:8080/Plone >/dev/null; do sleep 3; done
```

The bootstrap script creates the groups and demo users. The profile's
content-type portlet assignments provide aggregate case tasks on the case and
page-review tasks on Documents. The browser scenario deletes and recreates the
demo case during the recorded manager turn so the opening empty-site state and
the case-creation process instance are visible.

## Personas

| User | Role |
| --- | --- |
| `owner` | Renovation Owners |
| `contractor` | Renovation Contractors |
| `inspector` | Renovation Inspectors |
| `admin` | Operaton Cockpit observer |

## Scenario

1. The manager creates the Demo renovation project from Plone's Add new menu.
2. The contractor adds a Document directly inside the case.
3. The child-created message starts a child page-review process with parallel owner and inspector tasks.
4. Owner and inspector complete the document review independently.
5. The page-review subprocess completes and the main case process resumes.
6. A case manager closes the Plone case through its `close-case` workflow transition.
7. The close message reaches the main case process and ends it.

Run the browser smoke test with:

```sh
playwright-python scripts/scenarios/e2e_renovation_project.py
```

The recording follows the same conventions as the contact-form and
review-process scenarios:

- Cockpit is authenticated in an unrecorded context, then recorded first and
  kept open as the observer for the whole run. Auto-refresh and sequence-flow
  visualization are enabled before the empty Plone site is recorded.
- Each persona turn gets its own 1920x1080 recorded context, cursor/click
  overlay, human-paced interactions, and an eight-second title card.
- Cockpit enables auto-refresh and sequence-flow visualization, and waits
  after each actor turn so the state change is visible.
- The final recording is written as `renovation-project-pip.webm`; timing data
  and generated title segments are written beside it for later recuts.

The runner does not activate Cockpit's time heat-map. It captures the final
case in History with the left information-panel sash dragged left so the
panel remains visible at roughly two thirds of its original width.

## Artifacts

| Artifact | Description |
| --- | --- |
| `renovation-project-document-added.png` | Contractor's document in the case |
| `renovation-project-cockpit-parallel-review.png` | Cockpit showing the two review tasks |
| `renovation-project-closed.png` | Case after the manager closes it |
| `renovation-project-cockpit-completed.png` | Completed case in Cockpit History |
| `renovation-project-pip.webm` | Cockpit recording with actor turns as picture-in-picture |
| `renovation-project-timing.json` | Recorded offsets and title-segment metadata |

## Verifying a take

The runner's exit status does not verify the video. Check its duration and
stream properties, then sample the complete recording:

```sh
ffprobe -v error -show_entries format=duration \
  -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 \
  docs/renovation-project-pip.webm
ffmpeg -y -i docs/renovation-project-pip.webm \
  -vf 'fps=0.3,scale=480:-1,tile=6x5' -frames:v 1 \
  /tmp/renovation-pip-sheet.png
```

## Resetting

Delete the Operton deployment, stop Plone, redeploy the BPMN, and rerun
`make bootstrap-renovation-demo` to delete and recreate the demo case, groups,
roles, and portlets. Since this is a disposable example, no migration or
upgrade path is provided.
