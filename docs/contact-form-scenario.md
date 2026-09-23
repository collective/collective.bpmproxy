# Contact-form browser scenario

> **Status: implemented and recorded.** The bootstrap target and Playwright
> runner are ready for repeatable takes. Run recordings only with the shared
> service stack and contact-form worker available, and do not use an environment
> that is being used by another scenario.

This will be the reproducible demo scenario for `examples/contact-form`: a
`Bpm Proxy` content item used *directly*, with no Plone workflow and no
content-rule wiring at all. Unlike
[the review-process scenario](review-process-scenario.md) (a real Plone
workflow driven by content-rule Signal/Message actions on a Document) and
[the renovation-project scenario](renovation-project-scenario.md) (a
five-state workflow chaining three process definitions via a custom content
type and its own subscribers), this one needs none of that machinery: adding
a `Bpm Proxy` item, pointing its `process_definition_key` at a deployed
process, and publishing it *is* the entire setup. The page itself renders
whatever form is next -- the start form to an anonymous visitor, an open
task's form to whoever is its candidate or assignee -- with no subscriber,
portlet, or content rule involved. It follows the recording architecture
documented in [AGENTS.md](AGENTS.md): isolated Playwright contexts per
actor, a Cockpit observer spanning the whole run, human-paced cursor and
clicks, and a picture-in-picture composite aligned to real wall-clock
offsets.

The other two scenarios each drive exactly one process instance (or a
chain of one-at-a-time instances) per piece of content. This scenario's own
payoff is different and worth recording on its own merits: **one persistent
Plone page, two independent process instances running against it at once.**
Every visitor who submits the contact form starts a *new*
`example-contact-form` instance, all sharing the same page's business-key
prefix (`views/bpm_form_view.py` mints `IUUID(context) + ":" + uuid4().hex`
per submission) -- so the same "Contact us" page shows Reception a list of
every inquiry still awaiting review, and later shows Specialist only the one
inquiry delegated to them, all without ever creating a second piece of
content.

This scenario has **three named personas**: an anonymous Visitor (who
submits more than once, each time a fresh, unauthenticated turn), Reception
(who triages every inquiry), and Specialist (the delegate target for one of
them).

## Prerequisites

Run the following from the repository root. Start the services, wait for
Operaton, bootstrap the site (with Plone **stopped** -- bootstrapping opens
the ZODB directly), then start Plone:

```sh
make reset-site
devenv up -d
until curl -sf http://127.0.0.1:8081/engine-rest/engine >/dev/null; do sleep 5; done
make bootstrap-site
make bootstrap-contact-form-demo
make start
until curl -sf http://127.0.0.1:8080/Plone >/dev/null; do sleep 3; done
```

The recording runner also clears every existing Operaton deployment before
deploying this scenario's assets, so each take starts with clean Plone and
clean Operaton state.

`devenv up -d` often prints `Daemon failed to start within 120s` even when
everything comes up -- trust the `curl` gate, not that message; see
[devenv-browser-smoke.md](devenv-browser-smoke.md) for the failures that
*are* real.

`make bootstrap-contact-form-demo` will run
`scripts/bootstrap_contact_form_demo.py` via `zconsole`, on top of
`make bootstrap-site`'s Plone site. Unlike `bootstrap-review-demo` and
`bootstrap-renovation-demo`, it will **not** install a `collective.bpmproxy`
demo profile -- there is no content rule, portlet, or demo content for a
profile to register. It only needs to:

- create `reception`, and add it to the built-in **`Administrators`** group
  (not a custom group -- `contact-form.bpmn`'s review task hardcodes
  `camunda:candidateGroups="Administrators"`, and creating a group of our
  own would mean editing the checked-in BPMN just for this demo);
- create `specialist` as an ordinary Member with no special group at all --
  the delegated task's `camunda:assignee="${assignedUser}"` names a specific
  Plone username directly, not a group;
- set known passwords on both, the same way the other two bootstrap scripts
  do for their demo users.

The "Contact us" `Bpm Proxy` item itself is **not** created by the bootstrap
script. Reception creates it on camera, as their first recorded turn --
mirroring how the review-process scenario has Author create its own demo
document rather than have it pre-exist. This is also the one flow already
proven to work end-to-end by `scripts/uitest/scenarios/bpm_proxy.py`
(scenario "C"): add a `Bpm Proxy` from the add menu, select the deployed
process from `#form-widgets-process_definition_key`, check
`#form-widgets-diagram_enabled-0` to enable the diagram for authenticated
users, and save. The diagram tab remains hidden from anonymous visitors.

The scenario expects these endpoints and users:

| Service | URL |
| --- | --- |
| Plone | `http://localhost:8080/Plone` |
| Operaton REST/Cockpit | `http://localhost:8081` |
| Keycloak | `http://localhost:8082` |
| Mailpit | `http://localhost:8025` |

| User | Password | Role/use |
| --- | --- | --- |
| `reception` | `reception` | Administrators -- triages every inquiry (reply, delegate, or abandon) |
| `specialist` | `specialist` | Member -- handles whichever inquiry Reception delegates to them |
| `admin` | `admin` | Keycloak/Operaton Cockpit observer |

No BPM-side service account needs Plone credentials at all -- unlike
`review-bot`/`renovation-bot`, `contact-form-bot-py`'s worker only talks to
Operaton (to lock/complete its one external task topic) and to Mailpit's SMTP
port. It never calls back into Plone, because nothing here depends on a
Plone workflow transition.

Deploy the process and its three forms, then start the Python
(`operaton-tasks`) worker that sends the reply email (**the recording will
stall waiting on the email step if this isn't running**):

```sh
cd examples/contact-form-bot-py
cp secrets.example.env secrets.env   # OAuth2 + Mailpit config, no PLONE_AUTHORIZATION needed
make deploy
make serve &
cd ../..
```

Run the recording with the browser skill's headless Playwright wrapper:

```sh
playwright-python scripts/e2e_contact_form.py
```

## Personas and user stories

| Persona | Story | Expected result |
| --- | --- | --- |
| Reception | Adds a `Bpm Proxy` ("Contact Us") from the site-root add menu, selects "Example: Contact form" as its process definition, opens the Process diagram tab before publishing, and publishes it. | The page renders `contact-form-start`'s form (via form-js) to anyone who opens it; authenticated users can also open the Process diagram tab. |
| Visitor (anonymous) | Opens **Contact us** and submits an inquiry ("Venue availability for a conference"). | A new `example-contact-form` instance starts; a **Review contact** task appears, candidate group `Administrators`. |
| Visitor (anonymous) | Opens the same **Contact us** page in an independent turn and submits a second inquiry ("Sponsorship options"). | A second, fully independent instance starts against the *same* Plone page -- both share the page's UUID as the first half of their business key but differ in the random second half, so their tasks list side by side without colliding. |
| Reception | Opens **Contact us** (now logged in) and sees both pending **Review contact** tasks listed on the very page visitors used to submit them. Opens the venue inquiry, chooses **Reply**, writes a response. | `contact-form-email`'s external task fires, delivering the reply via Mailpit to the sender's own submitted address; that instance ends at *Reply sent*. |
| Reception | Opens the sponsorship inquiry's task, chooses **Delegate**, and names `specialist`. | A **Handle delegated contact** task is created, assigned directly to `specialist` -- an assignee, not a candidate group, so nobody else sees it. |
| Specialist | Opens **Contact us** and sees only the one task delegated to them, not Reception's other two. Chooses **Reply** and writes a response. | The delegated branch's own `contact-form-email` external task fires the same way; that instance ends at *Reply sent*. |
| Operations observer (`admin`) | Follows `example-contact-form` in Cockpit from the moment the first inquiry starts. | Two concurrent instances are visible against one process definition, ending independently as Reception and Specialist each act -- unlike the other two scenarios' one-instance-(or-one-at-a-time)-per-content pattern. |
| Maintainer | Re-run `scripts/e2e_contact_form.py` any number of times. | The script deletes and recreates its own **Contact us** page (Reception creates it on camera and so owns/publishes it fresh each run) and clears all Operaton deployments first, so Cockpit starts clean on every run. |

## Fixture adaptations

None expected: both exclusive gateways use plain `bpmn:tFormalExpression`
JUEL conditions (`${action == "reply"}`, `${action == "delegate"}`), which
the local Operaton fixture's default expression language already evaluates
-- no scripting engine or Camunda Connector involved. The one external task
topic (`contact-form-email`) sends real SMTP to Mailpit directly from the
worker process; it makes no call back into Plone, so it needs no
`PLONE_AUTHORIZATION` secret, unlike `review-bot-py`/`renovation-bot`. The
checked-in `examples/contact-form/*.bpmn`/`.form` and
`examples/contact-form-bot-py/` should stay unmodified by the recording
script.

## Cockpit observation

One process definition, but -- unlike either other scenario -- *multiple
concurrent instances* rather than one at a time. The recording starts with
Plone alone. The first Visitor submission introduces Operaton as a PIP, then
the refreshed process-definition view becomes the front view and its statistics
button is enabled so executed-activity badges appear on the BPMN. The second
submission briefly returns Operaton to a PIP; after an in-place refresh, the
newest process instance is shown with auto-refresh and sequence-flow
visualization enabled. Reception and Specialist turns keep that instance view
as the Operaton inset. The final history view keeps the information panel
visible at roughly two thirds of its original width.

## Artifacts

To be filled in after a first recording (the `.webm` files are gitignored,
so they are not committed, only regenerated by re-running the script):

| Artifact | Description |
| --- | --- |
| `contact-form-cockpit.webm` | Full HD (1920x1080) raw Cockpit recording, spanning all instances |
| `contact-form-pip.webm` | Full HD composite that starts with Plone alone, introduces Operaton as a PIP during the first submission, briefly brings the refreshed definition and second instance views front, then keeps the reviewed instance as a PIP |
| `contact-form-proxy-created.png` | Reception's freshly created, published "Contact us" page |
| `contact-form-start-form.png` | The start form as an anonymous Visitor sees it |
| `contact-form-review-tasks.png` | Reception's view of Contact us with two pending review tasks listed |
| `contact-form-delegated-task.png` | Specialist's view, showing only their own delegated task |
| `contact-form-mailpit.png` | Mailpit inbox with the delivered reply emails |
| `contact-form-cockpit-concurrent-instances.png` | Cockpit: the second reviewed process instance with activity statistics badges, auto-refresh, and sequence-flow visualization enabled |
| `contact-form-cockpit-completed.png` | Cockpit: all instances ended |
| `contact-form-timing.json` | Raw Cockpit/Plone offsets, focus ranges, and composed segment boundaries for later cuts |

## Verifying a take

The runner writes `contact-form-timing.json` beside the recordings. It
contains the raw Cockpit duration, each actor clip's offset and duration, the
Cockpit focus transition, and every composed segment's source range. Use those
values for later cuts without re-recording:

```sh
ffprobe -v error -show_entries format=duration \
  -show_entries stream=width,height,r_frame_rate \
  -of default=noprint_wrappers=1 docs/contact-form-pip.webm
ffmpeg -y -i docs/contact-form-pip.webm \
  -vf 'fps=0.4,scale=480:-1,tile=6x4' -frames:v 1 \
  /tmp/contact-form-pip-sheet.png
```

The six recorded turns are one Reception setup turn, two Visitor turns, two
Reception decision turns, and one Specialist turn. Recompute the contact-sheet
rate from the timing data and the actual output duration when a later cut
changes the tile grid.

## Cleanup

The recording script deletes and recreates "Contact us" at the start of every
run, and clears all existing Operaton deployments before deploying its four
assets. It does not delete the `reception` or `specialist` accounts. Mailpit's own inbox is
not cleared between runs --
expect earlier runs' reply emails to still be listed there. To remove
generated recordings and screenshots, delete only the `contact-form-*`
artifacts in `docs/`.

## Implementation checklist

The implementation is now in place. Re-run the recording against the shared
services whenever the process or composition changes; keep the generated
timing data with the scenario artifacts for later cuts.

1. Done: `scripts/bootstrap_contact_form_demo.py` -- creates `reception`
   (Administrators) and `specialist` (Member) with known passwords. No
   `collective.bpmproxy` GenericSetup profile needed (see *Prerequisites*
   above for why).
2. Done: a `bootstrap-contact-form-demo` target in the root `Makefile`, matching
   `bootstrap-review-demo`/`bootstrap-renovation-demo`'s one-line
   `zconsole run` pattern.
3. Done: `scripts/e2e_contact_form.py` -- the Playwright recording script:
   Reception's Bpm-Proxy-creation turn can reuse
   `scripts/uitest/scenarios/bpm_proxy.py`'s proven add-menu selectors
   (`#form-widgets-process_definition_key`, `#form-buttons-save`) rather than
   re-discovering them; the anonymous
   Visitor turns need no login/storage-state handling at all, only a fresh
   context per submission. This scenario has six turns across three personas,
   and the process key is used in Visitor slide subtitles so the overlays
   describe the operation rather than repeating the contact subject. Lessons
   already learned building/fixing the other two scripts, worth having from
   the start here rather than re-discovering:
   - Port `show_actor_slide()` and `paste_text()` from
     `scripts/e2e_review_process.py` (see docs/AGENTS.md's *Human-readable
     cursor and clicks* section). The six-turn scenario still benefits from
     the slide; `message`/`replyMessage` are exactly the
     free-text fields `paste_text()` (`fill()`, not `press_sequentially()`)
     is for.
   - Reception's own turn *publishes* the Bpm Proxy through Plone's standard
     workflow-menu dropdown (`#plone-contentmenu-workflow`), the same
     Patternslib-init race `e2e_review_process.py`'s `author_submits()` and
     `e2e_renovation_project.py`'s `contractor_submits_plan()` both guard
     against with a `page.wait_for_function(...)` on the toggle's
     `pointer-events`. Build it in from the first take instead of chasing an
     intermittent failure later.
   - The recording setup clears all existing Operaton deployments before
     deploying the contact-form assets, so Cockpit starts without stale
     process definitions or instances.
4. Done: a link to this document from [AGENTS.md](AGENTS.md)'s scenario index.
5. Done: the runner records the six-turn scenario with diagram support,
   process-derived Visitor subtitles, action-following PIP focus, and timing
   data for later cuts.
