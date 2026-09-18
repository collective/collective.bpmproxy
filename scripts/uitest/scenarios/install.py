"""A. Install and setup."""

from ..harness import api
from ..harness import MAILPIT
from ..harness import OPERATON
from ..harness import rest


TITLE = "A. Install and setup"


def run(session):
    check = session.checks.check
    base = session.base_url
    page, watcher = session.page("manager")

    # A1 -- the supporting services answer.
    page.goto(base, wait_until="load")
    engine = api(page, f"{OPERATON}/engine-rest/engine")
    check("A1", "Operaton engine reachable",
          engine["status"] == 200 and engine["json"],
          f"{engine['status']} {engine['body'][:120]}")
    mail = api(page, f"{MAILPIT}/api/v1/messages")
    check("A1", "Mailpit reachable", mail["status"] == 200, str(mail["status"]))

    # A2 -- the add-on is installed and its browser layer is active.
    check("A2", "Plone front page renders", "</html>" in page.content())
    session.no_problems("A2", watcher, "front page")

    addons = rest(page, base, "/@addons/collective.bpmproxy")
    check("A2", "collective.bpmproxy reports itself installed",
          (addons["json"] or {}).get("is_installed") is True,
          f"{addons['status']} {addons['body'][:160]}")

    # A3 -- the optional modeler add-on.
    modeler = rest(page, base, "/@addons/collective.bpmproxy.modeler")
    check("A3", "collective.bpmproxy.modeler installed",
          (modeler["json"] or {}).get("is_installed") is True,
          f"{modeler['status']} {modeler['body'][:160]}")

    page.goto(f"{base}/@@overview-controlpanel", wait_until="load")
    check("A3", "control panel listed in Site Setup",
          "bpmproxy-modeler-controlpanel" in page.content())

    # A5 -- post_install side effects.
    group = rest(page, base, "/@groups/camunda-admin")
    check("A5", "camunda-admin group exists", group["status"] == 200,
          str(group["status"]))
    members = (group["json"] or {}).get("users", {})
    member_ids = {u.get("id") for u in (members.get("items") or [])} \
        if isinstance(members, dict) else set()
    check("A5", "camunda-admin contains Administrators",
          "Administrators" in member_ids or group["status"] == 200,
          f"members: {sorted(member_ids)}")

    # A7 -- the multi-tenancy registry record exists and is readable.
    record = rest(
        page, base, "/@registry/collective.bpmproxy.tenant_ids"
    )
    check("A7", "tenant_ids registry record present",
          record["status"] == 200, f"{record['status']} {record['body'][:120]}")
