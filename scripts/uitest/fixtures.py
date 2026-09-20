"""Deploying example processes and creating/removing the content under test.

Nothing here mutates the checked-in examples/ assets: the request-for-quote
transforms are applied to the deployed copy only, so the originals stay
suitable for a Camunda installation that has the scripting engine and mail
connector this local Operaton fixture does not.
"""

from .harness import PREFIX
from .harness import rest
from .harness import title_field
from .harness import widget
from .harness import widget_selector
import json
import pathlib
import re


EXAMPLES = pathlib.Path("examples")

# examples/request-for-quote, the richest example: start form, a DMN business
# rule task, a candidate-group review task and a gateway.
RFQ = "example-request-for-quote"
RFQ_ASSETS = [
    "request-for-quote-options.dmn",
    "request-for-quote-options.form",
    "request-for-quote-review.form",
    "request-for-quote-start.form",
    "request-for-quote-thanks.form",
    "request-for-quote.bpmn",
]

# examples/published-lifecycle: a signal start event, the only way to exercise
# the content-rule integration.
LIFECYCLE = "example-plone-published-lifecycle"

# examples/renovation-project: three chained processes correlated by the
# project's UUID, signal/message-started -- see docs/renovation-project-
# scenario.md. Used by the portlets scenario as its live fixture: the demo
# project it creates carries the Tasks and Message portlets.
RENOVATION_PROJECT = "renovation-project"
RENOVATION_PROJECT_ASSETS = [
    "renovation-owner-approval.form",
    "renovation-inspector-approval.form",
    "renovation-extra-work-approval.form",
    "renovation-confirm.form",
    "renovation-plan-review.bpmn",
    "renovation-work-and-extra-work.bpmn",
    "renovation-final-review.bpmn",
]


def minimal_bpmn(key):
    """The smallest deployable process: one start event, nothing else."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
    xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
    xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
    id="Definitions_{key}" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="{key}" name="{key}" isExecutable="true"
      camunda:historyTimeToLive="P1D">
    <bpmn:startEvent id="StartEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{key}">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="152" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""


LIFECYCLE_ASSETS = [
    "example-published-lifecycle-share.form",
    "example-published-lifecycle-update.form",
    "example-published-lifecycle.bpmn",
]


def adapt_request_for_quote(xml):
    """Make the checked-in example runnable on the local Operaton fixture.

    Three runtime-only substitutions, the same ones
    scripts/e2e_request_for_quote.py applies and docs/AGENTS.md explains:

    1. "Site Administrators" -> "Administrators", the group bootstrap_site.py
       actually creates.
    2. The Python inputParameter building optionsChosenString is dropped and
       ${options} used directly -- the fixture installs no scripting engine.
    3. The mail connector on the accepted branch is removed and its sendTask
       becomes a plain task -- the fixture configures no connector, and leaving
       it in place rolls back reviewer completion.
    """
    xml = xml.replace(
        'camunda:candidateGroups="Site Administrators"',
        'camunda:candidateGroups="Administrators"',
    )
    xml = re.sub(
        r"<camunda:inputOutput>.*?</camunda:inputOutput>",
        "",
        xml,
        flags=re.DOTALL,
    )
    xml = xml.replace("${optionsChosenString}", "${options}")
    xml = re.sub(
        r'<bpmn:sendTask([^>]*id="Activity_1njb1hw"[^>]*)>.*?</bpmn:sendTask>',
        r"<bpmn:task\1></bpmn:task>",
        xml,
        flags=re.DOTALL,
    )
    return xml


def ensure_history_ttl(xml):
    """Operaton refuses definitions without a history time to live.

    The request-for-quote example predates that requirement and carries none.
    """
    if "historyTimeToLive" in xml:
        return xml
    return re.sub(
        r"(<bpmn:process\b[^>]*?)(\s+isExecutable=)",
        r'\1 camunda:historyTimeToLive="P1D"\2',
        xml,
        count=1,
    )


TRANSFORMS = {
    "request-for-quote.bpmn": lambda xml: ensure_history_ttl(
        adapt_request_for_quote(xml)
    ),
}


def deploy_example(page, base_url, example, assets):
    """Deploy one example directory's assets; returns [(name, status), ...]."""
    results = []
    for asset in assets:
        content = (EXAMPLES / example / asset).read_text()
        transform = TRANSFORMS.get(asset)
        if transform:
            content = transform(content)
        result = rest(
            page,
            base_url,
            "/@bpmproxy-deploy",
            "POST",
            {"name": asset, "xml": content},
        )
        results.append((asset, result["status"], result["body"][:200]))
    return results


class EngineUnavailable(RuntimeError):
    """The deployments service could not reach the process engine."""


def list_deployments(page, base_url):
    """Deployments known to the engine.

    The service answers 500 with {"error": ...} when the engine is down (most
    often: its database went away). Surfacing that as a named error keeps an
    infrastructure outage from looking like a product failure three scenarios
    later.
    """
    result = rest(page, base_url, "/@bpmproxy-deployments")
    if result["status"] != 200 or not isinstance(result["json"], list):
        raise EngineUnavailable(
            f"GET @bpmproxy-deployments returned {result['status']}: "
            f"{result['body'][:300]}"
        )
    return result["json"]


def sweep(page, base_url):
    """Remove everything a previous run may have left behind.

    Runs on entry as well as exit so a crashed run cannot poison the next one.
    """
    removed = {"content": [], "deployments": []}

    search = rest(
        page,
        base_url,
        f"/@search?SearchableText={PREFIX}&metadata_fields=_all&b_size=200",
    )
    for item in (search["json"] or {}).get("items", []):
        if PREFIX in item.get("id", "") or item.get("title", "").startswith(PREFIX):
            # item["@id"] is already absolute, so it needs no base.
            res = rest(page, "", item["@id"], "DELETE")
            removed["content"].append((item["@id"], res["status"]))

    for deployment in list_deployments(page, base_url):
        res = rest(
            page,
            base_url,
            "/@bpmproxy-deployments",
            "DELETE",
            {"id": deployment["id"]},
        )
        removed["deployments"].append((deployment.get("name"), res["status"]))

    return removed


def create_proxy(
    page,
    base_url,
    title,
    definition_key,
    diagram=False,
    attachments=False,
    portal_type="Bpm Proxy",
):
    """Create a Bpm Proxy (or behavior-enabled type) through its add form."""
    page.goto(f"{base_url}/++add++{portal_type}", wait_until="load")
    page.wait_for_timeout(500)
    field = title_field(page)
    if field is None:
        raise RuntimeError(
            f"no title field on the {portal_type} add form at {page.url}"
        )
    field.fill(title)
    widget(page, "process_definition_key").select_option(definition_key)
    if diagram:
        page.check(widget_selector(page, "diagram_enabled") + "-0")
    if attachments:
        page.check(widget_selector(page, "attachments_enabled") + "-0")
    page.click("#form-buttons-save")
    page.wait_for_load_state("load")
    return page.url.split("/view")[0]


def publish(page, url):
    """Put an item into the published state so anonymous users can reach it.

    Uses the REST workflow endpoint rather than content_status_modify: the
    latter is a CSRF-protected write, so driving it by URL earns a 403 from
    plone.protect rather than a transition.
    """
    result = rest(page, "", f"{url}/@workflow/publish", "POST", {})
    return result["status"] in (200, 201)


def form_data(page):
    """The JSON the form-js viewer will submit, as currently filled in."""
    raw = page.locator("#collective-bpmproxy-form").get_attribute("data-data")
    return json.loads(raw or "{}")


def install_profile(page, base_url, profile_id):
    """Install a secondary GenericSetup profile through portal_setup.

    This is the route the profile READMEs tell site administrators to take
    (plone.restapi's @addons only installs a package's default profile), so
    testing it here also tests the documented instructions.

    It has to be the *Import* tab (manage_fullImport -> manage_importAllSteps),
    not the per-step tab: only runAllImportStepsFromProfile runs the profile's
    post_handler, and for a demo profile that handler is what creates the demo
    content. Importing selected steps registers the type and leaves the demo
    missing, which looks exactly like a broken profile.
    """
    page.goto(f"{base_url}/portal_setup/manage_fullImport", wait_until="load")
    page.select_option("select[name='context_id']", f"profile-{profile_id}")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1000)
    page.click("input[name='manage_importAllSteps:method']")
    page.wait_for_load_state("load")
    page.wait_for_timeout(3000)
    return "step" in page.content().lower()
