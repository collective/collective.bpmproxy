"""Capture the Plone BPMN, DMN, form, and deployment modeler views.

Prerequisites:

* Plone must be running at the configured URL.
* Operaton must be running and the example resources must be deployed.
* The Plone user must be allowed to open the modeler control panel.

Run from the repository root with the browser skill wrapper::

    playwright-python scripts/capture_modeler_screenshots.py

The default login is ``admin`` / ``admin``. Override it without editing the
script using ``PLONE_ADMIN_USER`` and ``PLONE_ADMIN_PASSWORD``. Use
``PLONE_MODELER_URL`` when Plone is served at a different URL.

The script writes ``plone-modeler-bpmn.png``, ``plone-modeler-dmn.png``,
``plone-modeler-form.png``, and ``plone-modeler-deployments.png`` to the
repository root. BPMN and form captures load the matching example resources
from the deployment table when those resources are available.
"""

from pathlib import Path
import os

from playwright.sync_api import sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLONE_URL = os.environ.get(
    "PLONE_MODELER_URL",
    "http://127.0.0.1:8080/Plone/@@bpmproxy-modeler-controlpanel",
)
PLONE_USER = os.environ.get("PLONE_ADMIN_USER", "admin")
PLONE_PASSWORD = os.environ.get("PLONE_ADMIN_PASSWORD", "admin")


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000},
            device_scale_factor=1,
        )
        page.goto(PLONE_URL, wait_until="networkidle")

        if page.locator("#__ac_name").count():
            page.locator("#__ac_name").fill(PLONE_USER)
            page.locator("#__ac_password").fill(PLONE_PASSWORD)
            page.locator("#buttons-login").click()
            page.wait_for_load_state("networkidle")
            page.goto(PLONE_URL, wait_until="networkidle")

        page.wait_for_timeout(3000)
        page.locator("#deployments-tab").click()
        page.wait_for_timeout(1000)

        bpmn_load = page.locator(
            "button", has_text="Load contact-form.bpmn"
        ).first
        if bpmn_load.count():
            bpmn_load.click()
            page.wait_for_timeout(1500)
        page.locator("#bpmn-tab").click()
        page.wait_for_timeout(500)
        page.screenshot(
            path=PROJECT_ROOT / "plone-modeler-bpmn.png",
            full_page=True,
        )

        page.locator("#dmn-tab").click()
        page.wait_for_timeout(500)
        page.screenshot(
            path=PROJECT_ROOT / "plone-modeler-dmn.png",
            full_page=True,
        )

        page.locator("#deployments-tab").click()
        page.wait_for_timeout(800)
        form_load = page.locator(
            "button", has_text="Load review-decision.form"
        ).first
        if form_load.count():
            form_load.click()
            page.wait_for_timeout(1500)
        page.locator("#form-tab").click()
        page.wait_for_timeout(500)
        page.screenshot(
            path=PROJECT_ROOT / "plone-modeler-form.png",
            full_page=True,
        )

        page.locator("#deployments-tab").click()
        page.wait_for_timeout(500)
        page.screenshot(
            path=PROJECT_ROOT / "plone-modeler-deployments.png",
            full_page=True,
        )
        browser.close()


if __name__ == "__main__":
    main()
