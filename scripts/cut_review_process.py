"""Re-cut the review-process video from persisted timing data.

Run from the repository root:

    playwright-python scripts/cut_review_process.py
"""

from e2e_review_process import compose_recording
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
TIMING = ROOT / "docs/review-process-timing.json"
OUTPUT = ROOT / "docs/review-process-pip.webm"


def main():
    timing = json.loads(TIMING.read_text())
    if timing.get("version") != 1:
        raise ValueError(f"Unsupported timing data version: {timing.get('version')}")

    def resolve(path):
        path = Path(path)
        return path if path.is_absolute() else ROOT / path

    clips = [
        {
            **clip,
            "video": resolve(clip["video"]),
            "title_segment": str(resolve(clip["title_segment"])),
        }
        for clip in timing["clips"]
    ]
    compose_recording(
        resolve(timing["cockpit_video"]),
        clips,
        OUTPUT,
        gap_focus=[gap["focus"] for gap in timing["gaps"]],
        final_history_at=timing.get("final_history_at"),
    )


if __name__ == "__main__":
    main()
