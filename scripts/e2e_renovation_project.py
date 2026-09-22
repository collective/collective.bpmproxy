"""Record the renovation-project scenario in Plone and Operaton Cockpit.

Run from the repository root with:

    playwright-python scripts/e2e_renovation_project.py

The script assumes the devenv services, a Plone site bootstrapped with
`make bootstrap-site` and `make bootstrap-renovation-demo`, and the
renovation-bot purjo worker (`examples/renovation-bot/`, `make serve`) are
all running. See docs/renovation-project-scenario.md for the full sequence.

This scenario has three named personas who each act more than once, separated by
other actors' turns -- so each turn gets its own short recorded context, and
compose_recording() below places an arbitrary list of them onto the Cockpit
timeline.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
import base64
import json
import subprocess
import time


BASE = "http://localhost:8080/Plone"
COCKPIT = "http://localhost:8081/operaton/app/cockpit/default"
ASSETS = Path("examples/renovation-project")
DOCS = Path("docs")
PROJECT_PATH = "renovation-project-demo"
PROCESS_KEYS = (
    "renovation-plan-review",
    "renovation-work-and-extra-work",
    "renovation-final-review",
)
PLAN_BODY = (
    "Full kitchen and bathroom remodel: replace the kitchen cabinetry and "
    "countertops, retile the bathroom floor and shower surround, and "
    "upgrade the plumbing fixtures in both rooms. Work is scheduled to "
    "begin once the plan is approved by the owner and reviewed for code "
    "compliance by the inspector."
)
WORK_LOG_BODY = (
    "Week 1: demolished the old kitchen cabinetry and removed the bathroom "
    "floor tile. Rough plumbing was inspected and approved. Next week: "
    "install the new cabinetry and begin bathroom tiling."
)
VIDEO_SIZE = {"width": 1920, "height": 1080}

# Every recording opens on a blank frame while the first document paints.
# Trimming it keeps that frame out of the picture-in-picture hold frames.
VIDEO_TRIM = 0.8
PIP_SCALE = 0.4
PIP_MARGIN = 24
PIP_BORDER = 3
PIP_BORDER_COLOR = "0x1f2937"

CURSOR_SCRIPT = """
(() => {
  if (window.top !== window) return;
  const install = () => {
    const style = document.createElement('style');
    style.textContent = `
      #bpmproxy-recording-cursor {
        position: fixed; left: 50%; top: 50%; z-index: 2147483647;
        width: 24px; height: 24px;
        border: 2px solid #ff3b30; border-radius: 50%; pointer-events: none;
        transform: translate(-50%, -50%); box-shadow: 0 0 0 2px white;
      }
      .bpmproxy-recording-click {
        position: fixed; z-index: 2147483646; width: 56px; height: 56px;
        border: 4px solid #ff3b30; border-radius: 50%; pointer-events: none;
        transform: translate(-50%, -50%); animation: bpmproxy-click .8s ease-out;
      }
      @keyframes bpmproxy-click {
        from { opacity: .95; transform: translate(-50%, -50%) scale(.35); }
        to { opacity: 0; transform: translate(-50%, -50%) scale(1.25); }
      }
    `;
    document.documentElement.appendChild(style);
    const cursor = document.createElement('div');
    cursor.id = 'bpmproxy-recording-cursor';
    document.documentElement.appendChild(cursor);
    document.addEventListener('mousemove', event => {
      cursor.style.left = `${event.clientX}px`;
      cursor.style.top = `${event.clientY}px`;
    }, true);
    document.addEventListener('click', event => {
      const click = document.createElement('div');
      click.className = 'bpmproxy-recording-click';
      click.style.left = `${event.clientX}px`;
      click.style.top = `${event.clientY}px`;
      document.documentElement.appendChild(click);
      click.addEventListener('animationend', () => click.remove());
    }, true);
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }
})();
"""


def basic_auth(username, password):
    value = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {value}"


def deploy(page, name, content):
    return page.evaluate(
        """async ({base, name, xml}) => {
          const response = await fetch(base + '/@bpmproxy-deploy', {
            method: 'POST',
            headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
            body: JSON.stringify({name, xml})
          });
          return {status: response.status, body: await response.text()};
        }""",
        {"base": BASE, "name": name, "xml": content},
    )


def human_move(page, locator):
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    assert box
    page.mouse.move(
        box["x"] + box["width"] / 2,
        box["y"] + box["height"] / 2,
        steps=18,
    )
    page.wait_for_timeout(450)


def human_click(page, locator):
    human_move(page, locator)
    locator.click()
    page.wait_for_timeout(850)


def human_fill(page, locator, value):
    human_click(page, locator)
    locator.fill("")
    locator.press_sequentially(value, delay=75)
    page.wait_for_timeout(650)


def paste_text(page, locator, value):
    # Long body text via press_sequentially's per-keystroke delay would take
    # unreasonably long (see scripts/e2e_review_process.py) -- fill() pastes
    # it in one step instead.
    human_click(page, locator)
    locator.fill(value)
    page.wait_for_timeout(650)


def show_actor_slide(page, eyebrow, title, subtitle):
    """Overlay a full-frame title card naming the persona and turn, ported
    from scripts/e2e_review_process.py -- this scenario has three personas
    acting across nine turns (more than review's four across five), so
    identifying whose turn it is matters at least as much here.
    """
    page.evaluate(
        """({eyebrow, title, subtitle}) => {
          document.getElementById('bpmproxy-recording-slide')?.remove();
          const style = document.createElement('style');
          style.id = 'bpmproxy-recording-slide-style';
          style.textContent = `
            #bpmproxy-recording-slide {
              position: fixed; inset: 0; z-index: 2147483645;
              display: grid; place-items: center; pointer-events: none;
              background: rgba(15, 23, 42, .72);
              color: white; font-family: system-ui, sans-serif;
            }
            #bpmproxy-recording-slide > div {
              width: min(980px, 80vw); padding: 58px 72px;
              border-left: 10px solid #0ea5e9; background: rgba(15, 23, 42, .96);
              box-shadow: 0 18px 50px rgba(0, 0, 0, .35);
            }
            #bpmproxy-recording-slide .eyebrow {
              color: #7dd3fc; font-size: 24px; letter-spacing: .12em;
              text-transform: uppercase; margin-bottom: 22px;
            }
            #bpmproxy-recording-slide .title {
              font-size: 58px; font-weight: 700; line-height: 1.08;
            }
            #bpmproxy-recording-slide .subtitle {
              margin-top: 24px; color: #cbd5e1; font-size: 30px;
            }
          `;
          document.head.appendChild(style);
          const slide = document.createElement('div');
          slide.id = 'bpmproxy-recording-slide';
          slide.innerHTML = `<div>
            <div class="eyebrow"></div>
            <div class="title"></div>
            <div class="subtitle"></div>
          </div>`;
          slide.querySelector('.eyebrow').textContent = eyebrow;
          slide.querySelector('.title').textContent = title;
          slide.querySelector('.subtitle').textContent = subtitle;
          document.documentElement.appendChild(slide);
        }""",
        {"eyebrow": eyebrow, "title": title, "subtitle": subtitle},
    )
    page.wait_for_timeout(3600)
    page.evaluate(
        """() => {
          document.getElementById('bpmproxy-recording-slide')?.remove();
          document.getElementById('bpmproxy-recording-slide-style')?.remove();
        }"""
    )


def nix_ffmpeg(tool, *args, capture=True):
    """Run ffmpeg/ffprobe from nixpkgs, so no global install is required."""
    nix_expression = (
        'with (builtins.getFlake "nixpkgs").legacyPackages.'
        "${builtins.currentSystem}; ffmpeg-headless"
    )
    return subprocess.run(
        ["nix", "shell", "--impure", "--expr", nix_expression, "--command", tool]
        + [str(argument) for argument in args],
        check=True,
        capture_output=capture,
        text=True,
    )


def probe_duration(video):
    result = nix_ffmpeg(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video,
    )
    return float(result.stdout.strip())


def wait_for_task(page, name, timeout_ms=60000):
    """Poll the project view until a task named `name` shows in its task list.

    Tasks appear once renovation-bot (or, for the first one, the Contractor's
    own submit-plan click) has moved the workflow into the right state and
    Operaton has created the corresponding process instance -- both slightly
    asynchronous from the browser's point of view, so this is a real wait,
    not a fixed sleep.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    # :visible guards against any future duplicate match (e.g. a hidden nav
    # entry) picking a link that isn't actually on screen -- today the
    # "Project tasks" portlet is the only source of these links, so this is
    # a no-op safeguard, not a fix for an active ambiguity.
    link = page.locator("a:visible").filter(has_text=name)
    while time.monotonic() < deadline:
        page.reload(wait_until="load")
        if link.count():
            return link.first
        page.wait_for_timeout(1500)
    raise AssertionError(f"Task {name!r} did not appear in time")


def wait_for_state(page, project_url, state_text, timeout_ms=90000):
    """Poll the project's workflow state label until it reads `state_text`.

    Every transition after "Submit plan" is performed by renovation-bot
    reacting to a Camunda signal, not by anything in this script -- so
    reaching each next state is a real wait on that external worker, not a
    fixed sleep.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        page.goto(project_url, wait_until="load")
        if page.get_by_text(f"State: {state_text}", exact=False).count():
            return
        page.wait_for_timeout(1500)
    raise AssertionError(f"Workflow did not reach {state_text!r} in time")


def compose_recording(cockpit_video, clips, output=None):
    """Build a focus-flipping composite: Cockpit is the main view while
    nothing is happening in Plone, but the frame flips to Plone-as-main
    (with a small Cockpit inset) for the span of each persona turn, then
    flips back.

    `clips` is a chronological list of {"video": path, "offset": seconds},
    offset being wall-clock time since the Cockpit recording started
    (`time.monotonic() - started`, measured right when that turn's context
    was created).

    Rather than a static small-corner PIP (where Cockpit is always main and
    Plone always a small inset), every segment here is independently composited
    at full 1920x1080 and the segments are then concatenated -- there is no
    time-gated `overlay(enable=...)` and no alpha channel involved, which keeps
    alpha channel involved, which keeps the filter graph simple enough to
    reason about and to test against synthetic clips (see
    `scripts/uitest/` -- err, see the __main__ smoke test at the bottom of
    this file) before ever running it against a real recording:

      gap_0 (Cockpit alone, nothing happened yet)
      turn_0 (Plone main + small Cockpit inset)
      gap_1 (Cockpit main + small *frozen last frame of turn_0* inset)
      turn_1 (Plone main + small Cockpit inset)
      ...
      gap_N (Cockpit main + small frozen last frame of turn_{N-1})

    Never use `overlay=...:shortest=1` here -- see docs/AGENTS.md.
    """
    output = output or DOCS / "renovation-project-pip.webm"
    cockpit_duration = probe_duration(cockpit_video)
    durations = [probe_duration(clip["video"]) for clip in clips]

    # Back-to-back turns (e.g. Owner and Inspector approving in parallel,
    # with no Cockpit interstitial between them) leave zero real-time gap by
    # design. ffprobe's measured clip duration and the wall-clock offsets
    # captured via time.monotonic() then disagree by a small amount (video
    # encoder startup latency, not an actual ordering problem), which can
    # make `end` land fractionally before `start`. Clamp that away instead of
    # failing the whole recording; only a large overlap -- which would mean
    # two persona contexts genuinely ran concurrently, contradicting
    # record_turn()'s one-context-at-a-time contract -- is still a real bug.
    OVERLAP_TOLERANCE = 1.5

    gaps = []
    for index in range(len(clips) + 1):
        start = 0.0 if index == 0 else clips[index - 1]["offset"] + durations[index - 1]
        end = clips[index]["offset"] if index < len(clips) else cockpit_duration
        if end < start - OVERLAP_TOLERANCE:
            raise AssertionError(
                "Recording order broke the timeline: turn "
                f"{index - 1} ({clips[index - 1]['video']}) overlaps the "
                f"next one (gap={end - start:.2f}). Close each persona "
                "context before opening the next one."
            )
        end = max(end, start)
        gaps.append((start, end))

    print(
        "PIP timeline:",
        {
            "cockpit": round(cockpit_duration, 2),
            "clips": [
                {
                    "video": str(clip["video"]),
                    "offset": round(clip["offset"], 2),
                    "duration": round(durations[index], 2),
                }
                for index, clip in enumerate(clips)
            ],
            "gaps": [(round(a, 2), round(b, 2)) for a, b in gaps],
        },
    )

    filters = []
    segment_labels = []

    def cockpit_slice(label, start, end):
        filters.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,"
            f"fps=25[{label}]"
        )

    def small_pad(src_label, dst_label):
        filters.append(
            f"[{src_label}]scale=iw*{PIP_SCALE}:-2,"
            f"pad=iw+{2 * PIP_BORDER}:ih+{2 * PIP_BORDER}:{PIP_BORDER}:{PIP_BORDER}"
            f":color={PIP_BORDER_COLOR}[{dst_label}]"
        )

    # gap_0: Cockpit alone -- there is no prior Plone frame to show yet.
    start, end = gaps[0]
    cockpit_slice("seg0", max(start, VIDEO_TRIM), max(end, VIDEO_TRIM + 0.04))
    segment_labels.append("seg0")

    for index, clip in enumerate(clips):
        # turn_i: this persona's own clip, full frame, with a small Cockpit
        # inset sliced from the exact same real-time window.
        persona_start = VIDEO_TRIM
        persona_end = durations[index]
        filters.append(
            f"[{index + 1}:v]trim=start={persona_start:.3f}:end={persona_end:.3f},"
            f"setpts=PTS-STARTPTS,fps=25[t{index}main]"
        )
        inset_start = clip["offset"] + VIDEO_TRIM
        inset_end = clip["offset"] + persona_end
        cockpit_slice(f"t{index}cockraw", inset_start, inset_end)
        small_pad(f"t{index}cockraw", f"t{index}inset")
        filters.append(
            f"[t{index}main][t{index}inset]"
            f"overlay=W-w-{PIP_MARGIN}:H-h-{PIP_MARGIN}[seg_turn{index}]"
        )
        segment_labels.append(f"seg_turn{index}")

        # gap_{i+1}: Cockpit main again, small inset frozen on this turn's
        # last frame for the length of the gap -- a visual reminder of what
        # Plone just showed while the viewer's attention returns to Cockpit.
        gap_start, gap_end = gaps[index + 1]
        gap_len = gap_end - gap_start
        if gap_len > 0.05:
            cockpit_slice(f"g{index + 1}main", gap_start, gap_end)
            freeze_at = max(persona_end - 0.04, persona_start)
            filters.append(
                f"[{index + 1}:v]trim=start={freeze_at:.3f}:end={persona_end:.3f},"
                f"setpts=PTS-STARTPTS,tpad=stop_duration={gap_len:.3f}:stop_mode=clone,"
                f"fps=25[g{index + 1}frozen]"
            )
            small_pad(f"g{index + 1}frozen", f"g{index + 1}inset")
            filters.append(
                f"[g{index + 1}main][g{index + 1}inset]"
                f"overlay=W-w-{PIP_MARGIN}:H-h-{PIP_MARGIN}[seg{index + 1}]"
            )
        else:
            # No meaningful gap before the next turn -- skip straight to it,
            # rather than build a near-zero-length segment concat chokes on.
            filters.append(
                f"[t{index}main]fps=25,trim=start=0:end=0.04[seg{index + 1}]"
            )
        segment_labels.append(f"seg{index + 1}")

    concat_inputs = "".join(f"[{label}]" for label in segment_labels)
    filters.append(
        f"{concat_inputs}concat=n={len(segment_labels)}:v=1:a=0,format=yuv420p[out]"
    )
    filter_complex = ";".join(filters)

    inputs = ["-i", cockpit_video]
    for clip in clips:
        inputs += ["-i", clip["video"]]

    nix_ffmpeg(
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-nostats",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-c:v",
        "libvpx-vp9",
        "-deadline",
        "good",
        "-b:v",
        "0",
        "-crf",
        "32",
        "-an",
        output,
        capture=False,
    )
    return output


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        # --- Unrecorded setup, as the site manager ---------------------------
        setup = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("manager", "manager")}
        )
        setup_page = setup.new_page()
        setup_page.goto(BASE, wait_until="load")

        # `make bootstrap-renovation-demo` is what gives the project a fresh
        # "Drafting plan" state (including after a previous run closed it, which
        # has no transition back) -- this script only clears deployments and any
        # Work Log content a previous run left behind.
        #
        # Start with a clean Operaton engine so the process list and history
        # belong only to this recording.
        own_asset_names = (
            "renovation-owner-approval.form",
            "renovation-inspector-approval.form",
            "renovation-extra-work-approval.form",
            "renovation-confirm.form",
            "renovation-plan-review.bpmn",
            "renovation-work-and-extra-work.bpmn",
            "renovation-final-review.bpmn",
        )
        deployments = setup_page.evaluate(
            """async base => (await (await fetch(base + '/@bpmproxy-deployments', {
              headers: {'Accept': 'application/json'}
            })).json())""",
            BASE,
        )
        for deployment in deployments:
            setup_page.request.delete(
                f"{BASE}/@bpmproxy-deployments",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                data=json.dumps({"id": deployment["id"]}),
            )

        project_url = f"{BASE}/{PROJECT_PATH}"
        children = setup_page.evaluate(
            """async url => (await (await fetch(url + '?fullobjects=0', {
              headers: {'Accept': 'application/json'}
            })).json()).items || []""",
            project_url,
        )
        for child in children:
            setup_page.request.delete(
                child["@id"], headers={"Accept": "application/json"}
            )

        assets = {path.name: path.read_text() for path in ASSETS.iterdir()}
        for name in own_asset_names:
            result = deploy(setup_page, name, assets[name])
            assert result["status"] == 200, (name, result)

        setup.close()

        # Unrecorded, kept open for the whole script: wait_for_state()'s
        # polling needs a live page throughout, separate from the recorded
        # actor/Cockpit contexts (which open and close per turn -- reusing
        # one of those here would either interfere with its recording or
        # go stale the moment that context closes). Authenticated as manager
        # -- an unauthenticated context can't even see the workflow state
        # label once the project leaves "drafting_plan" (every later state's
        # permission map excludes Anonymous).
        poll_context = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("manager", "manager")}
        )
        poll_page = poll_context.new_page()

        # --- Cockpit: observer, opens first and closes last -------------------
        cockpit_setup = browser.new_context()
        cockpit_setup_page = cockpit_setup.new_page()
        cockpit_setup_page.goto(f"{COCKPIT}/", wait_until="load")
        if "8082/realms/plone" in cockpit_setup_page.url:
            cockpit_setup_page.get_by_label("Username or email").fill("admin")
            cockpit_setup_page.get_by_role("textbox", name="Password").fill("admin")
            cockpit_setup_page.get_by_role("button", name="Sign In").click()
            cockpit_setup_page.wait_for_load_state("load")
        cockpit_state = cockpit_setup.storage_state()
        cockpit_setup.close()

        cockpit = browser.new_context(
            viewport=VIDEO_SIZE,
            record_video_dir=str(DOCS),
            record_video_size=VIDEO_SIZE,
            storage_state=cockpit_state,
        )
        cockpit.add_init_script(CURSOR_SCRIPT)
        cockpit_page = cockpit.new_page()
        started = time.monotonic()
        clips = []

        def follow_process(process_key):
            """Re-enter Cockpit's process list and follow the latest instance.

            Navigates in-app (click "Processes", then the definition) rather
            than reload() -- a reload re-bootstraps Cockpit's Angular SPA and
            puts a blank flash in the recording; an in-app route change
            re-queries the instance table without one.
            """
            human_click(
                cockpit_page,
                cockpit_page.get_by_role("link", name="Processes", exact=True).first,
            )
            cockpit_page.wait_for_timeout(1000)
            human_click(
                cockpit_page, cockpit_page.get_by_role("link", name=process_key)
            )
            cockpit_page.wait_for_timeout(1200)
            instance_link = cockpit_page.locator('a[href*="/process-instance/"]').last
            instance_link.wait_for(state="visible", timeout=30000)
            human_click(cockpit_page, instance_link)
            cockpit_page.wait_for_timeout(1200)
            auto_refresh = cockpit_page.locator(".toggle-auto-refresh-button")
            sequence_flow = cockpit_page.locator(".toggle-sequence-flow-button")
            if auto_refresh.count():
                human_click(cockpit_page, auto_refresh)
            if sequence_flow.count():
                human_click(cockpit_page, sequence_flow)

        def focus_instance_view():
            cockpit_page.bring_to_front()
            cockpit_page.wait_for_timeout(6000)

        def record_turn(username, password, action):
            """Open a short recorded context for one persona turn and run `action`.

            `action(page)` drives the turn; the context is created immediately
            before it and closed immediately after, per docs/AGENTS.md -- so
            this is the unit every clip in `clips` corresponds to.
            """
            context = browser.new_context(
                viewport=VIDEO_SIZE,
                record_video_dir=str(DOCS),
                record_video_size=VIDEO_SIZE,
                extra_http_headers={"Authorization": basic_auth(username, password)},
            )
            context.add_init_script(CURSOR_SCRIPT)
            page = context.new_page()
            offset = time.monotonic() - started
            action(page)
            video_path = page.video.path()
            context.close()
            clips.append({"video": video_path, "offset": offset})
            return video_path

        # Cockpit follows Plan Review from the start -- there is nothing to see
        # yet, but auto-refresh means the instance appears the moment the
        # Contractor submits the plan, without this script reaching back into it.
        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name=PROCESS_KEYS[0]).click()
        cockpit_page.wait_for_timeout(800)

        # --- Contractor turn 1: draft and submit the plan ----------------------
        def contractor_submits_plan(page):
            page.goto(project_url, wait_until="load")
            page.wait_for_timeout(600)
            show_actor_slide(
                page,
                "Renovation project · 1 / 9",
                "Contractor",
                "Drafting the remodel plan",
            )
            human_click(page, page.get_by_role("link", name="Add new…"))
            human_click(page, page.get_by_role("link", name="Page", exact=True))
            human_fill(
                page,
                page.locator("#form-widgets-IDublinCore-title"),
                "Plan: kitchen and bathroom remodel",
            )
            editor = page.frame_locator("iframe").locator("body").first
            paste_text(page, editor, PLAN_BODY)
            human_click(page, page.get_by_role("button", name="Save"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)
            page.goto(project_url, wait_until="load")
            # Plone's workflow-menu dropdown toggle starts with
            # pointer-events: none until Patternslib's dropdown pattern
            # initializes on it, which wait_for_load_state alone can race --
            # the same race review_process.py's author_submits() guards
            # against on Simple Publication Workflow's own menu; this
            # project's custom renovation_project_workflow uses the same
            # generic #plone-contentmenu-workflow menu.
            page.wait_for_function(
                """() => {
                  const a = document.querySelector('#plone-contentmenu-workflow a');
                  return a && getComputedStyle(a).pointerEvents !== 'none';
                }"""
            )
            human_click(page, page.get_by_role("link", name="State: Drafting plan"))
            human_click(page, page.get_by_role("link", name="Submit plan"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(800)
            text = page.locator("body").inner_text()
            assert "Plan under review" in text
            page.screenshot(
                path=str(DOCS / "renovation-project-plan-submitted.png"), full_page=True
            )

        record_turn("contractor", "contractor", contractor_submits_plan)

        # Cockpit: the instance now exists -- re-enter to show the parallel
        # Owner/Inspector review tasks before either persona acts.
        follow_process(PROCESS_KEYS[0])
        focus_instance_view()
        cockpit_page.screenshot(
            path=str(DOCS / "renovation-project-cockpit-plan-review.png"),
            full_page=True,
        )

        # --- Owner turn 1: approve the plan -------------------------------------
        def owner_approves_plan(page):
            page.goto(project_url, wait_until="load")
            task = wait_for_task(page, "Owner reviews plan")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page, "Renovation project · 2 / 9", "Owner", "Reviewing the plan"
            )
            human_click(page, page.get_by_label("Approved"))
            human_click(page, page.get_by_role("button", name="Submit"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("owner", "owner", owner_approves_plan)
        focus_instance_view()

        # --- Inspector turn 1: approve the plan --------------------------------
        def inspector_approves_plan(page):
            page.goto(project_url, wait_until="load")
            task = wait_for_task(page, "Inspector reviews plan")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Renovation project · 3 / 9",
                "Inspector",
                "Reviewing the plan for compliance",
            )
            human_click(page, page.get_by_label("Approved"))
            human_click(page, page.get_by_role("button", name="Submit"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("inspector", "inspector", inspector_approves_plan)
        focus_instance_view()

        # Both reviews are in -- renovation-bot transitions the project once it
        # picks up the "Plone Workflow Transition" external task. Wait for it in
        # the unrecorded Cockpit context before moving on, then follow the next
        # process definition.
        wait_for_state(poll_page, project_url, "Work in progress")
        follow_process(PROCESS_KEYS[1])
        focus_instance_view()
        cockpit_page.screenshot(
            path=str(DOCS / "renovation-project-cockpit-work-and-extra-work.png"),
            full_page=True,
        )

        # --- Contractor turn 2: document completed work (auto-completes) -------
        def contractor_documents_work(page):
            page.goto(project_url, wait_until="load")
            page.wait_for_timeout(600)
            show_actor_slide(
                page,
                "Renovation project · 4 / 9",
                "Contractor",
                "Logging a week of completed work",
            )
            human_click(page, page.get_by_role("link", name="Add new…"))
            human_click(page, page.get_by_role("link", name="Page", exact=True))
            human_fill(
                page,
                page.locator("#form-widgets-IDublinCore-title"),
                "Week 1 progress",
            )
            editor = page.frame_locator("iframe").locator("body").first
            paste_text(page, editor, WORK_LOG_BODY)
            # Not tagging this "Work Log" -- the pat-select2 Tags widget is
            # configured with allowNewItems: false (only existing vocabulary
            # terms are selectable) and the profile seeds no such term, so
            # there is nothing to pick, even though the profile's own
            # README.rst still describes this content as tagged that way
            # (docs/renovation-project-scenario.md's persona table used to
            # make the same claim; it now describes this actual behavior
            # instead -- see that doc's *Fixture adaptations* section). See
            # completeAddTask() in subscribers/tasks.py: it matches on
            # portal_type/parent UUID, never on Subject, so this only affects
            # discoverability (e.g. a future "Work Log" Collection), never
            # the task auto-complete itself.
            human_click(page, page.get_by_role("button", name="Save"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(900)
            page.screenshot(
                path=str(DOCS / "renovation-project-work-log.png"), full_page=True
            )

        record_turn("contractor", "contractor", contractor_documents_work)
        focus_instance_view()

        # --- Contractor turn 3: request extra work ------------------------------
        def contractor_requests_extra_work(page):
            page.goto(project_url, wait_until="load")
            page.wait_for_timeout(600)
            show_actor_slide(
                page,
                "Renovation project · 5 / 9",
                "Contractor",
                "Requesting extra work approval",
            )
            button = page.get_by_role("button", name="Request extra work")
            human_click(page, button)
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("contractor", "contractor", contractor_requests_extra_work)
        focus_instance_view()

        # --- Owner turn 2: approve the extra-work request ------------------------
        def owner_approves_extra_work(page):
            page.goto(project_url, wait_until="load")
            task = wait_for_task(page, "Approve extra work")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Renovation project · 6 / 9",
                "Owner",
                "Approving the extra-work request",
            )
            human_click(page, page.get_by_label("Approved"))
            human_click(page, page.get_by_role("button", name="Submit"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("owner", "owner", owner_approves_extra_work)
        focus_instance_view()

        # --- Contractor turn 4: submit for final review -------------------------
        def contractor_submits_for_final_review(page):
            page.goto(project_url, wait_until="load")
            task = wait_for_task(page, "Submit for final review")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Renovation project · 7 / 9",
                "Contractor",
                "Submitting the completed work for final review",
            )
            human_click(page, page.get_by_role("button", name="Submit"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("contractor", "contractor", contractor_submits_for_final_review)
        focus_instance_view()

        wait_for_state(poll_page, project_url, "Final review")
        follow_process(PROCESS_KEYS[2])
        focus_instance_view()
        cockpit_page.screenshot(
            path=str(DOCS / "renovation-project-cockpit-final-review.png"),
            full_page=True,
        )

        # --- Owner turn 3: approve the final result -----------------------------
        def owner_approves_final(page):
            page.goto(project_url, wait_until="load")
            task = wait_for_task(page, "Owner reviews final result")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Renovation project · 8 / 9",
                "Owner",
                "Reviewing the final result",
            )
            human_click(page, page.get_by_label("Approved"))
            human_click(page, page.get_by_role("button", name="Submit"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("owner", "owner", owner_approves_final)
        focus_instance_view()

        # --- Inspector turn 2: approve the final result -------------------------
        def inspector_approves_final(page):
            page.goto(project_url, wait_until="load")
            task = wait_for_task(page, "Inspector reviews final result")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Renovation project · 9 / 9",
                "Inspector",
                "Reviewing the final result for compliance",
            )
            human_click(page, page.get_by_label("Approved"))
            human_click(page, page.get_by_role("button", name="Submit"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("inspector", "inspector", inspector_approves_final)
        focus_instance_view()

        wait_for_state(poll_page, project_url, "Closed")
        cockpit_page.wait_for_timeout(2500)
        cockpit_page.get_by_role("link", name="More", exact=True).first.evaluate(
            "(element) => element.click()"
        )
        history_link = cockpit_page.get_by_text("History", exact=True).last
        history_link.wait_for(state="visible", timeout=10000)
        history_link.evaluate("(element) => element.click()")
        cockpit_page.wait_for_timeout(5000)
        history_instance = cockpit_page.locator('a[href*="/process-instance/"]').last
        history_instance.wait_for(state="visible", timeout=30000)
        human_click(cockpit_page, history_instance)
        cockpit_page.wait_for_timeout(1500)
        info_panel = cockpit_page.get_by_role(
            "button", name="Minimize info panel", exact=True
        )
        if info_panel.count() and info_panel.first.is_visible():
            human_click(cockpit_page, info_panel.first)
        heatmap = cockpit_page.locator("button.toggle-heatmap-button")
        heatmap.wait_for(state="visible", timeout=10000)
        if heatmap.get_attribute("aria-label", timeout=10000).startswith(
            "Show time heatmap"
        ):
            human_click(cockpit_page, heatmap)
        cockpit_page.wait_for_timeout(5000)
        cockpit_page.screenshot(
            path=str(DOCS / "renovation-project-cockpit-completed.png"), full_page=True
        )
        poll_page.goto(project_url, wait_until="load")
        poll_page.screenshot(
            path=str(DOCS / "renovation-project-closed.png"), full_page=True
        )
        poll_context.close()

        print("Scenario completed:", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

        cockpit_video = cockpit_page.video.path()
        cockpit.close()
        browser.close()

        Path(cockpit_video).replace(DOCS / "renovation-project-cockpit.webm")
        for clip in clips:
            clip["video"] = Path(clip["video"])
        compose_recording(DOCS / "renovation-project-cockpit.webm", clips)


if __name__ == "__main__":
    main()
