"""Deploying example processes and creating/removing the content under test.

Handles example deployment, site content setup, and cleanup for uitest scenarios.
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

# examples/contact-form: start form, candidate-group review & triage,
# delegation, abandon route, and external email service task.
CONTACT_FORM = "example-contact-form"
CONTACT_FORM_ASSETS = [
    "contact-form-start.form",
    "contact-form-review.form",
    "contact-form-delegated.form",
    "contact-form.bpmn",
]

# examples/published-lifecycle: a signal start event, the only way to exercise
# the content-rule integration.
LIFECYCLE = "example-plone-published-lifecycle"


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


def ensure_history_ttl(xml):
    """Operaton refuses definitions without a history time to live."""
    if "historyTimeToLive" in xml:
        return xml
    return re.sub(
        r"(<bpmn:process\b[^>]*?)(\s+isExecutable=)",
        r'\1 camunda:historyTimeToLive="P1D"\2',
        xml,
        count=1,
    )


TRANSFORMS = {}


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
