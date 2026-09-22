"""Record the review-process scenario in Plone and Operaton Cockpit.

Run from the repository root with:

    playwright-python scripts/e2e_review_process.py

The script assumes the devenv services, a Plone site bootstrapped with
`make bootstrap-site` and `make bootstrap-review-demo`, and the review-bot-py
worker (`examples/review-bot-py/`, `make serve`) are all running. See
docs/review-process-scenario.md for the full sequence.

Unlike the renovation-project scenario, this one drives a single BPMN
process instance throughout -- one Document, one signal, one process
definition -- so there is no chained process to re-enter Cockpit for: the
observer follows one instance from the moment it starts to the moment it
ends. It still follows docs/AGENTS.md's recording architecture: isolated
Playwright contexts per actor turn, a Cockpit observer spanning the whole
run, human-paced cursor and clicks, and a picture-in-picture composite
aligned to real wall-clock offsets.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
import base64
import json
import subprocess
import time


BASE = "http://localhost:8080/Plone"
COCKPIT = "http://localhost:8081/operaton/app/cockpit/default"
ASSETS = Path("examples/review-process")
DOCS = Path("docs")
DOC_TITLE = "Plone Conference 2027 unveiled!"
DOC_PATH = "plone-conference-2027-unveiled"  # the slug Plone derives from DOC_TITLE
DOC_BODY = (
    "The upcoming conference brings together practical ideas, ambitious teams, "
    "and a fresh programme of useful conversations.\n\n"
    "Attendees can expect thoughtful sessions, productive connections, and "
    "plenty of opportunities to exchange lessons learned from recent projects.\n\n"
    "The programme will highlight:\n"
    "• responsible growth and customer understanding\n"
    "• small operational improvements that help good work scale\n"
    "• practical demonstrations and measurable outcomes\n\n"
    "Our organisers are shaping a welcoming experience with clear communication, "
    "carefully timed activities, and a steady focus on value for every participant. "
    "More announcements will follow as the schedule develops, including useful "
    "guidance for planning, participation, and follow-up after the event. "
    "The team is looking forward to a focused, energetic few days of learning "
    "and collaboration."
)
PROCESS_KEY = "example-plone-review-process"
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


def human_fill(page, locator, value, delay=75):
    human_click(page, locator)
    locator.fill("")
    locator.press_sequentially(value, delay=delay)
    page.wait_for_timeout(650)


def paste_text(page, locator, value):
    human_click(page, locator)
    locator.fill(value)
    page.wait_for_timeout(650)


def show_actor_slide(page, eyebrow, title, subtitle):
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
    """Poll the site root until a task named `name` shows in the Review
    tasks portlet. Unlike renovation-project's per-content Task list
    portlet, this profile's Tasks portlet lives on the site root (see
    review_demo.py's post-install handler), so this reloads BASE, not a
    content page -- both the delegation task and every parallel review task
    surface there regardless of which reviewer opens it.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    link = page.locator("a:visible").filter(has_text=name)
    while time.monotonic() < deadline:
        page.goto(BASE, wait_until="load")
        if link.count():
            return link.first
        page.wait_for_timeout(1500)
    raise AssertionError(f"Task {name!r} did not appear in time")


def wait_for_state(page, doc_url, state_text, timeout_ms=60000):
    """Poll the document's workflow state label until it reads `state_text`.

    The final transition is performed by review-bot-py reacting to the
    "Plone Workflow Transition" external task, not by anything in this
    script -- so reaching it is a real wait on that external worker, not a
    fixed sleep.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        page.goto(doc_url, wait_until="load")
        if page.get_by_text(f"State: {state_text}", exact=False).count():
            return
        page.wait_for_timeout(1500)
    raise AssertionError(f"Workflow did not reach {state_text!r} in time")


def compose_recording(cockpit_video, clips, output):
    """Build a focus-flipping composite: Cockpit is the main view while
    nothing is happening in Plone, but the frame flips to Plone-as-main
    (with a small Cockpit inset) for the span of each persona turn, then
    flips back.

    `clips` is a chronological list of {"video": path, "offset": seconds},
    offset being wall-clock time since the Cockpit recording started
    (`time.monotonic() - started`, measured right when that turn's context
    was created).

    Never use `overlay=...:shortest=1` here -- see docs/AGENTS.md.
    """
    cockpit_duration = probe_duration(cockpit_video)
    durations = [probe_duration(clip["video"]) for clip in clips]

    # Back-to-back turns leave zero real-time gap by design. ffprobe's
    # measured clip duration and the wall-clock offsets captured via
    # time.monotonic() then disagree by a small amount (video encoder
    # startup latency, not an actual ordering problem), which can make `end`
    # land fractionally before `start`. Clamp that away instead of failing
    # the whole recording; only a large overlap -- which would mean two
    # persona contexts genuinely ran concurrently, contradicting
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
        # last frame for the length of the gap.
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

        # Start with a clean Operaton engine so Cockpit's process list and
        # instance history cannot contain state from another scenario or run.
        own_asset_names = (
            "review-process.bpmn",
            "review-select-reviewers.form",
            "review-submit.form",
            "review-decision.form",
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

        assets = {
            path.name: path.read_text()
            for path in ASSETS.iterdir()
            if path.suffix in (".bpmn", ".form")
        }
        for name in own_asset_names:
            result = deploy(setup_page, name, assets[name])
            assert result["status"] == 200, (name, result)

        # Remove a previous run's demo document (any state) so the profile's
        # site-wide submit content rule starts a fresh process instance, not
        # one correlated to a stale UUID. The Author persona creates it fresh
        # on camera below (not here as manager) -- Simple Publication
        # Workflow's "submit" transition is only offered to the content's
        # Owner, and an object created by manager makes manager the owner,
        # not Author.
        doc_url = f"{BASE}/{DOC_PATH}"
        setup_page.request.delete(doc_url, headers={"Accept": "application/json"})
        setup.close()

        # Unrecorded, kept open for the whole script: wait_for_state()'s
        # polling needs a live page throughout, separate from the recorded
        # actor/Cockpit contexts (which open and close per turn).
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

        def follow_instance():
            """Enter the (only) running instance via in-app navigation.

            Navigates "Processes" then the definition again, rather than
            reload() -- see docs/AGENTS.md.
            """
            human_click(
                cockpit_page,
                cockpit_page.get_by_role("link", name="Processes", exact=True).first,
            )
            cockpit_page.wait_for_timeout(1000)
            human_click(
                cockpit_page, cockpit_page.get_by_role("link", name=PROCESS_KEY)
            )
            cockpit_page.wait_for_timeout(1200)
            instance_link = cockpit_page.locator('a[href*="/process-instance/"]').last
            instance_link.wait_for(state="visible", timeout=30000)
            human_click(cockpit_page, instance_link)
            cockpit_page.wait_for_timeout(1200)
            for selector in (
                ".toggle-auto-refresh-button",
                ".toggle-sequence-flow-button",
            ):
                button = cockpit_page.locator(selector)
                if button.count():
                    human_click(cockpit_page, button)

        def focus_instance_view():
            cockpit_page.bring_to_front()
            cockpit_page.wait_for_timeout(6000)

        def record_turn(username, password, action):
            """Open a short recorded context for one persona turn and run
            `action`. The context is created immediately before it and
            closed immediately after, per docs/AGENTS.md."""
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

        # Cockpit watches the (still empty) process list from the start --
        # there is nothing to see yet, but the instance appears the moment
        # the Author submits, without this script reaching back into it.
        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name=PROCESS_KEY).click()
        cockpit_page.wait_for_timeout(800)

        # --- Author: draft and submit for review --------------------------------
        def author_submits(page):
            page.goto(BASE, wait_until="load")
            page.wait_for_timeout(600)
            show_actor_slide(
                page,
                "Review process · 1 / 5",
                "Author",
                "Drafting and submitting the conference announcement",
            )
            human_click(page, page.get_by_role("link", name="Add new…"))
            human_click(page, page.get_by_role("link", name="Page", exact=True))
            human_fill(
                page,
                page.locator("#form-widgets-IDublinCore-title"),
                DOC_TITLE,
            )
            editor = page.frame_locator("iframe").locator("body").first
            paste_text(page, editor, DOC_BODY)
            human_click(page, page.get_by_role("button", name="Save"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)
            assert doc_url in page.url

            # Simple Publication Workflow's transitions dropdown only
            # renders once the object has a workflow history -- an object
            # this Author just created and owns already does -- and its
            # toggle starts with pointer-events: none until Patternslib's
            # dropdown pattern initializes on it, which wait_for_load_state
            # alone can race.
            page.wait_for_function(
                """() => {
                  const a = document.querySelector('#plone-contentmenu-workflow a');
                  return a && getComputedStyle(a).pointerEvents !== 'none';
                }"""
            )
            human_click(page, page.get_by_role("link", name="State: Private"))
            human_click(page, page.get_by_role("link", name="Submit for publication"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(800)
            text = page.locator("body").inner_text()
            assert "Pending review" in text
            page.screenshot(
                path=str(DOCS / "review-process-submitted.png"), full_page=True
            )

        record_turn("author", "author", author_submits)

        # Cockpit: the instance now exists -- enter it to show the Choose
        # reviewers task before the lead reviewer acts.
        follow_instance()
        focus_instance_view()
        cockpit_page.screenshot(
            path=str(DOCS / "review-process-cockpit-choose-reviewers.png"),
            full_page=True,
        )

        # --- Lead reviewer turn 1: delegate to two parallel reviewers -----------
        def lead_assigns_reviewers(page):
            task = wait_for_task(page, "Choose reviewers")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Review process · 2 / 5",
                "Lead reviewer",
                "Choosing reviewers for a parallel assessment",
            )
            taglist = page.locator(".fjs-taglist-input")
            for reviewer in ("reviewer1", "reviewer2"):
                human_move(page, taglist)
                taglist.fill(reviewer)
                page.wait_for_timeout(300)
                page.keyboard.press("Enter")
                page.wait_for_timeout(400)
            human_fill(
                page,
                page.get_by_label("Instructions for reviewers"),
                "Please recommend or critique the location, without naming it.",
            )
            human_click(page, page.get_by_role("button", name="Assign Reviewers"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("reviewer3", "reviewer3", lead_assigns_reviewers)

        # Cockpit: the multi-instance sub-process now has two parallel active
        # tasks -- the visual point of this whole example.
        focus_instance_view()
        cockpit_page.wait_for_timeout(1500)
        cockpit_page.screenshot(
            path=str(DOCS / "review-process-cockpit-parallel-review.png"),
            full_page=True,
        )

        # --- Reviewer 1 turn: approve ---------------------------------------------
        def reviewer1_submits(page):
            task = wait_for_task(page, "Submit review")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Review process · 3 / 5",
                "Reviewer 1",
                "Recommending the location",
            )
            human_click(page, page.get_by_label("Approve"))
            human_fill(
                page,
                page.get_by_label("Review Comments"),
                "I recommend the location; it supports a welcoming conference experience.",
            )
            human_click(page, page.get_by_role("button", name="Submit Review"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("reviewer1", "reviewer1", reviewer1_submits)
        focus_instance_view()

        # --- Reviewer 2 turn: request changes --------------------------------------
        def reviewer2_submits(page):
            task = wait_for_task(page, "Submit review")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Review process · 4 / 5",
                "Reviewer 2",
                "Critiquing the location",
            )
            human_click(page, page.get_by_label("Request Changes"))
            human_fill(
                page,
                page.get_by_label("Review Comments"),
                "I critique the location because access and flow may need improvement.",
            )
            human_click(page, page.get_by_role("button", name="Submit Review"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("reviewer2", "reviewer2", reviewer2_submits)
        focus_instance_view()

        # --- Lead reviewer turn 2: consolidate and decide --------------------------
        def lead_decides(page):
            task = wait_for_task(page, "Consolidate review")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Review process · 5 / 5",
                "Lead reviewer",
                "Consolidating feedback and making the final decision",
            )
            human_click(page, page.get_by_label("publish"))
            human_fill(
                page,
                page.get_by_label("Coordinator Comments"),
                "Thanks both -- the location feedback supports publishing as is.",
            )
            human_click(page, page.get_by_role("button", name="Complete Review"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(700)

        record_turn("reviewer3", "reviewer3", lead_decides)
        focus_instance_view()

        wait_for_state(poll_page, doc_url, "Published")
        cockpit_page.wait_for_timeout(2500)
        # Open the navigation menu without adding an unnecessary mouse gesture
        # to the recording; History is the intended next Cockpit view.
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
            path=str(DOCS / "review-process-cockpit-completed.png"), full_page=True
        )
        poll_page.goto(doc_url, wait_until="load")
        poll_page.screenshot(
            path=str(DOCS / "review-process-published.png"), full_page=True
        )
        poll_context.close()

        print("Scenario completed:", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

        cockpit_video = cockpit_page.video.path()
        cockpit.close()
        browser.close()

        Path(cockpit_video).replace(DOCS / "review-process-cockpit.webm")
        for clip in clips:
            clip["video"] = Path(clip["video"])
        compose_recording(
            DOCS / "review-process-cockpit.webm",
            clips,
            output=DOCS / "review-process-pip.webm",
        )


if __name__ == "__main__":
    main()
