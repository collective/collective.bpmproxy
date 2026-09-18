# Recording-specific guidance

This directory contains the request-for-quote browser recordings and the
scenario that generates them. The recording runner is
`scripts/e2e_request_for_quote.py`; run it from the repository root with the
browser skill wrapper:

```sh
playwright-python scripts/e2e_request_for_quote.py
```

## Recording architecture

- Use `1920x1080` for both the Playwright viewport and
  `record_video_size`. Native Playwright recordings are 25 fps WebM.
- Do setup in an unrecorded context. Cleanup, deployment, proxy creation, and
  Cockpit OIDC login otherwise become long blank or white sections in the
  videos.
- **A recorded context records from `new_page()` until `close()`, in real
  time.** Playwright duplicates frames while the page is idle to keep
  wall-clock sync, so any wall time a context is open but not being driven
  becomes dead air in its video. Two rules follow, and both matter more than
  they look:
  - Create each recorded context *immediately before* the flow it records.
    Creating the visitor context up front, before the Cockpit login and
    navigation, opened take 2 with ~7.5 s of blank white page.
  - Close each recorded context *as soon as* its flow is done. Leaving the
    visitor context open through the reviewer flow ended take 2 with ~25 s of
    frozen “Thank you!” page — more than half that clip was dead.
- Cockpit is the observer: open it first and close it last, so its recording
  spans every other clip. `compose_recording()` places the Plone clips on the
  Cockpit timeline and will refuse to build a misordered timeline.
- **Interleave Cockpit with the Plone actors; do not run them in sequence.**
  `StartEvent_1` carries `formRef="request-for-quote-start"`, so the category
  form *is* the start form and the instance does not exist until “Continue” is
  submitted. The moment it does, reload the definition view (its running count
  ticks to 1), follow the instance, and switch auto-refresh on — all *before*
  the visitor fills the first task form. The rest of the visitor and reviewer
  flow is then watched live, with the token advancing on screen, instead of
  being reconstructed from a finished instance afterwards.
  Refreshing matters: Cockpit's definition page loads its instance table once
  and does not poll, so a new instance never appears without one. Do it by
  navigating — click “Processes”, then the definition again — not with
  `page.reload()`. A reload re-bootstraps the Angular SPA and puts about a
  second of blank white in the middle of the main view; an in-app route change
  re-queries the table with no flash. `get_by_role("link", name="Processes")`
  matches both the top nav and the breadcrumb, so take `.first`.
- Authenticate the unrecorded Cockpit context first, copy its
  `storage_state()`, close it, and use that state when creating the recorded
  Cockpit context. This keeps the login redirect out of the recording while
  retaining the OIDC session.
- Keep the visitor on the “View thank you page” task at the end. Submitting it
  after the reviewer branch can produce a transient Plone “Unexpected error on
  submit” response while the process join is being resolved; it is not needed
  to demonstrate the reviewer completion. Assert the visitor's page before
  closing its context rather than reaching back into it afterwards.

## Human-readable cursor and clicks

Playwright's native video does not add a mouse cursor or click indicators.
`e2e_request_for_quote.py` injects `CURSOR_SCRIPT` into each recorded context
with `context.add_init_script()`. The script:

1. waits for `DOMContentLoaded` before touching `document.documentElement`
   (an init script can run before the document element exists);
2. adds a fixed, high-z-index red cursor ring with a white outline;
3. updates its position from a capturing `mousemove` listener;
4. adds a larger red animated ring from a capturing `click` listener; and
5. removes each click ring after its CSS animation ends.

The recording helpers deliberately move to the target with
`page.mouse.move(..., steps=18)`, pause for 450 ms, click, and pause for
850 ms. Text is entered with `press_sequentially(..., delay=75)`. Always move
the pointer again after navigation because a new document recreates the
injected cursor at its centered default position.

## Picture-in-picture composition

The final `request-for-quote-pip.webm` is made after the browser contexts
close, from the three role recordings plus the wall-clock offsets the runner
captured with `time.monotonic()` when each recorded page was created.

**Never use `overlay=...:shortest=1` here.** It ends the output at the *shorter*
input. In take 2 the Cockpit track was 47.1 s and the concatenated Plone track
61.4 s, so the composite was cut at 47.1 s and lost 14.3 s — the reviewer
opening, filling and approving the task, which is the whole point of the demo,
never appeared in the flagship video. The role clips still contained it, so the
defect was invisible unless the composite was actually watched.

Instead, build both tracks to the same length and overlay without `shortest`:

1. Trim `VIDEO_TRIM` (0.8 s) off the head of **all three** clips. Every clip's
   first frames are blank or unstyled while its document paints; on a Plone
   clip those frames are what the hold frames below would clone, and on the
   Cockpit clip they are what the composite would open on. Trimming the main
   track by the same amount is also what makes each Plone clip's lead-in
   exactly its recorded offset, with no correction term.
2. Place each Plone clip on the Cockpit timeline at its real offset, using
   `tpad` to hold the adjacent frame across the gaps:
   - visitor: `start_duration = requester_offset + VIDEO_TRIM` holds its first
     settled frame until the visitor starts; `stop_duration` holds its last
     frame until the reviewer takes over.
   - reviewer: `stop_duration` holds its last frame until Cockpit stops.
   - `start_mode`/`stop_mode` must be `clone`, not the default `add` (which
     pads with black).
3. `concat` the two padded segments. By construction the result is exactly the
   Cockpit duration, so the inset is present for the entire video and the
   reviewer's approval lines up with the Cockpit auto-refresh that shows it.
4. Scale to 40% width with `:-2` (not `:-1`) so both dimensions stay even, as
   `yuv420p` requires, then `pad` a 3 px `0x1f2937` border around it. Without a
   border the white Plone page is invisible against Cockpit's white background.
5. Overlay at `W-w-24:H-h-24` (bottom-right, 24 px margin) and end the chain
   with `format=yuv420p`.
6. Label the filtered output and map only that label. Without `-map "[out]"`,
   FFmpeg can retain the uncomposited main stream as a second video stream.

`compose_recording()` computes the hold durations and raises if either is
negative, which is the signal that the contexts were opened or closed in the
wrong order.

The runner obtains `ffmpeg-headless` through Nix, so no global FFmpeg install or
`playwright install` is required. Pass `-v error -nostats` to the encode: the
default FFmpeg banner and per-frame progress bury the runner's own output.

Verify the result rather than trusting the exit code — the truncation above
exits 0. The PIP output must have exactly one `1920x1080` 25 fps stream *and* a
duration equal to the Cockpit clip:

```sh
ffprobe -v error -show_entries format=duration \
  -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 \
  docs/request-for-quote-pip.webm
```

Then actually look at it. A contact sheet makes dead air and a missing inset
obvious in one image:

```sh
ffmpeg -y -i docs/request-for-quote-pip.webm \
  -vf 'fps=0.4,scale=480:-1,tile=5x4' -frames:v 1 /tmp/pip-sheet.png
```

## Process fixture adaptations

The checked-in request-for-quote example is not mutated. The runner transforms
the deployed copy to match the local fixture:

- `Site Administrators` becomes `Administrators`, the group created by
  `bootstrap_site.py`.
- The Python `optionsChosenString` script is removed and `${options}` is used
  directly because the Operaton fixture has no Python scripting engine.
- The accepted branch's mail connector extension is removed and its
  `sendTask` is converted to a no-op generic `task`. The fixture has no
  configured connector implementation; leaving the connector in place can
  roll back reviewer completion.

## BPMN diagram flashes

The Plone template always emits `#collective-bpmproxy-diagram` when diagrams
are enabled, even if the Process diagram tab is hidden. The old `diagram.js`
initialized `bpmn-js` immediately on page load, so the hidden container could
briefly paint during autotoc/tab setup and navigation.

`frontend-classic/src/diagram.ts` now checks `offsetParent` and uses a
`MutationObserver` on the tab container. BPMN XML is imported only after the
diagram container becomes visible. After changing this source, rebuild the
committed bundle:

```sh
npm --prefix frontend-classic run build
```

This keeps the diagram available when its tab is selected while preventing
unselected-tab flashes in the recordings.
