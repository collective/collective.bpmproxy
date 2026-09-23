"""operaton-tasks worker for the renovation case's workflow topic.

A pure-Python alternative to ../renovation-bot/tasks.robot, built on
https://pypi.org/project/operaton-tasks/ (the library purjo itself is built
on) instead of purjo/Robot Framework. Run with:

    uv run --env-file secrets.env --with="operaton-tasks[cli]" operaton-tasks serve tasks.py

or via `make serve` in this directory.
"""

import os

import aiohttp

import operaton.tasks
from operaton.tasks.types import CompleteExternalTaskDto
from operaton.tasks.types import ExternalTaskComplete
from operaton.tasks.types import LockedExternalTaskDto

PLONE_URL = os.environ.get("PLONE_URL", "http://localhost:8080/Plone")
PLONE_AUTHORIZATION = os.environ.get("PLONE_AUTHORIZATION", "")


@operaton.tasks.task("Plone Workflow Transition")
async def transition_content(task: LockedExternalTaskDto) -> ExternalTaskComplete:
    """Resolve a Plone content UUID and POST the requested workflow transition."""
    variables = task.variables or {}
    try:
        uuid = variables["caseUuid"].value
        transition = variables["transition"].value
    except KeyError as exc:
        raise RuntimeError(f"Missing required process variable: {exc}") from exc

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": PLONE_AUTHORIZATION,
    }

    async with aiohttp.ClientSession() as http:
        async with http.get(
            f"{PLONE_URL}/resolveuid/{uuid}",
            headers=headers,
            allow_redirects=False,
        ) as resolved:
            if resolved.status != 301:
                raise RuntimeError(
                    f"Expected a redirect resolving {uuid}, got {resolved.status}."
                )
            url = resolved.headers["Location"]

        async with http.post(f"{url}/@workflow/{transition}", headers=headers) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Workflow transition {transition!r} on {url} failed: "
                    f"{response.status} {await response.text()}"
                )

    return ExternalTaskComplete(
        task=task,
        response=CompleteExternalTaskDto(workerId=task.workerId),
    )
