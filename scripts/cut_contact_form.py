"""Re-cut the contact-form video from persisted timing data."""

from e2e_contact_form import compose_recording
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
TIMING = ROOT / "docs/contact-form-timing.json"
OUTPUT = ROOT / "docs/contact-form-pip.webm"


def main():
    timing = json.loads(TIMING.read_text())
    if timing.get("version") != 1:
        raise ValueError(f"Unsupported timing data version: {timing.get('version')}")

    def resolve(path):
        path = Path(path)
        return path if path.is_absolute() else ROOT / path

    clips = []
    for clip in timing["clips"]:
        item = {**clip, "video": resolve(clip["video"])}
        item["title_segment"] = str(resolve(clip["title_segment"]))
        clips.append(item)
    compose_recording(
        resolve(timing["cockpit_video"]),
        clips,
        OUTPUT,
        timing["cockpit_main_ranges"],
    )


if __name__ == "__main__":
    main()
