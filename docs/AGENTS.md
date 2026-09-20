# Recording-specific guidance

This directory contains browser scenario recordings and documentation. The primary recording runner is
`scripts/e2e_renovation_project.py`; run it from the repository root with the
browser skill wrapper:

```sh
playwright-python scripts/e2e_renovation_project.py
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
  - Close each recorded context *as soon as* its flow is done.
- Cockpit is the observer: open it first and close it last, so its recording
  spans every other clip. `compose_recording()` places the Plone clips on the
  Cockpit timeline and will refuse to build a misordered timeline.
- **Interleave Cockpit with the Plone actors; do not run them in sequence.**
  Cockpit's definition page loads its instance table once and does not poll, so
  a new instance never appears without navigation. Do it by navigating — click
  “Processes”, then the definition again — not with `page.reload()`. A reload
  re-bootstraps the Angular SPA and puts a flash in the middle of the main
  view; an in-app route change re-queries the table with no flash.
- Authenticate the unrecorded Cockpit context first, copy its
  `storage_state()`, close it, and use that state when creating the recorded
  Cockpit context. This keeps the login redirect out of the recording while
  retaining the OIDC session.

## Human-readable cursor and clicks

Playwright's native video does not add a mouse cursor or click indicators.
The e2e scripts inject `CURSOR_SCRIPT` into each recorded context
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

`compose_recording()` assembles role recordings onto the Cockpit timeline
using wall-clock offsets captured with `time.monotonic()`.

**Never use `overlay=...:shortest=1` here.** It ends the output at the *shorter*
input, which can silently truncate crucial review and completion scenes.

The runner obtains `ffmpeg-headless` through Nix, so no global FFmpeg install or
`playwright install` is required. Pass `-v error -nostats` to the encode: the
default FFmpeg banner and per-frame progress bury the runner's own output.

Verify the result rather than trusting the exit code: check that the PIP output
has exactly one `1920x1080` 25 fps stream and matches the observer duration:

```sh
ffprobe -v error -show_entries format=duration \
  -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 \
  docs/renovation-project-pip.webm
```

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
