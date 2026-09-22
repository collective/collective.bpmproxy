"""F. The Task list and Message dispatch portlets.

The renovation_demo profile assigns one of each to its demo project, which
is exactly the configuration the documentation recommends (a context-
filtered task list next to a message-dispatch button), so this exercises
the shipped assignment rather than one invented for the test.

renovation-project-demo is a plain Dexterity Container with no BpmProxy
behavior at all (see renovation_demo.py) -- part of what this scenario
proves is that both portlets work on ordinary content, needing nothing but
plone.uuid.
"""

from .. import fixtures
from ..harness import rest
from ..harness import shot

TITLE = "F. Portlets"

PROFILE = "collective.bpmproxy:renovation_demo"
PROJECT = "/renovation-project-demo"


def run(session):
    check = session.checks.check
    base = session.base_url
    page, watcher = session.page("manager")

    # renovation-project-demo is workflow-driven, and renovation_demo.
    # install() returns early once an object with that id already exists --
    # so a rerun that finds it already past drafting_plan (its own earlier
    # run, or a stale one from a previous session) can never be fast-
    # forwarded, only reset. Delete it first, unconditionally, so this
    # scenario is deterministic no matter how many times it has run before
    # (it isn't "uitest-" prefixed, so fixtures.sweep() never touches it).
    page.goto(base, wait_until="load")
    existing = rest(page, base, PROJECT)
    if existing["status"] == 200:
        rest(page, "", f"{base}{PROJECT}", "DELETE")

    fixtures.install_profile(page, base, PROFILE)
    fixtures.deploy_example(
        page, base, fixtures.RENOVATION_PROJECT, fixtures.RENOVATION_PROJECT_ASSETS
    )

    assigned = rest(page, base, PROJECT)
    if assigned["status"] != 200:
        check(
            "F0",
            "renovation-project-demo with its portlets is available",
            False,
            str(assigned["status"]),
        )
        return

    # The Tasks portlet hides itself when the list is empty, so put the
    # freshly (re)created project into plan_review first -- which is also
    # what makes the use_context filter meaningful (the Owner/Inspector
    # review tasks the signal-started Plan Review process creates on
    # submit).
    watcher.reset()
    result = rest(page, base, f"{PROJECT}/@workflow/submit-plan", "POST", {})
    check(
        "F1",
        "submit-plan starts the Plan Review process",
        result["status"] == 200,
        f"{result['status']} {result['body'][:200]}",
    )
    page.wait_for_timeout(1500)

    page.goto(f"{base}{PROJECT}", wait_until="load")
    page.wait_for_timeout(1500)
    column = page.locator("#portal-column-two, .portletColumn, aside")
    column_text = column.first.inner_text() if column.count() else ""

    # F2 -- the task list portlet, restricted to this context.
    check(
        "F2",
        "task list portlet rendered on the project",
        "Project tasks" in column_text or "Project tasks" in page.content(),
        column_text[:200],
    )
    shot(session, page, "portlet-tasks", "F2")

    # The extra-work message is only valid while the Work & Extra-Work
    # process is active, which starts in the in_progress Plone state.
    check(
        "F3",
        "extra-work message is hidden during plan review",
        "Request extra work" not in column_text
        and "Request extra work" not in page.content(),
        column_text[:200],
    )
    shot(session, page, "portlet-message-hidden", "F3")

    # Use the manager shortcut to advance the fixture into the work phase.
    # The full renovation scenario exercises both review tasks; this focused
    # portlet scenario only needs the normal workflow transition that starts
    # the correlated Work & Extra-Work process.
    watcher.reset()
    result = rest(page, base, f"{PROJECT}/@workflow/approve-plan", "POST", {})
    check(
        "F4",
        "approve-plan starts the work phase",
        result["status"] == 200,
        f"{result['status']} {result['body'][:200]}",
    )
    page.wait_for_timeout(1500)

    page.goto(f"{base}{PROJECT}", wait_until="load")
    page.wait_for_timeout(1500)
    column = page.locator("#portal-column-two, .portletColumn, aside")
    column_text = column.first.inner_text() if column.count() else ""

    check(
        "F5",
        "message portlet rendered during work in progress",
        "Request extra work" in column_text or "Request extra work" in page.content(),
        column_text[:200],
    )
    shot(session, page, "portlet-message", "F5")

    # F5 -- dispatching the message must not error while the Work & Extra-Work
    # instance is running to correlate to.
    watcher.reset()
    button = page.locator(
        "#portal-column-two button, #portal-column-two input[type=submit], "
        "aside button, aside input[type=submit]"
    )
    fired = False
    for index in range(button.count()):
        candidate = button.nth(index)
        label = candidate.get_attribute("value") or candidate.inner_text() or ""
        if "extra work" in label.lower():
            candidate.click()
            page.wait_for_load_state("load")
            page.wait_for_timeout(2000)
            fired = True
            break
    if fired:
        check(
            "F6",
            "dispatching the message does not error",
            "Internal Server Error" not in page.content(),
            page.url,
        )
    else:
        check(
            "F6",
            "message button found to click",
            False,
            f"{button.count()} candidate control(s) in the column",
        )

    # F7 -- the portlet's task links go through the redirect view.
    page.goto(f"{base}/@@redirect-to-bpm-task/does-not-exist", wait_until="load")
    page.wait_for_timeout(1000)
    check(
        "F7",
        "redirect view handles an unknown task id gracefully",
        "Internal Server Error" not in page.content(),
        page.url,
    )
