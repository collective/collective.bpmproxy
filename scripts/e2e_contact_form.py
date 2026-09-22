"""Record the contact-form scenario in Plone and Operaton Cockpit.

Run from the repository root with:

    playwright-python scripts/e2e_contact_form.py

The script assumes the devenv services, a Plone site bootstrapped with
`make bootstrap-site` and `make bootstrap-contact-form-demo`, and the
contact-form-bot-py worker (`examples/contact-form-bot-py/`, `make serve`) are
all running. See
docs/contact-form-scenario.md for the full sequence.

This scenario drives three independent process instances against one Bpm Proxy
page. It follows docs/AGENTS.md's recording architecture: isolated Playwright
contexts per actor turn, a Cockpit observer spanning the whole run, human-paced
cursor and clicks, and a picture-in-picture composite aligned to real wall-clock
offsets.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
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
        setup_page.request.delete(
            f"{BASE}/contact-us", headers={"Accept": "application/json"}
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
            cockpit_page.wait_for_timeout(6000)

        cockpit_toggles_configured = False

        def configure_cockpit_toggles():
            """Enable persistent Cockpit diagram toggles once per recording."""
            nonlocal cockpit_toggles_configured
            if cockpit_toggles_configured:
                return
            for selector in (
                ".toggle-auto-refresh-button",
                ".toggle-sequence-flow-button",
            ):
                button = cockpit_page.locator(selector)
                if not button.count() or not button.first.is_visible():
                    continue
                label = (button.first.get_attribute("aria-label") or "").lower()
                pressed = button.first.get_attribute("aria-pressed")
                if pressed == "false" or "enable" in label or "show" in label:
                    human_click(cockpit_page, button.first)
            cockpit_toggles_configured = True

        def follow_process():
            """Refresh the process instance table through Cockpit routes.

            Cockpit remembers the instance-view toggles in the browser. Set
            them only on the first instance, then leave the refreshed process
            definition view showing the newly arrived instance.
            """
            human_click(
                cockpit_page,
                cockpit_page.get_by_role("link", name="Processes", exact=True).first,
            )
            cockpit_page.wait_for_timeout(1000)
            human_click(cockpit_page, cockpit_page.get_by_role("link", name=PROCESS_KEY))
            cockpit_page.wait_for_timeout(1200)
            instances = cockpit_page.locator('a[href*="/process-instance/"]')
            if instances.count():
                human_click(cockpit_page, instances.last)
                cockpit_page.wait_for_timeout(1200)
                configure_cockpit_toggles()
                human_click(
                    cockpit_page,
                    cockpit_page.get_by_role(
                        "link", name="Processes", exact=True
                    ).first,
                )
                cockpit_page.wait_for_timeout(1000)
                human_click(
                    cockpit_page, cockpit_page.get_by_role("link", name=PROCESS_KEY)
                )
                cockpit_page.wait_for_timeout(1200)
            focus_process_definition()

        def record_turn(username, password, action, anonymous=False):
            kwargs = {
                "viewport": VIDEO_SIZE,
                "record_video_dir": str(DOCS),
                "record_video_size": VIDEO_SIZE,
            }
            if not anonymous:
                kwargs["extra_http_headers"] = {
                    "Authorization": basic_auth(username, password)
                }
            context = browser.new_context(**kwargs)
            context.add_init_script(CURSOR_SCRIPT)
            page = context.new_page()
            offset = time.monotonic() - started
            action(page)
            video_path = page.video.path()
            context.close()
            clips.append({"video": video_path, "offset": offset})

        proxy_url = f"{BASE}/contact-us"

        # Cockpit starts observing before Reception creates the proxy.
        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name=PROCESS_KEY).click()
        cockpit_page.wait_for_timeout(800)

        def reception_creates_proxy(page):
            nonlocal proxy_url
            page.goto(f"{BASE}/++add++Bpm Proxy", wait_until="load")
            page.wait_for_timeout(600)
            show_actor_slide(
                page,
                "Contact form · 1 / 8",
                "Reception",
                "Creating and publishing the public Contact us page",
            )
            human_fill(page, page.locator("#form-widgets-IBasic-title"), "Contact us")
            definition = page.locator("#form-widgets-process_definition_key"            )
            definition.select_option(PROCESS_KEY)
            human_click(page, page.locator("#form-buttons-save"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)
            proxy_url = page.url.split("/view")[0]
            assert proxy_url.endswith("/contact-us"), proxy_url
            page.goto(proxy_url, wait_until="load")
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
            page.screenshot(path=str(DOCS / "contact-form-proxy-created.png"), full_page=True)

        record_turn("reception", "reception", reception_creates_proxy)
        focus_process_definition()

        def visitor_submits(page, turn, name, email, subject, message, screenshot=False):
            page.goto(proxy_url, wait_until="load")
            page.locator("#collective-bpmproxy-form .fjs-container").wait_for(
                state="visible", timeout=30000
            )
            show_actor_slide(
                page,
                f"Contact form · {turn} / 8",
                "Visitor",
                subject,
            )
            if screenshot:
                page.screenshot(path=str(DOCS / "contact-form-start-form.png"), full_page=True)
            human_fill(page, page.get_by_label("Your Name"), name)
            human_fill(page, page.get_by_label("Your Email"), email)
            human_fill(page, page.get_by_label("Subject"), subject)
            paste_text(page, page.get_by_label("Message"), message)
            human_click(page, page.get_by_role("button", name="Send message"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1200)
            assert "/@@bpm-task/" in page.url or "Submit successful" in page.content()

        record_turn(
            "", "", lambda page: visitor_submits(
                page, 2, "Conference visitor", "venue@example.com",
                "Venue availability for a conference",
                "Could you tell me whether the venue is available for a conference?",
                True,
            ), anonymous=True,
        )
        follow_process()

        record_turn(
            "", "", lambda page: visitor_submits(
                page, 3, "Sponsorship visitor", "sponsor@example.com",
                "Sponsorship options",
                "Please send information about sponsorship options and packages.",
            ), anonymous=True,
        )
        follow_process()

        def reception_replies(page):
            page.goto(proxy_url, wait_until="load")
            task = wait_for_task(page, proxy_url, "Review contact form")
            # This screenshot intentionally shows both independent tasks before
            # the first one is opened.
            page.screenshot(path=str(DOCS / "contact-form-review-tasks.png"), full_page=True)
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Contact form · 4 / 8",
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
        follow_process()

        def reception_delegates(page):
            task = wait_for_task(page, proxy_url, "Review contact form")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Contact form · 5 / 8",
                "Reception",
                "Delegating the sponsorship inquiry to a specialist",
            )
            human_click(page, page.get_by_label("Delegate to specific user"))
            human_fill(page, page.get_by_label("Delegate to user (Plone username)"), "specialist")
            human_click(page, page.get_by_role("button", name="Submit decision"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)

        record_turn("reception", "reception", reception_delegates)
        follow_process()

        def visitor_submits_spam(page):
            visitor_submits(
                page, 6, "Anonymous visitor", "spam@example.com", "Looks like spam",
                "This message is only here to demonstrate the abandon path.",
            )

        record_turn("", "", visitor_submits_spam, anonymous=True)
        follow_process()
        cockpit_page.screenshot(
            path=str(DOCS / "contact-form-cockpit-concurrent-instances.png"), full_page=True
        )

        def reception_abandons(page):
            task = wait_for_task(page, proxy_url, "Review contact form")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Contact form · 7 / 8",
                "Reception",
                "Abandoning a spam inquiry without sending email",
            )
            human_click(page, page.get_by_label("Abandon contact form"))
            human_click(page, page.get_by_role("button", name="Submit decision"))
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)

        record_turn("reception", "reception", reception_abandons)
        follow_process()

        def specialist_replies(page):
            task = wait_for_task(page, proxy_url, "Handle delegated contact form")
            human_click(page, task)
            page.wait_for_load_state("load")
            show_actor_slide(
                page,
                "Contact form · 8 / 8",
                "Specialist",
                "Replying to the delegated sponsorship inquiry",
            )
            page.screenshot(path=str(DOCS / "contact-form-delegated-task.png"), full_page=True)
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
        human_click(cockpit_page, cockpit_page.get_by_role("link", name=PROCESS_KEY))
        focus_process_definition()

        # All three instances are now complete.  Use Cockpit's History route
        # without a reload, select the latest completed instance, enable its
        # heatmap, collapse only the left info pane, and leave Audit Log open.
        cockpit_page.wait_for_timeout(2500)
        cockpit_page.get_by_role("link", name="More", exact=True).first.evaluate(
            "element => element.click()"
        )
        history_link = cockpit_page.get_by_text("History", exact=True).last
        history_link.wait_for(state="visible", timeout=10000)
        history_link.evaluate("element => element.click()")
        cockpit_page.wait_for_timeout(5000)
        history_instance = cockpit_page.locator('a[href*="/process-instance/"]').last
        history_instance.wait_for(state="visible", timeout=30000)
        human_click(cockpit_page, history_instance)
        cockpit_page.wait_for_timeout(1500)
        maximize_diagram = cockpit_page.get_by_role(
            "button", name="Maximize diagram", exact=True
        )
        if maximize_diagram.count() and maximize_diagram.first.is_visible():
            # A prior Cockpit run may have persisted both panes collapsed in
            # localStorage. Restore them before collapsing only the left pane.
            human_click(cockpit_page, maximize_diagram.first)
        maximize_tabs = cockpit_page.get_by_role(
            "button", name="Maximize tabs panel", exact=True
        )
        if maximize_tabs.count() and maximize_tabs.first.is_visible():
            human_click(cockpit_page, maximize_tabs.first)
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
        mail_page.screenshot(path=str(DOCS / "contact-form-mailpit.png"), full_page=True)
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
        )


if __name__ == "__main__":
    main()
