"""Re-cut the renovation-project video from persisted timing data."""

from pathlib import Path
import json

from e2e_renovation_project import compose_recording


ROOT = Path(__file__).resolve().parents[1]
TIMING = ROOT / "docs/renovation-project-timing.json"
OUTPUT = ROOT / "docs/renovation-project-pip.webm"


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
        timing_path=None,
    )


if __name__ == "__main__":
    main()
