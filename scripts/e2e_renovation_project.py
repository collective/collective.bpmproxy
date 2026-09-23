"""Record the upstream renovation case-management scenario.

Run from the repository root with::

    playwright-python scripts/e2e_renovation_project.py

Prepare the services, deploy ``examples/renovation-project`` and run
``make bootstrap-renovation-demo`` first. The runner records the case
document review and close-case flow without requiring an external worker.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
from recording import ensure_cockpit_toggle
from recording import prepare_title_segments
from recording import write_timing_manifest
import base64
import json
import subprocess
import time


BASE = "http://localhost:8080/Plone"
COCKPIT = "http://localhost:8081/operaton/app/cockpit/default"
CASE = f"{BASE}/renovation-project-demo"
ASSETS = Path("examples/renovation-project")
DOCS = Path("docs")
TIMING_PATH = DOCS / "renovation-project-timing.json"
VIDEO_SIZE = {"width": 1920, "height": 1080}
ACTOR_SLIDE_DURATION = 8.0
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
    """Make Plone the main view and use Operaton as the observer view.

    Actor turns are shown full-frame from their first recorded frame, so the
    contractor's clip starts before the document container is added. Between
    turns, Operaton becomes the main view; the frozen Plone frame is retained
    as a larger (2x) inset while the submitted form is reflected by the engine.
    """
    cockpit_duration = probe_duration(cockpit_video)
    durations = [probe_duration(clip["video"]) for clip in clips]
    # The manager turn ends at about 1:55 in the composed timeline; switch
    # to the completed Operaton instance immediately after that turn.
    final_focus_switch_at = 117.0
    gaps = []
    for index in range(len(clips) + 1):
        start = 0 if index == 0 else clips[index - 1]["offset"] + durations[index - 1]
        end = clips[index]["offset"] if index < len(clips) else cockpit_duration
        gaps.append((start, max(start, end)))

    filters = []
    segment_labels = []
    inputs = ["-i", cockpit_video] + sum(
        (["-i", str(clip["video"])] for clip in clips), []
    )

    def cockpit_slice(label, start, end):
        filters.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,fps=25[{label}]"
        )

    def pad(label, output_label, scale):
        filters.append(
            f"[{label}]scale=iw*{scale}:-2,"
            f"pad=iw+{2 * PIP_BORDER}:ih+{2 * PIP_BORDER}:"
            f"{PIP_BORDER}:{PIP_BORDER}:color={PIP_BORDER_COLOR}[{output_label}]"
        )

    # Keep Plone visible from the beginning, including the opening navigation
    # and the contractor adding the renovation document.
    initial_start, initial_end = gaps[0]
    if initial_end - initial_start > 0.05:
        # The first clip opens on the empty site. Do not freeze its final
        # frame here: that would show the created case before the manager turn.
        freeze = 0
        filters.append(
            f"[1:v]trim=start={freeze:.3f}:end={freeze + 0.04:.3f},"
            f"setpts=PTS-STARTPTS,tpad=stop_duration={initial_end:.3f}:"
            f"stop_mode=clone,fps=25[initial_plone]"
        )
        cockpit_slice("initial_cockpit_raw", 0, initial_end)
        pad("initial_cockpit_raw", "initial_cockpit", PIP_SCALE)
        filters.append("[initial_plone][initial_cockpit]overlay=W-w-24:H-h-24[initial]")
        segment_labels.append("initial")

    for index, clip in enumerate(clips):
        input_index = index + 1
        duration = durations[index]
        body_start = 0
        if duration - body_start > 0.05:
            filters.append(
                f"[{input_index}:v]trim=start={body_start:.3f},"
                f"setpts=PTS-STARTPTS,fps=25[turn{index}]"
            )
            cockpit_slice(
                f"turn{index}_cockpit_raw",
                clip["offset"] + body_start,
                clip["offset"] + duration,
            )
            pad(f"turn{index}_cockpit_raw", f"turn{index}_cockpit", PIP_SCALE)
            filters.append(
                f"[turn{index}][turn{index}_cockpit]"
                f"overlay=W-w-24:H-h-24[turn{index}_out]"
            )
            segment_labels.append(f"turn{index}_out")

        gap_start, gap_end = gaps[index + 1]
        gap_duration = gap_end - gap_start
        if gap_duration > 0.05:
            freeze = max(0, duration - 0.04)
            # The first three turns submit Plone forms and produce a new
            # engine state; keep the final case-manager transition at normal
            # inset size because it does not submit a Camunda form.
            pip_scale = PIP_SCALE * 2 if index < len(clips) - 1 else PIP_SCALE
            if index == len(clips) - 1 and gap_start < final_focus_switch_at < gap_end:
                pre_duration = final_focus_switch_at - gap_start
                post_duration = gap_end - final_focus_switch_at
                filters.append(
                    f"[{input_index}:v]trim=start={freeze:.3f}:end={freeze + 0.04:.3f},"
                    f"setpts=PTS-STARTPTS,tpad=stop_duration={pre_duration:.3f}:"
                    f"stop_mode=clone,fps=25[final_pre_plone]"
                )
                cockpit_slice("final_pre_cockpit_raw", gap_start, final_focus_switch_at)
                pad("final_pre_cockpit_raw", "final_pre_cockpit", pip_scale)
                filters.append(
                    "[final_pre_plone][final_pre_cockpit]"
                    "overlay=W-w-24:H-h-24[final_pre]"
                )
                segment_labels.append("final_pre")

                filters.append(
                    f"[{input_index}:v]trim=start={freeze:.3f}:end={freeze + 0.04:.3f},"
                    f"setpts=PTS-STARTPTS,tpad=stop_duration={post_duration:.3f}:"
                    f"stop_mode=clone,fps=25[final_post_plone]"
                )
                cockpit_slice("final_post_cockpit", final_focus_switch_at, gap_end)
                pad("final_post_plone", "final_post_inset", pip_scale)
                filters.append(
                    "[final_post_cockpit][final_post_inset]"
                    "overlay=W-w-24:H-h-24[final_post]"
                )
                segment_labels.append("final_post")
            else:
                filters.append(
                    f"[{input_index}:v]trim=start={freeze:.3f}:end={freeze + 0.04:.3f},"
                    f"setpts=PTS-STARTPTS,tpad=stop_duration={gap_duration:.3f}:"
                    f"stop_mode=clone,fps=25[gap{index}_plone]"
                )
                cockpit_slice(f"gap{index}_cockpit_raw", gap_start, gap_end)
                pad(f"gap{index}_cockpit_raw", f"gap{index}_cockpit_inset", pip_scale)
                filters.append(
                    f"[gap{index}_plone][gap{index}_cockpit_inset]"
                    f"overlay=W-w-24:H-h-24[gap{index}]"
                )
                segment_labels.append(f"gap{index}")

    filters.append(
        f"{''.join(f'[{label}]' for label in segment_labels)}"
        f"concat=n={len(segment_labels)}:v=1:a=0,format=yuv420p[out]"
    )
    filter_complex = ";".join(filters)
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
    if timing_path:
        write_timing_manifest(
            timing_path,
            {
                "cockpit_video": str(cockpit_video),
                "clips": clips,
                "output": str(output),
                "main_view": "plone",
                "post_submit_operaton_scale": PIP_SCALE * 2,
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
    return page.request.post(
        f"{CASE}/@workflow/{action}",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        data="{}",
    )


def main():
    global CASE
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        manager = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("manager", "manager")}
        )
        manager_page = manager.new_page()
        manager_page.goto(BASE, wait_until="load")
        manager_page.request.delete(
            CASE,
            headers={"Accept": "application/json"},
        )
        deployments = manager_page.request.get(
            f"{BASE}/@bpmproxy-deployments",
            headers={"Accept": "application/json"},
        )
        assert deployments.status == 200, deployments.text()
        for deployment in deployments.json():
            response = manager_page.request.delete(
                f"{BASE}/@bpmproxy-deployments",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                data=json.dumps({"id": deployment["id"]}),
            )
            assert response.status == 200, response.text()
        for asset in ASSETS.iterdir():
            if asset.suffix not in (".bpmn", ".form"):
                continue
            response = manager_page.request.post(
                f"{BASE}/@bpmproxy-deploy",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                data=json.dumps({"name": asset.name, "xml": asset.read_text()}),
            )
            assert response.status == 200, response.text()
        case_url = None
        document_url = None

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
                extra_http_headers={"Authorization": basic_auth(username, password)},
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

        def manager_creates_case(page, turn, title, subtitle):
            nonlocal case_url
            page.goto(BASE, wait_until="load")
            show_actor_slide(page, f"Renovation case · {turn} / 5", title, subtitle)
            human_click(page, page.get_by_role("link", name="Add new…"))
            human_click(
                page,
                page.get_by_role("link", name="Renovation Project", exact=True),
            )
            page.locator("#form-widgets-IBasic-title").fill("Demo renovation project")
            human_click(page, page.get_by_role("button", name="Save"))
            page.wait_for_load_state("load")
            case_url = page.url.removesuffix("/view")

        def contractor_adds_document(page, turn, title, subtitle):
            nonlocal document_url
            page.goto(CASE, wait_until="load")
            show_actor_slide(page, f"Renovation case · {turn} / 5", title, subtitle)
            add_document(page)
            document_url = page.url.removesuffix("/view")
            page.screenshot(
                path=str(DOCS / "renovation-project-document-added.png"),
                full_page=True,
            )

        record_turn(
            "manager",
            "manager",
            manager_creates_case,
            1,
            "Case manager",
            "Creating the demo renovation project",
        )
        assert case_url
        CASE = case_url
        sharing = manager_page.request.post(
            f"{CASE}/@sharing",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "entries": [
                        {
                            "id": "Renovation Contractors",
                            "roles": {"Contributor": True, "Editor": True},
                            "type": "group",
                        },
                        {
                            "id": "Renovation Owners",
                            "roles": {"Reviewer": True},
                            "type": "group",
                        },
                        {
                            "id": "Renovation Inspectors",
                            "roles": {"Reviewer": True},
                            "type": "group",
                        },
                    ]
                }
            ),
        )
        assert sharing.status in (200, 204), sharing.text()

        # The new case is now visible in the definition list. Enter its live
        # instance before the contractor turn so auto-refresh and sequence
        # flow are active for every subsequent engine update.
        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name="renovation-case").click()
        cockpit_page.wait_for_timeout(1200)
        case_instance = cockpit_page.locator('a[href*="/process-instance/"]').last
        case_instance.wait_for(state="visible", timeout=30000)
        human_click(cockpit_page, case_instance)
        configure_cockpit()

        record_turn(
            "contractor",
            "contractor",
            contractor_adds_document,
            2,
            "Contractor",
            "Adding a document to the renovation case",
        )

        assert document_url
        sharing = manager_page.request.post(
            f"{document_url}/@sharing",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "entries": [
                        {
                            "id": username,
                            "roles": {"Reader": True},
                            "type": "user",
                        }
                        for username in ("owner", "inspector")
                    ]
                }
            ),
        )
        assert sharing.status in (200, 204), sharing.text()

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
            task_name = (
                "Owner reviews page" if title == "Owner" else "Inspector reviews page"
            )
            task = wait_for_task(page, task_name)
            human_click(page, task)
            show_actor_slide(page, f"Renovation case · {turn} / 5", title, subtitle)
            human_click(page, page.get_by_label("Approved"))
            human_click(page, page.get_by_role("button", name="Submit review"))
            page.wait_for_load_state("load")

        record_turn("owner", "owner", approves, 3, "Owner", "Reviewing the added page")
        cockpit_page.reload(wait_until="load")
        cockpit_page.wait_for_timeout(1200)
        configure_cockpit()
        record_turn(
            "inspector",
            "inspector",
            approves,
            4,
            "Inspector",
            "Reviewing the added page for compliance",
        )
        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name="renovation-case").click()
        cockpit_page.wait_for_timeout(1200)
        main_instance = cockpit_page.locator('a[href*="/process-instance/"]').last
        main_instance.wait_for(state="visible", timeout=30000)
        human_click(cockpit_page, main_instance)
        configure_cockpit()
        cockpit_page.wait_for_timeout(1800)

        def manager_closes(page, turn, title, subtitle):
            page.goto(CASE, wait_until="load")
            show_actor_slide(page, f"Renovation case · {turn} / 5", title, subtitle)
            state = page.get_by_role("link", name="State: Open")
            human_click(page, state)
            close_case = page.locator(
                '#plone-contentmenu-workflow a[href*="workflow_action=close-case"]'
            )
            close_case.wait_for(state="visible", timeout=10000)
            human_click(page, close_case.last)
            page.wait_for_load_state("load")
            page.reload(wait_until="load")
            assert "Closed" in page.locator("body").inner_text()
            page.screenshot(
                path=str(DOCS / "renovation-project-closed.png"), full_page=True
            )

        record_turn(
            "manager",
            "manager",
            manager_closes,
            5,
            "Case manager",
            "Closing the completed renovation case",
        )

        # The close transition can finish the engine instance while Cockpit's
        # auto-refresh request is between intervals. Force one refresh before
        # opening History so the completion flow is visible in the recording.
        cockpit_page.reload(wait_until="load")
        cockpit_page.wait_for_timeout(1800)
        cockpit_page.goto(f"{COCKPIT}/#/processes", wait_until="load")
        cockpit_page.get_by_role("link", name="renovation-case").click()
        cockpit_page.wait_for_timeout(1200)
        history_tab = cockpit_page.get_by_text("History", exact=True).last
        history_tab.wait_for(state="visible", timeout=10000)
        human_click(cockpit_page, history_tab)
        cockpit_page.wait_for_timeout(2500)
        history_instance = cockpit_page.locator('a[href*="/process-instance/"]').last
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
            path=str(DOCS / "renovation-project-cockpit-completed.png"),
            full_page=True,
        )

        title_segments = prepare_title_segments(
            nix_ffmpeg, clips, DOCS / "renovation-project-pip.webm"
        )
        for clip, segment in zip(clips, title_segments, strict=True):
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
