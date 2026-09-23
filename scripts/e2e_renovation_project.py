"""Record the upstream renovation case-management scenario.

Run from the repository root with::

    playwright-python scripts/e2e_renovation_project.py

Prepare the services, deploy ``examples/renovation-project`` and run
``make bootstrap-renovation-demo`` first. The runner records the case
document review and close-case flow without requiring an external worker.
"""

from pathlib import Path
import base64
import json
import subprocess
import time

from playwright.sync_api import sync_playwright

from recording import (
    ensure_cockpit_toggle,
    prepare_title_segments,
    write_timing_manifest,
)


BASE = "http://localhost:8080/Plone"
COCKPIT = "http://localhost:8081/operaton/app/cockpit/default"
CASE = f"{BASE}/renovation-project-demo"
DOCS = Path("docs")
TIMING_PATH = DOCS / "renovation-project-timing.json"
VIDEO_SIZE = {"width": 1920, "height": 1080}
ACTOR_SLIDE_DURATION = 8.0
VIDEO_TRIM = 0.8
PIP_SCALE = 0.4
PIP_MARGIN = 24
PIP_BORDER = 3


CURSOR_SCRIPT = """
(() => {
  if (window.top !== window) return;
  const install = () => {
    const style = document.createElement('style');
    style.textContent = `
      #bpmproxy-recording-cursor {
        position: fixed; left: 50%; top: 50%; z-index: 2147483647;
        width: 24px; height: 24px; border: 2px solid #ff3b30;
        border-radius: 50%; pointer-events: none;
        transform: translate(-50%, -50%); box-shadow: 0 0 0 2px white;
      }
      .bpmproxy-recording-click {
        position: fixed; z-index: 2147483646; width: 56px; height: 56px;
        border: 4px solid #ff3b30; border-radius: 50%; pointer-events: none;
        transform: translate(-50%, -50%);
        animation: bpmproxy-click .8s ease-out;
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


def show_actor_slide(page, eyebrow, title, subtitle):
    page._bpmproxy_title = {
        "eyebrow": eyebrow,
        "title": title,
        "subtitle": subtitle,
    }
    page.wait_for_timeout(int(ACTOR_SLIDE_DURATION * 1000))


def nix_ffmpeg(tool, *args, capture=True):
    expression = (
        'with (builtins.getFlake "nixpkgs").legacyPackages.'
        "${builtins.currentSystem}; ffmpeg-headless"
    )
    return subprocess.run(
        ["nix", "shell", "--impure", "--expr", expression, "--command", tool]
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


def compose_recording(cockpit_video, clips, output, timing_path=None):
    """Keep Cockpit as the main view and show each actor turn as a PIP."""
    cockpit_duration = probe_duration(cockpit_video)
    filters = ["[0:v]setpts=PTS-STARTPTS[base]"]
    current = "base"
    inputs = [cockpit_video]
    for index, clip in enumerate(clips, 1):
        inputs.append(clip["video"])
        duration = probe_duration(clip["video"])
        start = clip["offset"] + VIDEO_TRIM
        end = min(cockpit_duration, start + max(0, duration - VIDEO_TRIM))
        next_label = f"pip{index}"
        filters.append(
            f"[{index}:v]setpts=PTS-STARTPTS,"
            f"scale=iw*{PIP_SCALE}:ih*{PIP_SCALE}[clip{index}]"
        )
        filters.append(
            f"[{current}][clip{index}]overlay="
            f"x=W-w-{PIP_MARGIN}:y=H-h-{PIP_MARGIN}:"
            f"enable='between(t,{start:.3f},{end:.3f})':"
            f"eof_action=repeat[{next_label}]"
        )
        current = next_label
    filter_complex = ";".join(filters)
    nix_ffmpeg(
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-nostats",
        *sum((["-i", str(path)] for path in inputs), []),
        "-filter_complex",
        filter_complex,
        "-map",
        f"[{current}]",
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
    if timing_path:
        write_timing_manifest(
            timing_path,
            {
                "cockpit_video": str(cockpit_video),
                "clips": clips,
                "output": str(output),
            },
        )
    return output


def wait_for_task(page, name, timeout_ms=60000):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        page.goto(CASE, wait_until="load")
        link = page.locator("a:visible").filter(has_text=name)
        if link.count():
            return link.first
        page.wait_for_timeout(1000)
    raise AssertionError(f"Task {name!r} did not appear")


def add_document(page):
    page.goto(CASE, wait_until="load")
    human_click(page, page.get_by_role("link", name="Add new…"))
    human_click(page, page.get_by_role("link", name="Page", exact=True))
    page.locator("#form-widgets-IDublinCore-title").fill("Initial renovation document")
    page.frame_locator("iframe").locator("body").first.fill(
        "The case document requires independent owner and inspector review."
    )
    human_click(page, page.get_by_role("button", name="Save"))
    page.wait_for_load_state("load")


def workflow(page, action):
    response = page.request.post(
        f"{CASE}/@workflow/{action}",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        data="{}",
    )
    assert response.status == 200, response.text()


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        manager = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("manager", "manager")}
        )
        manager_page = manager.new_page()
        manager_page.goto(CASE, wait_until="load")

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

        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name="renovation-case").click()
        cockpit_page.wait_for_timeout(1200)

        def configure_cockpit():
            ensure_cockpit_toggle(
                cockpit_page, ".toggle-auto-refresh-button", "auto-refresh"
            )
            ensure_cockpit_toggle(
                cockpit_page, ".toggle-sequence-flow-button", "sequence-flow"
            )

        def record_turn(username, password, action, turn, title, subtitle):
            context = browser.new_context(
                viewport=VIDEO_SIZE,
                record_video_dir=str(DOCS),
                record_video_size=VIDEO_SIZE,
                extra_http_headers={
                    "Authorization": basic_auth(username, password)
                },
            )
            context.add_init_script(CURSOR_SCRIPT)
            page = context.new_page()
            offset = time.monotonic() - started
            action(page, turn, title, subtitle)
            video = page.video.path()
            context.close()
            cockpit_page.bring_to_front()
            cockpit_page.wait_for_timeout(6000)
            clips.append(
                {
                    "video": str(video),
                    "offset": offset,
                    "title": getattr(page, "_bpmproxy_title", None),
                    "title_duration": ACTOR_SLIDE_DURATION,
                }
            )

        def contractor_adds_document(page, turn, title, subtitle):
            page.goto(CASE, wait_until="load")
            show_actor_slide(page, f"Renovation case · {turn} / 4", title, subtitle)
            add_document(page)
            page.screenshot(
                path=str(DOCS / "renovation-project-document-added.png"),
                full_page=True,
            )

        record_turn(
            "contractor",
            "contractor",
            contractor_adds_document,
            1,
            "Contractor",
            "Adding a document to the renovation case",
        )

        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name="renovation-page-review").click()
        cockpit_page.wait_for_timeout(1200)
        instance = cockpit_page.locator('a[href*="/process-instance/"]').last
        instance.wait_for(state="visible", timeout=30000)
        human_click(cockpit_page, instance)
        configure_cockpit()
        cockpit_page.screenshot(
            path=str(DOCS / "renovation-project-cockpit-parallel-review.png"),
            full_page=True,
        )

        def approves(page, turn, title, subtitle):
            page.goto(CASE, wait_until="load")
            task_name = "Owner reviews page" if title == "Owner" else "Inspector reviews page"
            task = wait_for_task(page, task_name)
            human_click(page, task)
            show_actor_slide(page, f"Renovation case · {turn} / 4", title, subtitle)
            human_click(page, page.get_by_label("Approved"))
            human_click(page, page.get_by_role("button", name="Submit review"))
            page.wait_for_load_state("load")

        record_turn(
            "owner", "owner", approves, 2, "Owner", "Reviewing the added page"
        )
        cockpit_page.reload(wait_until="load")
        cockpit_page.wait_for_timeout(1200)
        configure_cockpit()
        record_turn(
            "inspector",
            "inspector",
            approves,
            3,
            "Inspector",
            "Reviewing the added page for compliance",
        )

        def manager_closes(page, turn, title, subtitle):
            page.goto(CASE, wait_until="load")
            show_actor_slide(page, f"Renovation case · {turn} / 4", title, subtitle)
            workflow(page, "close-case")
            page.reload(wait_until="load")
            assert "Closed" in page.locator("body").inner_text()
            page.screenshot(
                path=str(DOCS / "renovation-project-closed.png"), full_page=True
            )

        record_turn(
            "manager",
            "manager",
            manager_closes,
            4,
            "Case manager",
            "Closing the completed renovation case",
        )

        cockpit_page.goto(f"{COCKPIT}/#/history", wait_until="load")
        cockpit_page.wait_for_timeout(2500)
        history_instance = cockpit_page.locator('a[href*="/process-instance/"]').last
        history_instance.wait_for(state="visible", timeout=30000)
        human_click(cockpit_page, history_instance)
        cockpit_page.wait_for_timeout(1500)
        info_panel = cockpit_page.get_by_role(
            "button", name="Minimize info panel", exact=True
        )
        if info_panel.count() and info_panel.first.is_visible():
            human_click(cockpit_page, info_panel.first)
        cockpit_page.wait_for_timeout(5000)
        cockpit_page.screenshot(
            path=str(DOCS / "renovation-project-cockpit-completed.png"),
            full_page=True,
        )

        title_segments = prepare_title_segments(
            nix_ffmpeg, clips, DOCS / "renovation-project-pip.webm"
        )
        for clip, segment in zip(clips, title_segments):
            clip["title_segment"] = str(segment)
        cockpit_video = cockpit_page.video.path()
        cockpit.close()
        manager.close()
        browser.close()

        output = DOCS / "renovation-project-pip.webm"
        compose_recording(cockpit_video, clips, output, TIMING_PATH)
        print(f"Scenario completed: {output}")


if __name__ == "__main__":
    main()
