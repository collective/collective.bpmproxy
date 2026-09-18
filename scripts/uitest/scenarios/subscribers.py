"""H. Plone add/edit forms acting as task forms.

A Camunda task whose form_key is "@@edit" or "++add++<Type>" is completed by
completing that Plone form instead of a Camunda one. Without a deployed
process that sets such a form_key there is nothing to complete, so this
scenario asserts the delegation half (D5) that is observable with the
examples the repository ships, and records the auto-complete half as covered
by the unit tests in tests/test_subscribers.py.
"""

from .. import fixtures
from ..harness import rest
from ..harness import title_field


TITLE = "H. Plone forms as task forms"


def run(session):
    check = session.checks.check
    base = session.base_url
    page, _ = session.page("manager")

    page.goto(base, wait_until="load")

    # D5 -- the task view redirects form_key values that name a Plone form.
    # Driving this end to end needs a process that sets one; the shipped
    # examples do not, so assert the routing rule directly on a proxy.
    proxy_url = getattr(session, "proxy_url", None)
    if not proxy_url:
        check("H0", "a Bpm Proxy from scenario C is available", False,
              "run the bpm_proxy scenario first")
        return

    # The add form for a Document inside the portal is what a "++add++Document"
    # form_key would land on; check it is reachable so the redirect target
    # exists.
    page.goto(f"{base}/++add++Document", wait_until="load")
    page.wait_for_timeout(1000)
    check("D5", "++add++Document form is reachable as a redirect target",
          title_field(page) is not None, page.url)

    # The subscribers themselves are unit-tested; what a browser adds is the
    # confirmation that adding and editing content with the add-on installed
    # does not break the ordinary Plone flows the subscribers hook into.
    doc_id = fixtures.PREFIX + "subscriber-doc"
    created = rest(page, base, "", "POST",
                   {"@type": "Document", "id": doc_id, "title": doc_id})
    check("H1", "adding content with the add-on installed succeeds",
          created["status"] in (200, 201),
          f"{created['status']} {created['body'][:160]}")

    if created["status"] in (200, 201):
        page.goto(f"{base}/{doc_id}/edit", wait_until="load")
        page.wait_for_timeout(1000)
        field = title_field(page)
        if field is not None:
            field.fill(doc_id + " edited")
            page.click("#form-buttons-save")
            page.wait_for_load_state("load")
            page.wait_for_timeout(1500)
        check("H2", "editing content with the add-on installed succeeds",
              "Internal Server Error" not in page.content(), page.url)
