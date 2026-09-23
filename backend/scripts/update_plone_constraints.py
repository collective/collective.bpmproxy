#!/usr/bin/env python3
"""Regenerate [tool.uv] constraint-dependencies in pyproject.toml from
Plone's official constraints for the 6.1 release line
(https://dist.plone.org/release/6.1-latest/constraints.txt), the same
source tox.ini applies directly via `-c <url>`.

`uv lock`/`uv sync` (project mode) have no mechanism to reference a remote
constraints file directly (`uv lock --constraint`/`UV_CONSTRAINT` only
apply to the pip-compatible `uv pip` interface) so the pins must be
embedded as a static list. Run via `make lock`, which regenerates this
list and then runs `uv lock`.
"""

import re
import sys
import urllib.request
from pathlib import Path


CONSTRAINTS_URL = "https://dist.plone.org/release/6.1-latest/constraints.txt"
PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"

HEADER = """[tool.uv]
# Pin resolution to Plone's official known-good versions for the 6.1
# release line (https://dist.plone.org/release/6.1-latest/constraints.txt,
# same source tox.ini applies directly), regenerated via `make lock`
# (backend/scripts/update_plone_constraints.py).
# Without this, uv's default "highest" resolution strategy picks
# untested newer releases (e.g. it previously resolved Products.CMFPlone
# 6.2.1 / plone.restapi 10.0.2 instead of the tested 6.1.5 / 9.15.6),
# which is what caused the broken-looking site.
"""

LINE_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*==\s*([^\s;]+)\s*(?:;\s*(.*))?$")


def fetch_constraints(text: str) -> list[str]:
    entries: dict[tuple[str, str], tuple[str, str, str | None]] = {}
    order: list[tuple[str, str]] = []

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            print(f"WARNING: skipping unparsed constraint line: {raw_line!r}", file=sys.stderr)
            continue
        name, version, marker = m.group(1), m.group(2), m.group(3)
        key = (name.lower(), marker or "")
        if key in entries and entries[key][1] != version:
            print(
                f"WARNING: conflicting pins for {name} (marker={marker!r}): "
                f"{entries[key][1]} -> {version}, keeping the last one",
                file=sys.stderr,
            )
        if key not in entries:
            order.append(key)
        entries[key] = (name, version, marker)

    lines = []
    for key in order:
        name, version, marker = entries[key]
        req = f"{name}=={version}"
        if marker:
            req += f"; {marker.replace(chr(34), chr(39))}"
        lines.append(req)
    lines.sort(key=str.lower)
    return lines


def render_block(lines: list[str]) -> str:
    body = "\n".join(f'    "{line}",' for line in lines)
    return f"{HEADER}constraint-dependencies = [\n{body}\n]\n"


def main() -> None:
    print(f"Fetching {CONSTRAINTS_URL} ...", file=sys.stderr)
    with urllib.request.urlopen(CONSTRAINTS_URL, timeout=30) as resp:  # noqa: S310
        text = resp.read().decode()

    lines = fetch_constraints(text)
    print(f"Parsed {len(lines)} constraint entries", file=sys.stderr)
    block = render_block(lines)

    content = PYPROJECT_PATH.read_text()
    pattern = re.compile(r"\[tool\.uv\]\n.*?\n\]\n", re.DOTALL)
    if pattern.search(content):
        content = pattern.sub(block, content, count=1)
    else:
        marker = '[project.entry-points."plone.autoinclude.plugin"]'
        assert marker in content, "insertion point not found in pyproject.toml"
        content = content.replace(marker, block + "\n" + marker, 1)

    PYPROJECT_PATH.write_text(content)
    print(f"Updated {PYPROJECT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
