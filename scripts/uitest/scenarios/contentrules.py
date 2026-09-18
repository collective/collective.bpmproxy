"""G. Content rules that broadcast BPMN signals."""

from .. import fixtures
from ..harness import rest
from ..harness import shot


TITLE = "G. Content rules and signals"

RULES = [
    "collective-bpmproxy-published-any",
    "collective-bpmproxy-submitted-any",
    "collective-bpmproxy-published-one",
    "collective-bpmproxy-retracted-one",
    "collective-bpmproxy-rejected-one",
    "collective-bpmproxy-deleted-one",
    "collective-bpmproxy-modified-one",
]


def run(session):
    check = session.checks.check
    base = session.base_url
    page, watcher = session.page("manager")

    # G1 -- all seven rules ship with the default profile.
    page.goto(f"{base}/@@rules-controlpanel", wait_until="load")
    page.wait_for_timeout(1500)
    body = page.content()
    missing = [rule for rule in RULES if rule not in body]
    check("G1", "all seven BPMN signal rules are installed",
          not missing, f"missing: {', '.join(missing)}")
    shot(session, page, "contentrules-list", "G1")

    # The signal-started example is what makes G2 observable.
    deployed = fixtures.deploy_example(
        page, base, "published-lifecycle", fixtures.LIFECYCLE_ASSETS
    )
    for name, status, detail in deployed:
        check("G2", f"deployed {name}", status == 200, f"{status} {detail}")

    # G2 -- assign "Published any" to the site root and publish something.
    page.goto(f"{base}/@@manage-content-rules", wait_until="load")
    page.wait_for_timeout(1000)
    assigned = False
    select = page.locator("select[name='rule_id'], #rule_id")
    if select.count():
        options = select.first.locator("option").evaluate_all(
            "options => options.map((o) => o.value)")
        target = "collective-bpmproxy-published-any"
        if target in options:
            select.first.select_option(target)
            add = page.locator(
                "input[type=submit][name*='add'], button[type=submit]")
            if add.count():
                add.first.click()
                page.wait_for_load_state("load")
                page.wait_for_timeout(1500)
                assigned = True
    check("G2", "published-any rule assignable to a folder", assigned,
          "could not drive @@manage-content-rules")

    # Publishing a document must not error, whether or not a process picks the
    # signal up: the dispatch is deferred to tpc_finish, so a failure here
    # would mean the commit itself broke (G5).
    watcher.reset()
    doc_id = fixtures.PREFIX + "signal-doc"
    created = rest(page, base, "", "POST",
                   {"@type": "Document", "id": doc_id, "title": doc_id})
    check("G2", "document created", created["status"] in (200, 201),
          f"{created['status']} {created['body'][:160]}")

    if created["status"] in (200, 201):
        doc_url = f"{base}/{doc_id}"
        published = fixtures.publish(page, doc_url)
        check("G2", "publishing with a signal rule active succeeds",
              published, "see @workflow/publish response")

        # G5 -- the signal is dispatched at tpc_finish, so a committed
        # transition is the evidence the deferred dispatch did not break the
        # commit. Read the state back rather than trusting the response.
        state = rest(page, base, f"/{doc_id}")
        review_state = (state["json"] or {}).get("review_state")
        check("G5", "the publish transaction committed",
              review_state == "published", f"review_state={review_state!r}")
        session.no_problems("G2", watcher, "publish with signal rule")
