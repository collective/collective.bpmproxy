"""Record the contact-form scenario in Plone and Operaton Cockpit.

Run from the repository root with:

    playwright-python scripts/e2e_contact_form.py

The script assumes the devenv services, a Plone site bootstrapped with
`make bootstrap-site` and `make bootstrap-contact-form-demo`, and the
contact-form-bot-py worker (`examples/contact-form-bot-py/`, `make serve`) are
all running. See
docs/contact-form-scenario.md for the full sequence.

This scenario drives two independent process instances against one Bpm Proxy
page. It follows docs/AGENTS.md's recording architecture: isolated Playwright
contexts per actor turn, a Cockpit observer spanning the whole run, human-paced
cursor and clicks, and a picture-in-picture composite aligned to real wall-clock
offsets.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
from recording import delete_demo_content
from recording import ensure_cockpit_toggle
from recording import prepare_title_segments
from recording import write_timing_manifest
import base64
import json
import subprocess
import time
import urllib.error
import urllib.request


BASE = "http://localhost:8080/Plone"
COCKPIT = "http://localhost:8081/operaton/app/cockpit/default"
ASSETS = Path("examples/contact-form")
DOCS = Path("docs")
PROCESS_KEY = "example-contact-form"
VIDEO_SIZE = {"width": 1920, "height": 1080}
TIMING_PATH = DOCS / "contact-form-timing.json"

# Every recording opens on a blank frame while the first document paints.
# Trimming it keeps that frame out of the picture-in-picture hold frames.
VIDEO_TRIM = 0.8
ACTOR_SLIDE_DURATION = 8.0
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
    """Record title metadata; the title is rendered as an independent segment."""
    page._bpmproxy_title = {
        "eyebrow": eyebrow,
        "title": title,
        "subtitle": subtitle,
    }
    page.wait_for_timeout(int(ACTOR_SLIDE_DURATION * 1000))


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


def compose_recording(cockpit_video, clips, output, cockpit_main_ranges):
    """Build the contact-form composite with explicit Cockpit focus ranges.

    `clips` is a chronological list of {"video": path, "offset": seconds},
    offset being wall-clock time since the Cockpit recording started
    (`time.monotonic() - started`, measured right when that turn's context
    was created).

    Never use `overlay=...:shortest=1` here -- see docs/AGENTS.md.
    """
    cockpit_duration = probe_duration(cockpit_video)
    durations = [probe_duration(clip["video"]) for clip in clips]
    title_segments = prepare_title_segments(nix_ffmpeg, clips, output)
    first_visitor_slide = min(ACTOR_SLIDE_DURATION, durations[1] - VIDEO_TRIM)
    first_pip_at = clips[1]["offset"] + VIDEO_TRIM + first_visitor_slide

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
    timing_segments = []
    output_time = 0.0

    def cockpit_slice(label, start, end):
        filters.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,"
            f"fps=25[{label}]"
        )

    def plone_slice(label, input_index, start, end):
        filters.append(
            f"[{input_index}:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,fps=25[{label}]"
        )

    def inset(src_label, dst_label, scale=PIP_SCALE):
        filters.append(
            f"[{src_label}]scale=iw*{scale}:-2,"
            f"pad=iw+{2 * PIP_BORDER}:ih+{2 * PIP_BORDER}:{PIP_BORDER}:{PIP_BORDER}"
            f":color={PIP_BORDER_COLOR}[{dst_label}]"
        )

    def add_composite(label, main, overlay):
        filters.append(
            f"[{main}][{overlay}]overlay=W-w-{PIP_MARGIN}:H-h-{PIP_MARGIN}[{label}]"
        )

    def add_title_pip(label, main, title_label, cockpit_label=None):
        """Center a translucent chapter card over the current main source."""
        filters.append(
            f"[{title_label}]scale=iw:-2,format=rgba,"
            "colorchannelmixer=aa=0.8,"
            f"pad=iw+{2 * PIP_BORDER}:ih+{2 * PIP_BORDER}:{PIP_BORDER}:{PIP_BORDER}"
            f":color={PIP_BORDER_COLOR}[{label}title]"
        )
        filters.append(
            f"[{main}][{cockpit_label}]"
            f"overlay=W-w-{PIP_MARGIN}:H-h-{PIP_MARGIN}[{label}withpip]"
            if cockpit_label
            else f"[{main}]copy[{label}withpip]"
        )
        filters.append(
            f"[{label}withpip][{label}title]overlay=(W-w)/2:(H-h)/2[{label}]"
        )

    def add_timing(label, start, end, main):
        nonlocal output_time
        duration = max(0.0, end - start)
        timing_segments.append(
            {
                "output_start": round(output_time, 3),
                "output_end": round(output_time + duration, 3),
                "cockpit_start": round(start, 3),
                "cockpit_end": round(end, 3),
                "main": main,
                "label": label,
            }
        )
        output_time += duration

    def mode_for(start, end):
        if end <= first_pip_at:
            return "hidden"
        # Keep Operaton as an inset until the final title card. From that
        # chapter onward it becomes the main view for the remainder.
        final_switch_at = clips[-1]["offset"] + VIDEO_TRIM + clips[-1]["title_duration"]
        if start >= final_switch_at or end > final_switch_at:
            return "cockpit"
        return "plone"

    def add_gap(index, start, end, previous_end, plone_input_index):
        if end - start <= 0.05:
            return
        freeze_at = max(previous_end - 0.04, 0.0)
        plone_slice(f"gap{index}plone", plone_input_index, freeze_at, previous_end)
        filters.append(
            f"[gap{index}plone]tpad=stop_duration={end - start:.3f}:stop_mode=clone"
            f"[gap{index}ploneheld]"
        )
        mode = mode_for(start, end)
        if mode == "hidden":
            filters.append(f"[gap{index}ploneheld]copy[gap{index}]")
            main = "plone"
        else:
            cockpit_slice(f"gap{index}cockpit", start, end)
        if mode == "plone":
            inset(
                f"gap{index}cockpit",
                f"gap{index}inset",
                PIP_SCALE * 2,
            )
            add_composite(f"gap{index}", f"gap{index}ploneheld", f"gap{index}inset")
            main = "plone"
        elif mode == "cockpit":
            inset(f"gap{index}ploneheld", f"gap{index}inset")
            add_composite(f"gap{index}", f"gap{index}cockpit", f"gap{index}inset")
            main = "cockpit"
        segment_labels.append(f"gap{index}")
        add_timing(f"gap-{index}", start, end, main)

    # The initial hold is Plone-led so the recording begins with the content
    # setup, not an empty Cockpit process view.
    add_gap(0, gaps[0][0], gaps[0][1], VIDEO_TRIM, 1)

    for index, clip in enumerate(clips):
        persona_start = VIDEO_TRIM
        persona_end = durations[index]
        filters.append(
            f"[{len(clips) + index + 1}:v]trim=start=0:end={clip['title_duration']:.3f},"
            f"setpts=PTS-STARTPTS,fps=25[slide{index}]"
        )
        slide_end = clip["title_duration"]
        title_start = clip["offset"] + VIDEO_TRIM
        title_end = title_start + slide_end
        if index == len(clips) - 1:
            cockpit_slice(f"title{index}main", title_start, title_end)
            plone_slice(
                f"title{index}ploneraw",
                index + 1,
                persona_start + slide_end,
                persona_start + slide_end + 0.04,
            )
            filters.append(
                f"[title{index}ploneraw]tpad=stop_duration={slide_end:.3f}:"
                f"stop_mode=clone[title{index}plone]"
            )
            inset(f"title{index}plone", f"title{index}inset")
            add_title_pip(
                f"title{index}",
                f"title{index}main",
                f"slide{index}",
                f"title{index}inset",
            )
            title_main = "cockpit"
        else:
            plone_slice(
                f"title{index}ploneraw",
                index + 1,
                persona_start + slide_end,
                persona_start + slide_end + 0.04,
            )
            filters.append(
                f"[title{index}ploneraw]tpad=stop_duration={slide_end:.3f}:"
                f"stop_mode=clone[title{index}main]"
            )
            cockpit_label = None
            if index:
                cockpit_slice(f"title{index}cockraw", title_start, title_end)
                inset(f"title{index}cockraw", f"title{index}cockpit")
                cockpit_label = f"title{index}cockpit"
            add_title_pip(
                f"title{index}",
                f"title{index}main",
                f"slide{index}",
                cockpit_label,
            )
            title_main = "plone"
        segment_labels.append(f"title{index}")
        add_timing(
            f"turn-{index}-slide",
            title_start,
            title_end,
            title_main,
        )

        body_start = persona_start + slide_end
        body_end = persona_end
        if body_end - body_start > 0.04:
            global_start = clip["offset"] + body_start
            global_end = clip["offset"] + body_end
            plone_slice(f"turn{index}plone", index + 1, body_start, body_end)
            mode = mode_for(global_start, global_end)
            if mode == "hidden":
                filters.append(f"[turn{index}plone]copy[turn{index}]")
                main = "plone"
            else:
                cockpit_slice(f"turn{index}cockpit", global_start, global_end)
            if mode == "plone":
                inset(f"turn{index}cockpit", f"turn{index}inset")
                add_composite(f"turn{index}", f"turn{index}plone", f"turn{index}inset")
                main = "plone"
            elif mode == "cockpit":
                inset(f"turn{index}plone", f"turn{index}inset")
                add_composite(
                    f"turn{index}", f"turn{index}cockpit", f"turn{index}inset"
                )
                main = "cockpit"
            segment_labels.append(f"turn{index}")
            add_timing(
                f"turn-{index}-body",
                global_start,
                global_end,
                main,
            )

        gap_start, gap_end = gaps[index + 1]
        add_gap(index + 1, gap_start, gap_end, persona_end, index + 1)

    concat_inputs = "".join(f"[{label}]" for label in segment_labels)
    filters.append(
        f"{concat_inputs}concat=n={len(segment_labels)}:v=1:a=0,format=yuv420p[out]"
    )
    filter_complex = ";".join(filters)
    write_timing_manifest(
        TIMING_PATH,
        {
            "cockpit_video": str(cockpit_video),
            "pip_video": str(output),
            "cockpit_duration": round(cockpit_duration, 3),
            "cockpit_main_ranges": [
                [round(start, 3), round(end, 3)] for start, end in cockpit_main_ranges
            ],
            "first_pip_at": round(first_pip_at, 3),
            "title_segments": [
                {
                    "video": str(clip["title_segment"]),
                    "title": clip["title"],
                    "duration": clip["title_duration"],
                }
                for clip in clips
            ],
            "clips": [
                {
                    **clip,
                    "video": str(clip["video"]),
                    "duration": round(durations[index], 3),
                }
                for index, clip in enumerate(clips)
            ],
            "segments": timing_segments,
        },
    )

    inputs = ["-i", cockpit_video]
    for clip in clips:
        inputs += ["-i", clip["video"]]
    for title_segment in title_segments:
        inputs += ["-i", title_segment]

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


def wait_for_task(page, proxy_url, task_name, timeout_ms=60000):
    """Wait for a task link rendered by the proxy's context-bound task table."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        page.goto(proxy_url, wait_until="load")
        task_tab = page.get_by_text("Task list", exact=True)
        if task_tab.count() and task_tab.first.is_visible():
            task_tab.first.click()
            page.wait_for_timeout(400)
        link = page.locator("a[href*='/@@bpm-task/']").filter(has_text=task_name)
        for index in range(link.count()):
            candidate = link.nth(link.count() - index - 1)
            if candidate.is_visible():
                return candidate
        page.wait_for_timeout(1500)
    raise AssertionError(f"Task {task_name!r} did not appear in time")


def wait_for_mail(subject, timeout_ms=60000):
    """Wait for the contact worker to deliver a message to Mailpit."""
    deadline = time.monotonic() + timeout_ms / 1000
    url = "http://localhost:8025/api/v1/messages"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                messages = json.load(response).get("messages", [])
        except (OSError, urllib.error.URLError):
            messages = []
        if any(message.get("Subject") == subject for message in messages):
            return
        time.sleep(1.5)
    raise AssertionError(f"Mailpit did not receive {subject!r} in time")


def cleanup_deployments(page):
    deployments = page.evaluate(
        """async base => (await (await fetch(base + '/@bpmproxy-deployments', {
          headers: {'Accept': 'application/json'}
        })).json())""",
        BASE,
    )
    for deployment in deployments:
        response = page.request.delete(
            f"{BASE}/@bpmproxy-deployments",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            data=json.dumps({"id": deployment["id"]}),
        )
        assert response.status in (200, 204), response.text()


def main():
    own_asset_names = (
        "contact-form.bpmn",
        "contact-form-start.form",
        "contact-form-review.form",
        "contact-form-delegated.form",
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        # Unrecorded manager setup: start with a clean Operaton engine and
        # recreate only this scenario's page and assets.
        setup = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("manager", "manager")}
        )
        setup_page = setup.new_page()
        setup_page.goto(BASE, wait_until="load")
        cleanup_deployments(setup_page)
        delete_demo_content(
            setup_page,
            BASE,
            ("contact-us", "plone-conference-2027-unveiled"),
        )
        assets = {path.name: path.read_text() for path in ASSETS.iterdir()}
        for name in own_asset_names:
            result = deploy(setup_page, name, assets[name])
            assert result["status"] == 200, (name, result)
        setup.close()

        # Keep a manager page outside all recordings for final page/mail checks.
        poll_context = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("manager", "manager")}
        )

        # Authenticate Cockpit once, then carry only its OIDC storage state into
        # the recorded observer context.  The login redirect never enters video.
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

        def focus_process_definition():
            cockpit_page.bring_to_front()
            cockpit_page.wait_for_timeout(1800)

        cockpit_toggles_configured = False
        statistics_toggle_configured = False

        def configure_cockpit_toggles():
            """Enable persistent Cockpit diagram toggles once per recording."""
            nonlocal cockpit_toggles_configured
            if cockpit_toggles_configured:
                return
            ensure_cockpit_toggle(
                cockpit_page, ".toggle-auto-refresh-button", "auto-refresh"
            )
            ensure_cockpit_toggle(
                cockpit_page, ".toggle-sequence-flow-button", "sequence-flow"
            )
            cockpit_toggles_configured = True

        def refresh_definition_with_statistics():
            """Refresh the visible definition view after a new submission."""
            nonlocal statistics_toggle_configured
            cockpit_page.bring_to_front()
            cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
            cockpit_page.get_by_role("link", name=PROCESS_KEY).click()
            cockpit_page.wait_for_timeout(1200)
            if statistics_toggle_configured:
                return
            statistics = cockpit_page.locator(".toggle-history-statistics-button")
            statistics.wait_for(state="visible", timeout=10000)
            label = statistics.get_attribute("aria-label") or ""
            if label.startswith("Show"):
                human_click(cockpit_page, statistics)
            statistics_toggle_configured = True

        def refresh_definition_and_open_instance():
            """Refresh the definition, then show its newest process instance."""
            refresh_definition_with_statistics()
            instances = cockpit_page.locator('a[href*="/process-instance/"]')
            instances.last.wait_for(state="visible", timeout=30000)
            human_click(cockpit_page, instances.last)
            cockpit_page.wait_for_timeout(1200)
            configure_cockpit_toggles()

        def record_turn(username, password, action, anonymous=False, label=None):
            kwargs = {
                "viewport": VIDEO_SIZE,
                "record_video_dir": str(DOCS),
                "record_video_size": VIDEO_SIZE,
            }
            if not anonymous:
                kwargs["extra_http_headers"] = {
                    "Authorization": basic_auth(username, password)
                }
                auth = browser.new_context(
                    extra_http_headers=kwargs["extra_http_headers"]
                )
                auth_page = auth.new_page()
                auth_page.goto(BASE, wait_until="load")
                if auth_page.locator("#__ac_name").count():
                    auth_page.locator("#__ac_name").fill(username)
                    auth_page.locator("#__ac_password").fill(password)
                    auth_page.locator("#buttons-login").click()
                    auth_page.wait_for_load_state("load")
                kwargs["storage_state"] = auth.storage_state()
                auth.close()
            context = browser.new_context(**kwargs)
            context.add_init_script(CURSOR_SCRIPT)
            page = context.new_page()
            offset = time.monotonic() - started
            action(page)
            video_path = page.video.path()
            context.close()
            # Leave the Operaton observer visible for one polling interval
            # after every Plone submission so the state transition is recorded.
            cockpit_page.bring_to_front()
            cockpit_page.wait_for_timeout(6000)
            clips.append(
                {
                    "video": str(Path(video_path).relative_to(Path.cwd())),
                    "offset": offset,
                    "label": label or action.__name__,
                    "title": getattr(page, "_bpmproxy_title", None),
                    "title_duration": ACTOR_SLIDE_DURATION,
                }
            )

        proxy_url = f"{BASE}/contact-us"

        # Cockpit starts observing before Reception creates the proxy.
        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name=PROCESS_KEY).click()
        cockpit_page.wait_for_timeout(800)

        def reception_creates_proxy(page):
            nonlocal proxy_url
            page.goto(BASE, wait_until="load")
            page.wait_for_timeout(1000)
            show_actor_slide(
                page,
                "Contact form · 1 / 6",
                "Reception",
                "Creating and publishing the public Contact Us page",
            )
            human_click(page, page.get_by_role("link", name="Add new…"))
            human_click(page, page.get_by_role("link", name="Bpm Proxy", exact=True))
            page.wait_for_load_state("load")
            page.wait_for_timeout(600)
            human_fill(page, page.locator("#form-widgets-IBasic-title"), "Contact us")
            definition = page.locator("#form-widgets-process_definition_key")
            definition.select_option(PROCESS_KEY)
            page.check("#form-widgets-diagram_enabled-0")
            human_click(page, page.locator("#form-buttons-save"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)
            proxy_url = page.url.split("/view")[0]
            assert proxy_url.endswith("/contact-us"), proxy_url
            page.goto(proxy_url, wait_until="load")
            diagram_tab = page.get_by_role("link", name="Process diagram", exact=True)
            diagram_tab.wait_for(state="visible", timeout=10000)
            human_click(page, diagram_tab)
            page.wait_for_timeout(900)
            page.wait_for_function(
                """() => {
                  const a = document.querySelector('#plone-contentmenu-workflow a');
                  return a && getComputedStyle(a).pointerEvents !== 'none';
                }"""
            )
            human_click(page, page.get_by_role("link", name="State: Private"))
            publish = page.locator(
                '#plone-contentmenu-workflow a[href*="workflow_action=publish"]'
            )
            human_click(page, publish.last)
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)
            assert "Published" in page.locator("body").inner_text(), page.locator(
                "body"
            ).inner_text()
            page.goto(proxy_url, wait_until="load")
            page.wait_for_timeout(1200)
            page.screenshot(
                path=str(DOCS / "contact-form-proxy-created.png"), full_page=True
            )

        record_turn("reception", "reception", reception_creates_proxy)
        focus_process_definition()

        def visitor_submits(
            page, turn, name, email, subject, message, screenshot=False
        ):
            page.goto(proxy_url, wait_until="load")
            page.locator("#collective-bpmproxy-form .fjs-container").wait_for(
                state="visible", timeout=30000
            )
            show_actor_slide(
                page,
                f"Contact form · {turn} / 6",
                "Visitor",
                (
                    "Submitting the venue availability inquiry"
                    if turn == 2
                    else "Submitting the sponsorship inquiry"
                ),
            )
            if screenshot:
                page.screenshot(
                    path=str(DOCS / "contact-form-start-form.png"), full_page=True
                )
            human_fill(page, page.get_by_label("Your Name"), name)
            human_fill(page, page.get_by_label("Your Email"), email)
            human_fill(page, page.get_by_label("Subject"), subject)
            paste_text(page, page.get_by_label("Message"), message)
            human_click(page, page.get_by_role("button", name="Send message"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1200)
            assert "/@@bpm-task/" in page.url or "Submit successful" in page.content()

        record_turn(
            "",
            "",
            lambda page: visitor_submits(
                page,
                2,
                "Conference visitor",
                "venue@example.com",
                "Venue availability for a conference",
                "Could you tell me whether the venue is available for a conference?",
                True,
            ),
            anonymous=True,
            label="visitor_submits_first",
        )
        refresh_definition_with_statistics()

        record_turn(
            "",
            "",
            lambda page: visitor_submits(
                page,
                3,
                "Sponsorship visitor",
                "sponsor@example.com",
                "Sponsorship options",
                "Please send information about sponsorship options and packages.",
            ),
            anonymous=True,
            label="visitor_submits_second",
        )
        refresh_definition_and_open_instance()
        cockpit_page.screenshot(
            path=str(DOCS / "contact-form-cockpit-concurrent-instances.png"),
            full_page=True,
        )

        def reception_replies(page):
            page.goto(proxy_url, wait_until="load")
            task = wait_for_task(page, proxy_url, "Review contact")
            # This screenshot intentionally shows both independent tasks before
            # the first one is opened.
            page.screenshot(
                path=str(DOCS / "contact-form-review-tasks.png"), full_page=True
            )
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Contact form · 4 / 6",
                "Reception",
                "Replying to the venue inquiry",
            )
            human_click(page, page.get_by_label("Reply to sender by email"))
            paste_text(
                page,
                page.get_by_label("Reply message"),
                "Thank you for your inquiry. The venue is available, and we would be happy to discuss dates and room arrangements.",
            )
            human_click(page, page.get_by_role("button", name="Submit decision"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)

        record_turn("reception", "reception", reception_replies)
        wait_for_mail("Re: Venue availability for a conference")
        # Return to the newest instance before the second Reception task.
        # Otherwise Cockpit remains on whichever instance was selected while
        # showing the concurrent submissions.
        refresh_definition_and_open_instance()

        def reception_delegates(page):
            task = wait_for_task(page, proxy_url, "Review contact")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Contact form · 5 / 6",
                "Reception",
                "Delegating the sponsorship inquiry to a specialist",
            )
            human_click(page, page.get_by_label("Delegate to specific user"))
            human_fill(
                page,
                page.get_by_label("Delegate to user (Plone username)"),
                "specialist",
            )
            human_click(page, page.get_by_role("button", name="Submit decision"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)

        record_turn("reception", "reception", reception_delegates)

        def specialist_replies(page):
            task = wait_for_task(page, proxy_url, "Handle delegated contact")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Contact form · 6 / 6",
                "Specialist",
                "Replying to the delegated sponsorship inquiry",
            )
            page.screenshot(
                path=str(DOCS / "contact-form-delegated-task.png"), full_page=True
            )
            human_click(page, page.get_by_label("Reply to sender by email"))
            paste_text(
                page,
                page.get_by_label("Reply message"),
                "Thank you for asking about sponsorship. I have attached our current sponsorship options and would be glad to answer any questions.",
            )
            human_click(page, page.get_by_role("button", name="Submit decision"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)

        record_turn("specialist", "specialist", specialist_replies)
        wait_for_mail("Re: Sponsorship options")
        human_click(
            cockpit_page,
            cockpit_page.get_by_role("link", name="Processes", exact=True).first,
        )
        cockpit_page.wait_for_timeout(1000)
        human_click(cockpit_page, cockpit_page.get_by_role("link", name=PROCESS_KEY))
        cockpit_page.wait_for_timeout(1500)

        # Both instances are now complete. Use Cockpit's History route
        # without a reload, select the latest completed instance, collapse
        # only the left info pane, and leave Audit Log open.
        cockpit_page.wait_for_timeout(2500)
        cockpit_page.get_by_role("link", name="More", exact=True).first.evaluate(
            "element => element.click()"
        )
        history_link = cockpit_page.get_by_text("History", exact=True).last
        history_link.wait_for(state="visible", timeout=10000)
        history_link.evaluate("element => element.click()")
        cockpit_page.wait_for_timeout(5000)
        # Cockpit lists history instances newest-first.  The newest instance
        # is the delegated branch; use the first visible process link rather
        # than `.last`, which can resolve to the older reply-only instance
        # when Angular keeps duplicate links in the DOM.
        history_instance = cockpit_page.locator('a[href*="/process-instance/"]').first
        history_instance.wait_for(state="visible", timeout=30000)
        human_click(cockpit_page, history_instance)
        cockpit_page.wait_for_timeout(1500)
        info_sash = cockpit_page.locator('[data-testid="sash"]').first
        info_sash.wait_for(state="visible", timeout=10000)
        sash_box = info_sash.bounding_box()
        assert sash_box is not None
        target_x = sash_box["x"] * (2 / 3)
        target_y = sash_box["y"] + sash_box["height"] / 2
        cockpit_page.mouse.move(sash_box["x"] + sash_box["width"] / 2, target_y)
        cockpit_page.mouse.down()
        cockpit_page.mouse.move(target_x, target_y, steps=18)
        cockpit_page.mouse.up()
        cockpit_page.get_by_text("Audit Log", exact=True).last.wait_for(
            state="visible", timeout=10000
        )
        cockpit_page.wait_for_timeout(5000)
        cockpit_page.screenshot(
            path=str(DOCS / "contact-form-cockpit-completed.png"), full_page=True
        )

        mail_context = browser.new_context(viewport=VIDEO_SIZE)
        mail_page = mail_context.new_page()
        mail_page.goto("http://localhost:8025", wait_until="load")
        mail_page.wait_for_timeout(1500)
        mail_page.screenshot(
            path=str(DOCS / "contact-form-mailpit.png"), full_page=True
        )
        mail_context.close()

        cockpit_video = cockpit_page.video.path()
        cockpit.close()
        poll_context.close()
        browser.close()

        Path(cockpit_video).replace(DOCS / "contact-form-cockpit.webm")
        for clip in clips:
            clip["video"] = Path(clip["video"])
        compose_recording(
            DOCS / "contact-form-cockpit.webm",
            clips,
            output=DOCS / "contact-form-pip.webm",
            cockpit_main_ranges=[
                (
                    clips[1]["offset"] + probe_duration(clips[1]["video"]),
                    clips[2]["offset"],
                ),
                (
                    clips[2]["offset"] + probe_duration(clips[2]["video"]),
                    clips[3]["offset"],
                ),
                (
                    clips[-1]["offset"] + probe_duration(clips[-1]["video"]),
                    probe_duration(DOCS / "contact-form-cockpit.webm"),
                ),
            ],
        )


if __name__ == "__main__":
    main()
