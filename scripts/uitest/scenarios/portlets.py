"""F. The context-filtered Tasks portlet."""

from ..harness import rest
from ..harness import shot


TITLE = "F. Portlets"
PROJECT = "/renovation-project-demo"


def run(session):
    check = session.checks.check
    base = session.base_url
    page, _watcher = session.page("manager")

    page.goto(base, wait_until="load")
    assigned = rest(page, base, PROJECT)
    if assigned["status"] != 200:
        check(
            "F0",
            "renovation-project-demo with its task portlet is available",
            False,
            str(assigned["status"]),
        )
        return

    page.goto(f"{base}{PROJECT}", wait_until="load")
    page.wait_for_timeout(500)
    column = page.locator("#portal-column-two, .portletColumn, aside")
    column_text = column.first.inner_text() if column.count() else ""
    check(
        "F1",
        "context-filtered task list portlet rendered on the case",
        "Case tasks" in column_text or "Case tasks" in page.content(),
        column_text[:200],
    )
    shot(session, page, "portlet-tasks", "F1")

    page.goto(f"{base}/@@redirect-to-bpm-task/does-not-exist", wait_until="load")
    page.wait_for_timeout(500)
    check(
        "F2",
        "redirect view handles an unknown task id gracefully",
        "Internal Server Error" not in page.content(),
        page.url,
    )
