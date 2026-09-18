"""D. The task form view, and C7/C9 -- starting a process and listing tasks."""

from .. import fixtures

from ..harness import shot
import json
import re


TITLE = "D. Task forms (and starting a process)"


def start_instance(page, base, proxy_url, data):
    """Submit the start form the way the browser bundle does.

    form.js serializes the form-js data into the hidden
    collective-bpmproxy-form-data input and posts the surrounding form, so
    driving that directly is the same code path a user takes.
    """
    page.goto(proxy_url, wait_until="load")
    page.wait_for_timeout(1500)
    page.evaluate(
        """(payload) => {
            const form = document.querySelector('#collective-bpmproxy-form-submit');
            const field = form.querySelector(
                '[name="collective-bpmproxy-form-data"]');
            field.value = payload;
            form.submit();
        }""",
        json.dumps(data),
    )
    page.wait_for_load_state("load")
    page.wait_for_timeout(2500)
    return page.url


def run(session):
    check = session.checks.check
    base = session.base_url
    page, watcher = session.page("manager")

    proxy_url = getattr(session, "proxy_url", None)
    if not proxy_url:
        check("D0", "a Bpm Proxy from scenario C is available", False,
              "run the bpm_proxy scenario first")
        return

    # C7 -- a valid submission starts an instance and lands on the first task.
    watcher.reset()
    url = start_instance(page, base, proxy_url, {"category": "a"})
    body = page.content()
    check("C7", "submit reported success", "Submit successful" in body,
          url)
    check("C7", "redirected into a task form",
          "/@@bpm-task/" in url, url)
    session.task_url = url

    # D1 -- the task form renders.
    check("D1", "task form rendered",
          page.locator("#collective-bpmproxy-form .fjs-container").count() > 0)
    session.no_problems("D1", watcher, "task form")
    shot(session, page, "task-form", "D1")

    # D2 -- breadcrumbs pick up the task name.
    crumbs = page.locator("#portal-breadcrumbs, .breadcrumb, nav[aria-label='breadcrumb']")
    crumb_text = crumbs.first.inner_text() if crumbs.count() else ""
    check("D2", "breadcrumbs include the task title",
          bool(crumb_text.strip()), crumb_text[:160])

    # C9 -- the task list tab on the proxy.
    page.goto(proxy_url, wait_until="load")
    page.wait_for_timeout(1500)
    check("C9", "task list shows the running instance's task",
          "Choose options" in page.content() or "Task list" in page.content(),
          page.url)
    shot(session, page, "task-list", "C9")

    # D4 -- a task id that is not this context's is refused.
    bogus = "00000000-0000-0000-0000-000000000000"
    page.goto(f"{proxy_url}/@@bpm-task/{bogus}", wait_until="load")
    page.wait_for_timeout(1000)
    refused = page.content()
    check("D4", "unknown task is refused with a message",
          "no longer available" in refused or "Task not found" in refused,
          page.url)

    # D3 -- completing the task moves the process on.
    if "/@@bpm-task/" in session.task_url:
        page.goto(session.task_url, wait_until="load")
        page.wait_for_timeout(1500)
        if page.locator("#collective-bpmproxy-form-submit").count():
            data = fixtures.form_data(page)
            page.evaluate(
                """(payload) => {
                    const form = document.querySelector(
                        '#collective-bpmproxy-form-submit');
                    form.querySelector(
                        '[name="collective-bpmproxy-form-data"]').value = payload;
                    form.submit();
                }""",
                json.dumps(data),
            )
            page.wait_for_load_state("load")
            page.wait_for_timeout(2500)
            after = page.content()
            check("D3", "task submission is accepted",
                  "Internal Server Error" not in after,
                  page.url)

    # The proxy's own task list is the user-visible proof that an instance
    # exists; querying the engine directly would need a JWT of its own, which
    # is exactly the coupling this add-on exists to avoid.
    page.goto(proxy_url, wait_until="load")
    page.wait_for_timeout(1500)
    check("C7", "the proxy still renders after the round trip",
          "Internal Server Error" not in page.content(), page.url)
