"""The screenshot registry.

Every image in the end-user guide is declared here exactly once, together with
the doc page that is supposed to reference it. `--check-docs` walks this list
against docs/user/*.md and fails on either half of the drift: an image no page
uses, or a page referencing an image no scenario produces.

Adding a screenshot is therefore a three-step move that cannot be done
halfway: declare the Shot, take it from a scenario, reference it from the page.
"""

from collections import namedtuple
import pathlib
import re


Shot = namedtuple("Shot", "name caption doc")

SHOTS = [
    # --- 02 deploying processes -------------------------------------------
    Shot(
        "controlpanel-bpmn",
        "The BPMN modeler in the Plone control panel",
        "02-deploying-processes.md",
    ),
    Shot(
        "controlpanel-dmn",
        "The DMN modeler, for decision tables",
        "02-deploying-processes.md",
    ),
    Shot("controlpanel-form", "The form playground", "02-deploying-processes.md"),
    Shot(
        "controlpanel-deployments",
        "Deployments currently known to the engine",
        "02-deploying-processes.md",
    ),
    # --- 03 publishing a process ------------------------------------------
    Shot(
        "bpm-proxy-add-form",
        "Adding a Bpm Proxy and choosing a process",
        "03-publishing-a-process.md",
    ),
    Shot(
        "bpm-proxy-start-form",
        "The deployed start form rendered in Plone",
        "03-publishing-a-process.md",
    ),
    Shot("bpm-proxy-diagram", "The Process diagram tab", "03-publishing-a-process.md"),
    Shot(
        "bpm-proxy-validation",
        "Server-side validation rejecting a submission",
        "03-publishing-a-process.md",
    ),
    # --- 04 working with tasks --------------------------------------------
    Shot(
        "task-form",
        "A user task rendered as a sub-page of the proxy",
        "04-working-with-tasks.md",
    ),
    Shot("task-list", "The Task list tab", "04-working-with-tasks.md"),
    # --- 05 attachments ----------------------------------------------------
    Shot(
        "attachments-task",
        "A task offering the Add attachment button",
        "05-attachments.md",
    ),
    Shot(
        "attachments-listing",
        "Files uploaded against one process instance",
        "05-attachments.md",
    ),
    # --- 06 portlets -------------------------------------------------------
    Shot("portlet-tasks", "The Task list portlet", "06-portlets.md"),
    Shot("portlet-message", "The Message dispatch portlet", "06-portlets.md"),
    # --- 07 content rules --------------------------------------------------
    Shot(
        "contentrules-list",
        "The BPMN signal rules installed by the add-on",
        "07-content-rules.md",
    ),
]

BY_NAME = {shot.name: shot for shot in SHOTS}

IMAGE_RE = re.compile(r"!\[[^\]]*\]\(images/([A-Za-z0-9._-]+)\.png\)")


def check_docs(docs_dir):
    """Return a list of drift problems between SHOTS and docs/user/*.md."""
    docs_dir = pathlib.Path(docs_dir)
    problems = []

    referenced = {}
    for page in sorted(docs_dir.glob("*.md")):
        for name in IMAGE_RE.findall(page.read_text()):
            referenced.setdefault(name, set()).add(page.name)

    for shot in SHOTS:
        if shot.name not in referenced:
            problems.append(
                f"{shot.name}: taken but referenced by no page (expected {shot.doc})"
            )
        elif shot.doc not in referenced[shot.name]:
            problems.append(
                f"{shot.name}: declared for {shot.doc} but referenced by "
                f"{', '.join(sorted(referenced[shot.name]))}"
            )

    for name, pages in sorted(referenced.items()):
        if name not in BY_NAME:
            problems.append(
                f"{name}: referenced by {', '.join(sorted(pages))} but no "
                f"scenario produces it"
            )

    return problems
