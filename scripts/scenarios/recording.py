"""Shared helpers for recorded scenario title cards and timing manifests."""

from pathlib import Path
import json


TITLE_CARD_VERSION = 1


def make_title_card_segment(ffmpeg_runner, output, title, duration=8.0):
    """Render an independent title-card video from ``title`` metadata."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def escape(value):
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace(",", "\\,")
            .replace("[", "\\[")
            .replace("]", "\\]")
        )

    eyebrow = escape(title["eyebrow"])
    heading = escape(title["title"])
    subtitle = escape(title["subtitle"])
    filters = (
        "drawtext=font='DejaVu Sans':"
        f"text='{eyebrow}':fontcolor=#7dd3fc:fontsize=40:x=160:y=330,"
        "drawtext=font='DejaVu Sans':"
        f"text='{heading}':fontcolor=white:fontsize=76:x=160:y=420,"
        "drawtext=font='DejaVu Sans':"
        f"text='{subtitle}':fontcolor=#cbd5e1:fontsize=40:x=160:y=560"
    )
    ffmpeg_runner(
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c=#0f172a:s=1920x1080:d={float(duration):.3f}",
        "-vf",
        filters,
        "-r",
        "25",
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


def write_timing_manifest(path, data):
    """Write a versioned, recut-friendly timing manifest."""
    payload = {"version": TITLE_CARD_VERSION, **data}
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")


def prepare_title_segments(ffmpeg_runner, clips, output):
    """Create or reuse title segments and return their paths."""
    output = Path(output)
    segments = []
    for index, clip in enumerate(clips):
        title = clip.get("title")
        path = clip.get("title_segment")
        if path:
            path = Path(path)
        else:
            path = output.with_name(f"{output.stem}-title-{index + 1:02d}.webm")
        if title and not path.exists():
            make_title_card_segment(
                ffmpeg_runner,
                path,
                title,
                clip.get("title_duration", 8.0),
            )
        if not path.exists():
            raise FileNotFoundError(
                f"Missing title segment for clip {clip.get('video')}: {path}"
            )
        clip["title_segment"] = str(path)
        clip.setdefault("title_duration", 8.0)
        segments.append(path)
    return segments


def ensure_cockpit_toggle(page, selector, label):
    """Enable a Cockpit toggle and fail instead of silently skipping it."""
    button = page.locator(selector).first
    button.wait_for(state="visible", timeout=10000)

    def enabled():
        pressed = button.get_attribute("aria-pressed")
        aria_label = (button.get_attribute("aria-label") or "").lower()
        if pressed is not None:
            return pressed == "true"
        if label == "auto-refresh":
            return "off" in aria_label
        return "hide" in aria_label or "disable" in aria_label

    if not enabled():
        button.click()
    for _ in range(10):
        if enabled():
            return
        page.wait_for_timeout(300)
    raise AssertionError(f"Cockpit {label} did not become enabled")


def delete_demo_content(page, base_url, paths):
    """Remove scenario-owned top-level content before a recording."""
    for path in paths:
        response = page.request.delete(
            f"{base_url}/{path.lstrip('/')}",
            headers={"Accept": "application/json"},
        )
        if response.status not in (200, 204, 404):
            raise AssertionError(
                f"Could not remove demo content {path!r}: "
                f"{response.status} {response.text()}"
            )
