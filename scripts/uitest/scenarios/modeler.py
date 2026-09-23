"""B. The BPMN/DMN/Form modeler control panel and its REST services."""

from ..harness import rest
from ..harness import shot


TITLE = "B. Modeler control panel and deployment REST"

PROCESS_ID = "uitest-modeler-probe"

PROBE_BPMN = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
    xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
    xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
    id="Definitions_uitest" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="{PROCESS_ID}" name="UI test probe" isExecutable="true"
      camunda:historyTimeToLive="P1D">
    <bpmn:startEvent id="StartEvent_1" name="Start" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{PROCESS_ID}">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="152" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""


def run(session):
    check = session.checks.check
    base = session.base_url
    page, watcher = session.page("manager")

    # Fixed, not time-stamped: this name appears in the deployments
    # screenshot, and the sweep removes it between runs anyway.
    deployment_name = "uitest-modeler-demo.bpmn"
    dialogs = []

    def on_dialog(dialog):
        dialogs.append((dialog.type, dialog.message))
        dialog.accept(deployment_name) if dialog.type == "prompt" else dialog.accept()

    page.on("dialog", on_dialog)

    # The modeler bundle must not leak onto ordinary pages (L2).
    page.goto(base, wait_until="load")
    check(
        "L2", "modeler bundle stays off other pages", "modeler.js" not in page.content()
    )

    watcher.reset()
    page.goto(f"{base}/@@bpmproxy-modeler-controlpanel", wait_until="load")
    page.wait_for_timeout(2500)

    # B1 -- the BPMN modeler.
    check(
        "B1",
        "BPMN modeler booted",
        page.locator("#bpmn-modeler-container .bjs-container").count() > 0,
    )
    check(
        "B1",
        "properties panel booted",
        page.locator("#bpmn-properties-panel .bio-properties-panel").count() > 0,
    )
    check(
        "B1",
        "BPMN icon font loaded",
        page.evaluate(
            """async () => {
            // bpmn-font ships an EOT face Chromium cannot parse next to the
            // usable one, so a rejection here is not conclusive -- what
            // matters is that some 'bpmn' face ends up loaded.
            try { await document.fonts.load('1em bpmn'); } catch (err) {}
            return [...document.fonts].some(
                (f) => f.family === 'bpmn' && f.status === 'loaded');
        }"""
        ),
    )
    session.no_problems("B1", watcher, "control panel")
    shot(session, page, "controlpanel-bpmn", "B1")

    # B2 -- DMN.
    page.click("#dmn-tab")
    page.wait_for_timeout(1500)
    check(
        "B2",
        "DMN modeler booted",
        page.locator(
            "#dmn-modeler-container .dmn-decision-table-container, "
            "#dmn-modeler-container .dmn-drd-container, "
            "#dmn-modeler-container .djs-container"
        ).count()
        > 0,
    )
    shot(session, page, "controlpanel-dmn", "B2")

    # B3 -- the form playground.
    page.click("#form-tab")
    page.wait_for_timeout(1500)
    check(
        "B3",
        "form playground booted",
        page.locator(
            "#form-playground-container .fjs-container, "
            "#form-playground-container .cfp-playground"
        ).count()
        > 0,
    )
    shot(session, page, "controlpanel-form", "B3")

    # B4 -- deploy from the modeler UI.
    page.click("#bpmn-tab")
    page.wait_for_timeout(500)
    watcher.reset()
    dialogs.clear()
    page.click("#bpmn-deploy-btn")
    page.wait_for_timeout(3500)
    check(
        "B4",
        "deploy button reported success",
        any("success" in message.lower() for _, message in dialogs),
        "; ".join(f"{t}: {m}" for t, m in dialogs),
    )

    # B5 -- the deployment shows up without an explicit refresh.
    page.click("#deployments-tab")
    page.wait_for_timeout(2000)
    table = page.locator("#deployments-table tbody")
    check(
        "B5",
        "deployment listed without pressing Refresh",
        deployment_name in table.inner_text(),
        table.inner_text()[:200],
    )
    # The engine's deployment id and timestamp differ on every run; mask them
    # so the screenshot is byte-stable and reviewable as a diff.
    shot(
        session,
        page,
        "controlpanel-deployments",
        "B5",
        mask=[
            page.locator("#deployments-table tbody td:nth-child(1)"),
            page.locator("#deployments-table tbody td:nth-child(4)"),
        ],
    )

    # B6 -- deleting it cascades.
    row = page.locator("#deployments-table tbody tr", has_text=deployment_name)
    row.locator("button").click()
    page.wait_for_timeout(2500)
    check(
        "B6",
        "deployment deleted",
        deployment_name not in page.locator("#deployments-table tbody").inner_text(),
    )

    # B4 again, this time through the service directly, to prove the Accept
    # header requirement is the only thing standing between 404 and 200.
    direct = rest(
        page,
        base,
        "/@bpmproxy-deploy",
        "POST",
        {"name": f"{PROCESS_ID}.bpmn", "xml": PROBE_BPMN},
    )
    check(
        "B4",
        "deploy service accepts a POST",
        direct["status"] == 200,
        f"{direct['status']} {direct['body'][:160]}",
    )

    no_accept = page.evaluate(
        """async (url) => {
            const res = await fetch(url + '/@bpmproxy-deploy', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: 'x.bpmn', xml: '<bpmn/>'}),
            });
            return res.status;
        }""",
        base,
    )
    check(
        "B4",
        "deploy service is not routed without an Accept header",
        no_accept == 404,
        str(no_accept),
    )

    # B7 -- a Site Administrator outside camunda-admin gets nothing.
    editor = session.context("editor")
    response = editor.request.get(
        f"{base}/@bpmproxy-deployments", headers={"Accept": "application/json"}
    )
    check(
        "B7",
        "deployments endpoint refused to a Site Administrator",
        response.status in (401, 403),
        str(response.status),
    )
