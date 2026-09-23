"""Smoke-test the renovation case and its event subprocesses.

The fixture must be prepared as described in
``docs/renovation-project-scenario.md``: deploy the BPMN, apply the profile
after deployment, and start Plone. No external worker is needed for this
scenario because the case workflow is advanced directly by the manager.
"""

from playwright.sync_api import sync_playwright
import base64
import time


BASE = "http://localhost:8080/Plone"
CASE = f"{BASE}/renovation-project-demo"


def basic_auth(username, password):
    value = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {value}"


def wait_for_task(page, name, timeout_ms=60000):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        page.reload(wait_until="load")
        link = page.locator("a:visible").filter(has_text=name)
        if link.count():
            return link.first
        page.wait_for_timeout(1000)
    raise AssertionError(f"Task {name!r} did not appear")


def add_document(page, title, body):
    page.goto(CASE, wait_until="load")
    page.get_by_role("link", name="Add new…").click()
    page.get_by_role("link", name="Page", exact=True).click()
    page.locator("#form-widgets-IDublinCore-title").fill(title)
    page.frame_locator("iframe").locator("body").first.fill(body)
    page.get_by_role("button", name="Save").click()
    page.wait_for_load_state("load")


def complete_review(username, password, task_name, submit_label):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            extra_http_headers={"Authorization": basic_auth(username, password)}
        )
        page = context.new_page()
        page.goto(CASE, wait_until="load")
        task = wait_for_task(page, task_name)
        task.click()
        page.wait_for_load_state("load")
        page.get_by_label("Approved").check()
        page.get_by_role("button", name=submit_label).click()
        page.wait_for_load_state("load")
        context.close()
        browser.close()


def workflow(page, action):
    response = page.request.post(
        f"{CASE}/@workflow/{action}",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        data="{}",
    )
    assert response.status == 200, response.text()


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        manager = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("manager", "manager")}
        )
        manager_page = manager.new_page()
        manager_page.goto(CASE, wait_until="load")

        contractor = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("contractor", "contractor")}
        )
        contractor_page = contractor.new_page()
        add_document(
            contractor_page,
            "Initial renovation document",
            "The case document requires independent owner and inspector review.",
        )
        contractor.close()

        complete_review("owner", "owner", "Owner reviews page", "Submit review")
        complete_review(
            "inspector", "inspector", "Inspector reviews page", "Submit review"
        )
        workflow(manager_page, "close-case")

        manager_page.reload(wait_until="load")
        assert "Closed" in manager_page.locator("body").inner_text()
        manager.close()
        browser.close()
    print("Renovation case smoke test completed")


if __name__ == "__main__":
    main()
