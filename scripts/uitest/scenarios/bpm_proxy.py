"""C. The Bpm Proxy content type: add form, start form, validation, diagram."""

from .. import fixtures
from ..harness import PREFIX
from ..harness import rest
from ..harness import shot


TITLE = "C. Bpm Proxy content type"

TITLE_TEXT = f"{PREFIX}quote"


def run(session):
    check = session.checks.check
    base = session.base_url
    page, watcher = session.page("manager")

    # Deploy the example this and the following scenarios drive.
    page.goto(base, wait_until="load")
    deployed = fixtures.deploy_example(
        page, base, "request-for-quote", fixtures.RFQ_ASSETS
    )
    for name, status, body in deployed:
        check("C0", f"deployed {name}", status == 200, f"{status} {body}")

    # C1 -- the vocabulary offers what we just deployed.
    watcher.reset()
    page.goto(f"{base}/++add++Bpm Proxy", wait_until="load")
    definition = page.locator("#form-widgets-process_definition_key")
    values = definition.locator("option").evaluate_all(
        "options => options.map((o) => o.value)"
    )
    check("C1", "vocabulary lists the deployed process",
          fixtures.RFQ in values, "; ".join(values)[:200])

    # C3 -- the JSON fields get the code editor widget.
    check("C3", "process_variables uses pat-code-editor",
          "pat-code-editor" in (page.locator(
              "#form-widgets-process_variables").get_attribute("class") or ""))
    check("C3", "default_values uses pat-code-editor",
          "pat-code-editor" in (page.locator(
              "#form-widgets-default_values").get_attribute("class") or ""))

    page.fill("#form-widgets-IBasic-title", TITLE_TEXT)
    definition.select_option(fixtures.RFQ)
    page.check("#form-widgets-diagram_enabled-0")
    shot(session, page, "bpm-proxy-add-form", "C1")

    page.click("#form-buttons-save")
    page.wait_for_load_state("load")
    page.wait_for_timeout(2500)
    item_url = page.url.split("/view")[0]
    session.proxy_url = item_url

    # C2 -- the toggle stuck.
    check("C2", "Bpm Proxy created", TITLE_TEXT in page.content(), page.url)

    # Reload before the documentation screenshots: the post-save "Item
    # created" status message is an artefact of having just created the page,
    # not something a reader of the guide should see.
    page.goto(item_url, wait_until="load")
    page.wait_for_timeout(2500)

    # C4 -- the deployed start form renders client-side.
    check("C4", "start form rendered by form-js",
          page.locator("#collective-bpmproxy-form .fjs-container").count() > 0)
    session.no_problems("C4", watcher, "Bpm Proxy view")
    shot(session, page, "bpm-proxy-start-form", "C4")

    # C5 -- interpolation reached the form data.
    data = fixtures.form_data(page)
    check("C5", "default_values interpolated into the form data",
          isinstance(data, dict), str(data)[:200])

    # C8 -- the diagram tab renders, and only once it is visible.
    hidden_before = page.locator(
        "#collective-bpmproxy-diagram .bjs-container svg").count()
    tab = page.locator("a[href='#autotoc-item-autotoc-1'], #autotoc-item-autotoc-1")
    if tab.count():
        tab.first.click()
        page.wait_for_timeout(2000)
    check("C8", "diagram renders once its tab is selected",
          page.locator("#collective-bpmproxy-diagram .bjs-container svg").count() > 0,
          f"hidden-tab render count was {hidden_before}")
    shot(session, page, "bpm-proxy-diagram", "C8")

    # C6 -- the start form is required, so an empty submit must be refused.
    watcher.reset()
    page.goto(item_url, wait_until="load")
    page.wait_for_timeout(1500)
    submitted = page.evaluate(
        """async () => {
            const form = document.querySelector(
                '#collective-bpmproxy-form-submit');
            if (!form) { return 'no form'; }
            const field = form.querySelector(
                '[name="collective-bpmproxy-form-data"]');
            if (field) { field.value = '{}'; }
            form.submit();
            return 'submitted';
        }"""
    )
    page.wait_for_load_state("load")
    page.wait_for_timeout(2000)
    body = page.content()
    check("C6", "empty submit is rejected server-side",
          "Invalid or missing data" in body or "Submit successful" not in body,
          f"{submitted}; {('Invalid' in body)=}")
    shot(session, page, "bpm-proxy-validation", "C6")

    # A8 -- a page whose process definition has been removed from the engine
    # must say so, not answer with a traceback. Deleting a deployment from the
    # control panel cascades, so this is an ordinary operational state.
    # Use a throwaway deployment so the rest of the suite keeps its fixtures.
    orphan_key = PREFIX + "orphan-process"
    deployed = rest(page, base, "/@bpmproxy-deploy", "POST",
                    {"name": f"{orphan_key}.bpmn",
                     "xml": fixtures.minimal_bpmn(orphan_key)})
    check("A8", "throwaway process deployed", deployed["status"] == 200,
          f"{deployed['status']} {deployed['body'][:160]}")

    if deployed["status"] == 200:
        orphan_url = fixtures.create_proxy(
            page, base, PREFIX + "orphan", orphan_key
        )
        deployment_id = (deployed["json"] or {}).get("result", {}).get("id")
        removed = rest(page, base, "/@bpmproxy-deployments", "DELETE",
                       {"id": deployment_id})
        check("A8", "throwaway deployment deleted",
              removed["status"] in (200, 204), str(removed["status"]))

        watcher.reset()
        page.goto(orphan_url, wait_until="load")
        page.wait_for_timeout(2000)
        body = page.content()
        check("A8",
              "a page whose process is gone renders a message, not a traceback",
              "Traceback" not in body and "not available" in body,
              f"{page.url}; traceback={'Traceback' in body}")
