"""Record the request-for-quote scenario in Plone and Operaton Cockpit.

Run from the repository root with:

    playwright-python scripts/e2e_request_for_quote.py

The script assumes the devenv services and a Plone site are running.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
import base64
import json
import re
import subprocess
import time


BASE = "http://localhost:8080/Plone"
COCKPIT = "http://localhost:8081/operaton/app/cockpit/default"
ASSETS = Path("examples/request-for-quote")
DOCS = Path("docs")
PROCESS_KEY = "example-request-for-quote"
PAGE_TITLE = "Request for quote demo"
PAGE_PATH = "request-for-quote-demo"
VIDEO_SIZE = {"width": 1920, "height": 1080}

# Each recording opens on a blank frame while the first document paints.
# Trimming it keeps that frame out of the picture-in-picture hold frames.
VIDEO_TRIM = 0.8
PIP_SCALE = 0.4
PIP_MARGIN = 24
PIP_BORDER = 3
PIP_BORDER_COLOR = "0x1f2937"

# While Plone is being driven the inset grows to FOCUS_SCALE of the frame and
# centres; when it goes quiet it shrinks back to the corner so Cockpit has the
# stage. FOCUS_FADE is the transition each way.
FOCUS_SCALE = 0.8
FOCUS_FADE = 0.6
# Actions this close together are one window -- a form fill is a burst of many
# small ones, and pulsing between the two states through it would be unwatchable.
FOCUS_MERGE_GAP = 1.5
FOCUS_LINGER = 0.5  # stay on Plone briefly after the last action
FOCUS_MIN = 1.8  # never grow and shrink faster than this

CURSOR_SCRIPT = """
(() => {
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


def create_and_publish_proxy(page):
    page.goto(f"{BASE}/++add++Bpm%20Proxy", wait_until="load")
    page.fill("#form-widgets-IBasic-title", PAGE_TITLE)
    page.select_option("#form-widgets-process_definition_key", PROCESS_KEY)
    page.check("#form-widgets-diagram_enabled-0")
    page.click("#form-buttons-save")
    page.wait_for_load_state("load")
    page.get_by_role("link", name="State: Private").click()
    page.get_by_role("link", name="Publish").click()
    page.wait_for_load_state("load")
    page.wait_for_timeout(800)
    return f"{BASE}/{PAGE_PATH}/view"


def login_cockpit(page):
    page.goto(f"{COCKPIT}/", wait_until="load")
    if "8082/realms/plone" in page.url:
        page.get_by_label("Username or email").fill("admin")
        page.get_by_role("textbox", name="Password").fill("admin")
        page.get_by_role("button", name="Sign In").click()
        page.wait_for_load_state("load")
    page.wait_for_timeout(2200)


# When each page was actively driven. compose_recording() turns the entries
# for the Plone pages into the windows where the inset takes over the frame,
# so the viewer is looking at whichever side is actually doing something.
ACTIVITY = []


def _mark(page, since):
    ACTIVITY.append({"page": page, "start": since, "end": time.monotonic()})


def human_click(page, locator):
    since = time.monotonic()
    human_move(page, locator)
    locator.click()
    page.wait_for_timeout(850)
    _mark(page, since)


def human_move(page, locator):
    since = time.monotonic()
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    assert box
    page.mouse.move(
        box["x"] + box["width"] / 2,
        box["y"] + box["height"] / 2,
        steps=18,
    )
    page.wait_for_timeout(450)
    _mark(page, since)


def human_fill(page, locator, value):
    since = time.monotonic()
    human_click(page, locator)
    locator.fill("")
    locator.press_sequentially(value, delay=75)
    page.wait_for_timeout(650)
    _mark(page, since)


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


def focus_windows(pages, started, span):
    """Coalesce recorded activity on `pages` into windows, on composite time.

    Composite time is `monotonic - started - VIDEO_TRIM`, because the main
    track is trimmed by that settle before anything is overlaid on it.
    """
    marks = sorted(
        (
            entry["start"] - started - VIDEO_TRIM,
            entry["end"] - started - VIDEO_TRIM,
        )
        for entry in ACTIVITY
        if any(entry["page"] is page for page in pages)
    )
    windows = []
    for start, end in marks:
        end += FOCUS_LINGER
        if windows and start - windows[-1][1] <= FOCUS_MERGE_GAP:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
    merged = []
    for start, end in windows:
        end = max(end, start + FOCUS_MIN)
        start, end = max(0.0, start), min(span, end)
        if end > start:
            merged.append((start, end))
    return merged


def focus_expression(windows):
    """An ffmpeg expression for the 0..1 focus factor over time.

    Each window becomes a trapezoid that ramps up over FOCUS_FADE before it
    starts and back down after it ends; `max()` combines them. Wrapping the
    linear ramp in `0.5-0.5*cos(PI*u)` eases it in and out, and costs only one
    mention of `u` -- a smoothstep would repeat the whole (already long)
    sub-expression three times.
    """
    if not windows:
        return "0"
    ramps = [
        f"clip(min((t-{start - FOCUS_FADE:.3f})/{FOCUS_FADE}"
        f",({end + FOCUS_FADE:.3f}-t)/{FOCUS_FADE}),0,1)"
        for start, end in windows
    ]
    linear = ramps[0]
    for ramp in ramps[1:]:
        linear = f"max({linear},{ramp})"
    return f"(0.5-0.5*cos(PI*({linear})))"


def compose_recording(
    cockpit_video, requester_video, manager_video, offsets, windows=()
):
    """Overlay the Plone role flows on the Cockpit recording, time-aligned.

    The contexts record concurrently against one wall clock, so each Plone clip
    is placed at the offset where it actually happened relative to the start of
    the Cockpit recording, and the gaps between them are filled by holding the
    adjacent frame. The inset is therefore continuous and exactly as long as
    the Cockpit recording, so the reviewer approval lines up with the Cockpit
    auto-refresh that shows it.

    Do not reach for `overlay=...:shortest=1` here. It ends the output at the
    shorter input, which silently dropped the whole reviewer flow in an earlier
    take; building both tracks to the same length keeps every frame.
    """
    cockpit_duration = probe_duration(cockpit_video)
    requester_duration = probe_duration(requester_video)
    manager_duration = probe_duration(manager_video)

    # Every clip opens blank while its first document paints, so the same
    # settle is trimmed off all three -- the Cockpit one included, or the
    # composite opens on white. Trimming the main track by that same amount is
    # what makes the visitor's lead-in exactly its recorded offset.
    requester_lead = offsets["requester"]
    requester_hold = (offsets["manager"] + VIDEO_TRIM) - (
        offsets["requester"] + requester_duration
    )
    manager_hold = cockpit_duration - (offsets["manager"] + manager_duration)
    if requester_hold < 0 or manager_hold < 0:
        raise AssertionError(
            "Recording order broke the timeline: close the visitor context "
            "before opening the reviewer context, and close Cockpit last "
            f"(requester_hold={requester_hold:.2f}, "
            f"manager_hold={manager_hold:.2f})"
        )
    print(
        "PIP timeline:",
        {
            "cockpit": round(cockpit_duration, 2),
            "requester": round(requester_duration, 2),
            "manager": round(manager_duration, 2),
            "requester_at": round(offsets["requester"], 2),
            "manager_at": round(offsets["manager"], 2),
            "composite": round(cockpit_duration - VIDEO_TRIM, 2),
        },
    )
    print(
        "Focus windows:",
        [(round(start, 1), round(end, 1)) for start, end in windows] or "none (static)",
    )

    # Animate the inset between the corner and a centred FOCUS_SCALE of the
    # frame. `scale` normally fixes its size at init; eval=frame re-evaluates
    # per frame, and `overlay`'s own eval=frame then tracks the size it is
    # actually handed, so x/y can be written against the live `w`/`h`.
    focus = focus_expression(windows)
    factor = f"({PIP_SCALE}+{FOCUS_SCALE - PIP_SCALE:.3f}*{focus})"
    inset_w = f"trunc({VIDEO_SIZE['width']}*{factor}/2)*2"
    inset_h = f"trunc({VIDEO_SIZE['height']}*{factor}/2)*2"
    corner_x, corner_y = f"(W-w-{PIP_MARGIN})", f"(H-h-{PIP_MARGIN})"

    nix_ffmpeg(
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-nostats",
        "-i",
        cockpit_video,
        "-i",
        requester_video,
        "-i",
        manager_video,
        "-filter_complex",
        (
            f"[1:v]trim=start={VIDEO_TRIM},setpts=PTS-STARTPTS,"
            f"tpad=start_duration={requester_lead:.3f}:start_mode=clone"
            f":stop_duration={requester_hold:.3f}:stop_mode=clone,fps=25[visitor];"
            f"[2:v]trim=start={VIDEO_TRIM},setpts=PTS-STARTPTS,"
            f"tpad=stop_duration={manager_hold:.3f}:stop_mode=clone,fps=25[reviewer];"
            "[visitor][reviewer]concat=n=2:v=1:a=0[plone];"
            f"[plone]scale=w='{inset_w}':h='{inset_h}':eval=frame,"
            f"pad=w='iw+{2 * PIP_BORDER}':h='ih+{2 * PIP_BORDER}'"
            f":x={PIP_BORDER}:y={PIP_BORDER}"
            f":color={PIP_BORDER_COLOR}:eval=frame[inset];"
            f"[0:v]trim=start={VIDEO_TRIM},setpts=PTS-STARTPTS[main];"
            f"[main][inset]overlay=eval=frame"
            f":x='{corner_x}+((W-w)/2-{corner_x})*{focus}'"
            f":y='{corner_y}+((H-h)/2-{corner_y})*{focus}',"
            "format=yuv420p[out]"
        ),
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
        DOCS / "request-for-quote-pip.webm",
        capture=False,
    )


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    setup = browser.new_context(
        extra_http_headers={"Authorization": basic_auth("manager", "manager")}
    )
    setup_page = setup.new_page()

    # Remove data from earlier probes, including any active instances.
    setup_page.goto(BASE, wait_until="load")
    setup_page.request.delete(
        f"{BASE}/{PAGE_PATH}", headers={"Accept": "application/json"}
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
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            data=json.dumps({"id": deployment["id"]}),
        )

    # Deploy the example. The fixture's seeded Plone admin group is
    # "Administrators", while the example targets "Site Administrators".
    assets = {path.name: path.read_text() for path in ASSETS.iterdir()}
    assets["request-for-quote.bpmn"] = assets["request-for-quote.bpmn"].replace(
        'candidateGroups="Site Administrators"',
        'candidateGroups="Administrators"',
    )
    assets["request-for-quote.bpmn"] = re.sub(
        r"\s*<camunda:inputOutput>\s*"
        r'<camunda:inputParameter name="optionsChosenString">.*?'
        r"</camunda:inputParameter>\s*</camunda:inputOutput>",
        "",
        assets["request-for-quote.bpmn"],
        flags=re.DOTALL,
    ).replace("${optionsChosenString}", "${options}")
    # The fixture has no configured mail connector. Keep the accepted branch
    # as a no-op send task so the reviewer completion is not rolled back.
    assets["request-for-quote.bpmn"] = re.sub(
        r'(<bpmn:sendTask id="Activity_1njb1hw"[^>]*>)\s*'
        r"<bpmn:extensionElements>.*?</bpmn:extensionElements>",
        r'<bpmn:task id="Activity_1njb1hw" name="Send request forward">',
        assets["request-for-quote.bpmn"],
        flags=re.DOTALL,
    )
    assets["request-for-quote.bpmn"] = assets["request-for-quote.bpmn"].replace(
        "</bpmn:sendTask>",
        "</bpmn:task>",
    )
    for name in (
        "request-for-quote-options.dmn",
        "request-for-quote-options.form",
        "request-for-quote-review.form",
        "request-for-quote-start.form",
        "request-for-quote-thanks.form",
        "request-for-quote.bpmn",
    ):
        result = deploy(setup_page, name, assets[name])
        assert result["status"] == 200, (name, result)

    proxy_url = create_and_publish_proxy(setup_page)
    setup_page.screenshot(path=str(DOCS / "request-for-quote-plone-published.png"))
    setup.close()

    # Cockpit is the observer, so it opens first and closes last: every other
    # clip is placed on its timeline by compose_recording().
    cockpit_setup = browser.new_context()
    cockpit_setup_page = cockpit_setup.new_page()
    login_cockpit(cockpit_setup_page)
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
    offsets = {}

    # Log into Cockpit before the process starts, then monitor the same run.
    login_cockpit(cockpit_page)
    cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
    cockpit_page.get_by_role("link", name=PROCESS_KEY).click()
    cockpit_page.wait_for_timeout(800)

    # Anonymous requester: category -> options -> contact details. The context
    # is created here rather than up front so the recording opens on the first
    # real page instead of a blank one.
    requester = browser.new_context(
        viewport=VIDEO_SIZE,
        record_video_dir=str(DOCS),
        record_video_size=VIDEO_SIZE,
    )
    requester.add_init_script(CURSOR_SCRIPT)
    requester_page = requester.new_page()
    offsets["requester"] = time.monotonic() - started

    # StartEvent_1 carries formRef="request-for-quote-start", so the category
    # form is the start form: submitting it is what creates the instance.
    requester_page.goto(proxy_url, wait_until="load")
    requester_page.wait_for_timeout(600)
    human_click(
        requester_page, requester_page.locator("label").filter(has_text="Category A")
    )
    human_click(requester_page, requester_page.get_by_role("button", name="Continue"))
    requester_page.wait_for_load_state("load")
    requester_page.wait_for_timeout(700)

    # The instance exists now. Refresh the definition view so its running count
    # ticks up, then follow the instance -- all before the visitor fills the
    # first task form, so the rest of the visitor flow is watched live in
    # Cockpit instead of being reconstructed after the fact.
    # Re-enter the definition through the Processes list instead of calling
    # reload(): an in-app route change re-queries the instance table just the
    # same, without the ~1 s white flash that re-bootstrapping the Cockpit SPA
    # puts in the middle of the main view. "Processes" matches both the top nav
    # and the breadcrumb, and both lead to #/processes, so take the first.
    human_click(
        cockpit_page,
        cockpit_page.get_by_role("link", name="Processes", exact=True).first,
    )
    cockpit_page.wait_for_timeout(1000)
    human_click(cockpit_page, cockpit_page.get_by_role("link", name=PROCESS_KEY))
    cockpit_page.wait_for_timeout(1200)
    instance_link = cockpit_page.locator('a[href*="/process-instance/"]').last
    instance_link.wait_for(state="visible", timeout=15000)
    human_click(cockpit_page, instance_link)
    cockpit_page.wait_for_timeout(1200)
    auto_refresh = cockpit_page.locator(".toggle-auto-refresh-button")
    sequence_flow = cockpit_page.locator(".toggle-sequence-flow-button")
    print(
        "Cockpit controls:",
        {"auto_refresh": auto_refresh.count(), "sequence_flow": sequence_flow.count()},
    )
    # Auto-refresh is what makes the token advance on screen while the visitor
    # and reviewer work, so turn it on before they do.
    if auto_refresh.count():
        human_click(cockpit_page, auto_refresh)
    if sequence_flow.count():
        human_click(cockpit_page, sequence_flow)
    cockpit_page.screenshot(
        path=str(DOCS / "request-for-quote-cockpit-instance.png"), full_page=True
    )

    # Back to the visitor, who now fills the first task form ("Choose options")
    # while Cockpit shows the waiting token.
    human_click(
        requester_page, requester_page.locator("label").filter(has_text="Option 1")
    )
    human_fill(
        requester_page,
        requester_page.locator("input[type=text]").last,
        "visitor@example.com",
    )
    human_click(requester_page, requester_page.get_by_role("button", name="Submit"))
    requester_page.wait_for_load_state("load")
    requester_page.wait_for_timeout(900)
    requester_text = requester_page.locator("body").inner_text()
    assert "View thank you page" in requester_text
    assert "Internal Server Error" not in requester_text
    # Leave the visitor on the "View thank you page" task. Submitting it after
    # the reviewer branch can produce a transient Plone error while the process
    # join resolves, and it is not needed to show the reviewer completion.
    thank_you_submit = requester_page.get_by_role("button", name="Submit")
    if thank_you_submit.count():
        human_move(requester_page, thank_you_submit)
    requester_page.screenshot(
        path=str(DOCS / "request-for-quote-plone-thank-you.png"), full_page=True
    )
    # Close as soon as the visitor is done. An open context keeps recording the
    # frozen page, which is what padded an earlier take with idle time.
    requester_video = requester_page.video.path()
    requester.close()

    # Cockpit is already following this instance and auto-refreshing, so let it
    # settle on the post-visitor state before the reviewer takes over.
    cockpit_page.wait_for_timeout(1500)

    # Reviewer: inspect and approve the request in Plone.
    manager = browser.new_context(
        viewport=VIDEO_SIZE,
        record_video_dir=str(DOCS),
        record_video_size=VIDEO_SIZE,
        extra_http_headers={"Authorization": basic_auth("manager", "manager")},
    )
    manager.add_init_script(CURSOR_SCRIPT)
    manager_page = manager.new_page()
    offsets["manager"] = time.monotonic() - started
    manager_page.goto(proxy_url, wait_until="load")
    manager_page.wait_for_timeout(800)
    if manager_page.get_by_text("Task list", exact=True).count():
        human_click(
            manager_page,
            manager_page.get_by_role("link", name="Task list", exact=True),
        )
        manager_page.wait_for_timeout(350)
    reviewer_link = manager_page.locator("a").filter(has_text="Review request").first
    assert reviewer_link.count() == 1
    human_click(manager_page, reviewer_link)
    manager_page.wait_for_load_state("load")
    manager_page.wait_for_timeout(750)
    reviewer_submit = manager_page.get_by_role("button", name="Submit")
    assert reviewer_submit.count() == 1
    human_click(manager_page, reviewer_submit)
    manager_page.wait_for_load_state("load")
    manager_page.wait_for_timeout(1100)
    # Reload the proxy after completion so the recording shows the updated
    # task list rather than the transient post-submit notification response.
    manager_page.goto(proxy_url, wait_until="load")
    manager_page.wait_for_timeout(700)
    if manager_page.get_by_text("Task list", exact=True).count():
        human_click(
            manager_page, manager_page.get_by_role("link", name="Task list", exact=True)
        )
    reviewed_text = manager_page.locator("body").inner_text()
    assert "Review request" not in reviewed_text
    assert "Internal Server Error" not in reviewed_text
    manager_page.screenshot(
        path=str(DOCS / "request-for-quote-plone-reviewed.png"), full_page=True
    )
    manager_video = manager_page.video.path()
    manager.close()

    # Let Cockpit's auto-refresh settle on the terminal state, and hold it long
    # enough to read. Cockpit closes last so its recording spans every clip.
    cockpit_page.wait_for_timeout(3500)
    cockpit_page.screenshot(
        path=str(DOCS / "request-for-quote-cockpit-completed.png"),
        full_page=True,
    )

    # Mailpit provides the fixture's observable SMTP result.
    mailpit = cockpit_page.request.get("http://localhost:8025/api/v1/messages")
    assert mailpit.ok
    mailpit_data = mailpit.json()
    print("Mailpit:", mailpit.status, mailpit.text()[:500])
    print("Mailpit message count:", mailpit_data.get("messages_count", 0))
    print("Scenario completed:", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    cockpit_video = cockpit_page.video.path()
    cockpit.close()
    browser.close()

    Path(manager_video).replace(DOCS / "request-for-quote-plone.webm")
    Path(requester_video).replace(DOCS / "request-for-quote-requester.webm")
    Path(cockpit_video).replace(DOCS / "request-for-quote-cockpit.webm")
    compose_recording(
        DOCS / "request-for-quote-cockpit.webm",
        DOCS / "request-for-quote-requester.webm",
        DOCS / "request-for-quote-plone.webm",
        offsets,
        focus_windows(
            (requester_page, manager_page),
            started,
            probe_duration(DOCS / "request-for-quote-cockpit.webm") - VIDEO_TRIM,
        ),
    )
