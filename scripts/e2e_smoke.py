"""End-to-end smoke test for the Plone Classic frontend and the deployment API.

Drives a real browser against a running Plone and a running Operaton, and
checks the things only a page load can check: that the bundles parse and boot,
that the BPMN icon font is there, and that deploying, listing and deleting a
process from the control panel actually works.

    make services       # Operaton (and friends) on :8081
    make start          # Plone on :8080
    make bootstrap-site # once, with Plone stopped
    make e2e

Needs playwright (provided by devenv, see devenv.nix).
"""

from playwright.sync_api import sync_playwright
import argparse
import base64
import json
import pathlib
import sys
import time


PROCESS_ID = "bpmproxy-smoke"
FORM_ID = "bpmproxy-smoke-start"

SMOKE_BPMN = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
    xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
    xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
    xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
    id="Definitions_smoke" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="{PROCESS_ID}" name="BPM Proxy smoke test" isExecutable="true"
      camunda:historyTimeToLive="P1D">
    <bpmn:startEvent id="StartEvent_1" name="Start"
        camunda:formRef="{FORM_ID}" camunda:formRefBinding="latest" camunda:initiator="author">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:userTask id="Task_1" name="Review">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:userTask>
    <bpmn:endEvent id="EndEvent_1" name="Done">
      <bpmn:incoming>Flow_2</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="EndEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{PROCESS_ID}">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="152" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_1_di" bpmnElement="Task_1">
        <dc:Bounds x="240" y="80" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="EndEvent_1_di" bpmnElement="EndEvent_1">
        <dc:Bounds x="392" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="Flow_1_di" bpmnElement="Flow_1">
        <di:waypoint x="188" y="120" />
        <di:waypoint x="240" y="120" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_2_di" bpmnElement="Flow_2">
        <di:waypoint x="340" y="120" />
        <di:waypoint x="392" y="120" />
      </bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""

SMOKE_FORM = json.dumps(
    {
        "type": "default",
        "id": FORM_ID,
        "executionPlatform": "Camunda Platform",
        "executionPlatformVersion": "7.17.0",
        "schemaVersion": 4,
        "components": [
            {"text": "# Smoke test", "type": "text", "id": "Field_intro"},
            {
                "label": "Your name",
                "type": "textfield",
                "id": "Field_name",
                "key": "name",
            },
        ],
    }
)


def basic_auth(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


class Checks:
    """Collects results so one failure does not hide the rest."""

    def __init__(self):
        self.results = []

    def check(self, name, condition, detail=""):
        self.results.append((bool(condition), name, detail))
        print(
            f"{'PASS' if condition else 'FAIL'}  {name}{f' -- {detail}' if detail else ''}"
        )
        return bool(condition)

    @property
    def failed(self):
        return [r for r in self.results if not r[0]]


class PageWatcher:
    """Console errors and uncaught exceptions, per page."""

    def __init__(self, page):
        self.errors = []
        self.warnings = []
        self.failed_requests = []
        self.http_errors = []
        page.on("console", self._on_console)
        page.on("pageerror", lambda exc: self.errors.append(f"pageerror: {exc}"))
        page.on(
            "requestfailed",
            lambda req: self.failed_requests.append(f"{req.url} {req.failure}"),
        )
        page.on(
            "response",
            lambda res: (
                self.http_errors.append(f"{res.status} {res.url}")
                if res.status >= 400
                else None
            ),
        )

    def _on_console(self, msg):
        if msg.type == "error":
            self.errors.append(f"console.error: {msg.text}")
        elif msg.type == "warning":
            self.warnings.append(msg.text)

    def reset(self):
        self.errors.clear()
        self.warnings.clear()
        self.failed_requests.clear()
        self.http_errors.clear()


def deploy(page, base_url, name, content):
    """Deploy through the REST service from within the authenticated page."""
    return page.evaluate(
        """async ({url, name, content}) => {
            const res = await fetch(url + '/@bpmproxy-deploy', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify({name: name, xml: content}),
            });
            return {status: res.status, body: await res.text()};
        }""",
        {"url": base_url, "name": name, "content": content},
    )


def run(base_url, screenshots, headed):
    shots = pathlib.Path(screenshots)
    shots.mkdir(parents=True, exist_ok=True)
    checks = Checks()
    deployment_name = f"smoke-{int(time.time())}.bpmn"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headed,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 1000},
            # A site manager in the "camunda-admin" group: the Zope root user
            # can open the control panel but its JWT carries no engine rights.
            extra_http_headers={"Authorization": basic_auth("manager", "manager")},
        )
        page = context.new_page()
        watcher = PageWatcher(page)

        dialogs = []

        def on_dialog(dialog):
            dialogs.append((dialog.type, dialog.message))
            if dialog.type == "prompt":
                dialog.accept(deployment_name)
            else:
                dialog.accept()

        page.on("dialog", on_dialog)

        # --- the site root renders (breadcrumbs on the navigation root) ------
        page.goto(base_url, wait_until="load")
        checks.check("front page renders", "</html>" in page.content())
        checks.check(
            "front page has no errors", not watcher.errors, "; ".join(watcher.errors)
        )
        checks.check(
            "front page served no 4xx/5xx resources",
            not watcher.http_errors,
            "; ".join(watcher.http_errors),
        )
        checks.check(
            "modeler bundle stays off other pages",
            "modeler.js" not in page.content(),
        )

        # --- the control panel boots ----------------------------------------
        watcher.reset()
        page.goto(f"{base_url}/@@bpmproxy-modeler-controlpanel", wait_until="load")
        page.wait_for_timeout(1500)
        checks.check(
            "control panel loads without console errors",
            not watcher.errors,
            "; ".join(watcher.errors),
        )
        checks.check(
            "control panel has no failed requests",
            not watcher.failed_requests,
            "; ".join(watcher.failed_requests),
        )
        checks.check(
            "BPMN modeler booted",
            page.locator("#bpmn-modeler-container .bjs-container").count() > 0,
        )
        checks.check(
            "properties panel booted",
            page.locator("#bpmn-properties-panel .bio-properties-panel").count() > 0,
        )
        checks.check(
            "BPMN icon font loaded",
            page.evaluate(
                """async () => {
                    // bpmn-font ships an EOT face Chromium cannot parse next to
                    // the usable one, so a rejection here is not conclusive --
                    // what matters is that some 'bpmn' face ends up loaded.
                    try {
                        await document.fonts.load('1em bpmn');
                    } catch (err) {}
                    return [...document.fonts].some(
                        (f) => f.family === 'bpmn' && f.status === 'loaded');
                }"""
            ),
        )
        checks.check(
            "control panel served no 4xx/5xx resources",
            not watcher.http_errors,
            "; ".join(watcher.http_errors),
        )
        font_warnings = [
            w for w in watcher.warnings if "font" in w.lower() or "OTS parsing" in w
        ]
        checks.check(
            "no undecodable fonts",
            not font_warnings,
            "; ".join(w[:80] for w in font_warnings)
            or f"{len(watcher.warnings)} console warnings seen, none about fonts",
        )
        page.screenshot(path=str(shots / "controlpanel-bpmn.png"))

        page.click("#dmn-tab")
        page.wait_for_timeout(1000)
        checks.check(
            "DMN modeler booted",
            page.locator(
                "#dmn-modeler-container .dmn-decision-table-container, "
                "#dmn-modeler-container .dmn-drd-container, "
                "#dmn-modeler-container .djs-container"
            ).count()
            > 0,
        )
        page.screenshot(path=str(shots / "controlpanel-dmn.png"))

        page.click("#form-tab")
        page.wait_for_timeout(1000)
        checks.check(
            "form playground booted",
            page.locator(
                "#form-playground-container .fjs-container, "
                "#form-playground-container .cfp-playground"
            ).count()
            > 0,
        )
        page.screenshot(path=str(shots / "controlpanel-form.png"))

        # --- deploy from the modeler, then list and delete -------------------
        page.click("#bpmn-tab")
        page.wait_for_timeout(500)
        watcher.reset()
        dialogs.clear()
        page.click("#bpmn-deploy-btn")
        page.wait_for_timeout(3000)
        checks.check(
            "deploy button reported success",
            any("success" in message.lower() for _, message in dialogs),
            "; ".join(f"{t}: {m}" for t, m in dialogs),
        )

        page.click("#deployments-tab")
        page.wait_for_timeout(1500)
        table = page.locator("#deployments-table tbody")
        checks.check(
            "deployment listed without pressing Refresh",
            deployment_name in table.inner_text(),
            table.inner_text()[:200],
        )
        page.screenshot(path=str(shots / "controlpanel-deployments.png"))

        row = page.locator("#deployments-table tbody tr", has_text=deployment_name)
        row.locator("button").click()
        page.wait_for_timeout(2000)
        checks.check(
            "deployment deleted",
            deployment_name
            not in page.locator("#deployments-table tbody").inner_text(),
        )

        # --- a real process, rendered on a content item ----------------------
        form_result = deploy(page, base_url, f"{FORM_ID}.form", SMOKE_FORM)
        bpmn_result = deploy(page, base_url, f"{PROCESS_ID}.bpmn", SMOKE_BPMN)
        checks.check(
            "smoke form deployed",
            form_result["status"] == 200,
            f"{form_result['status']} {form_result['body'][:160]}",
        )
        checks.check(
            "smoke process deployed",
            bpmn_result["status"] == 200,
            f"{bpmn_result['status']} {bpmn_result['body'][:160]}",
        )

        watcher.reset()
        page.goto(f"{base_url}/++add++Bpm Proxy", wait_until="load")
        page.fill("#form-widgets-IBasic-title", "Smoke proxy")
        definition = page.locator("#form-widgets-process_definition_key")
        values = definition.locator("option").evaluate_all(
            "options => options.map((o) => o.value)"
        )
        checks.check(
            "process definition vocabulary lists the deployed process",
            PROCESS_ID in values,
            "; ".join(values)[:200],
        )
        definition.select_option(PROCESS_ID)
        page.check("#form-widgets-diagram_enabled-0")
        page.click("#form-buttons-save")
        page.wait_for_load_state("load")
        page.wait_for_timeout(2000)

        checks.check(
            "Bpm Proxy view has no console errors",
            not watcher.errors,
            "; ".join(watcher.errors),
        )
        checks.check(
            "start form rendered",
            page.locator("#collective-bpmproxy-form .fjs-container").count() > 0,
        )
        checks.check(
            "diagram rendered",
            page.locator("#collective-bpmproxy-diagram .bjs-container svg").count() > 0,
        )
        page.screenshot(path=str(shots / "bpm-proxy-view.png"), full_page=True)

        # --- leave the site as we found it -----------------------------------
        item_url = page.url.split("/view")[0]
        cleanup = page.evaluate(
            """async ({item, url}) => {
                const json = {'Accept': 'application/json',
                              'Content-Type': 'application/json'};
                const removed = [];
                const item_res = await fetch(item, {method: 'DELETE', headers: json});
                removed.push(['item', item_res.status]);
                const list = await (await fetch(url + '/@bpmproxy-deployments',
                                                {headers: json})).json();
                for (const d of list) {
                    const res = await fetch(url + '/@bpmproxy-deployments', {
                        method: 'DELETE', headers: json,
                        body: JSON.stringify({id: d.id}),
                    });
                    removed.push([d.name, res.status]);
                }
                return removed;
            }""",
            {"item": item_url, "url": base_url},
        )
        checks.check(
            "cleaned up",
            all(status in (200, 204) for _, status in cleanup),
            "; ".join(f"{name}:{status}" for name, status in cleanup),
        )

        # --- the deployment endpoints are for managers only ------------------
        editor = browser.new_context(
            extra_http_headers={"Authorization": basic_auth("editor", "editor")}
        )
        response = editor.request.get(
            f"{base_url}/@bpmproxy-deployments",
            headers={"Accept": "application/json"},
        )
        checks.check(
            "deployments endpoint refused to a Site Administrator",
            response.status in (401, 403),
            str(response.status),
        )
        editor.close()

        browser.close()

    print()
    if checks.failed:
        print(f"{len(checks.failed)} check(s) failed")
        return 1
    print(f"all {len(checks.results)} checks passed; screenshots in {shots}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080/Plone")
    parser.add_argument("--screenshots", default="var/e2e")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    sys.exit(run(args.url.rstrip("/"), args.screenshots, args.headed))
