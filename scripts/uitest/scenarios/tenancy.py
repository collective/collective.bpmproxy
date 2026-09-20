"""K. Multi-tenancy filtering of the process definition vocabulary."""

from .. import fixtures
from ..harness import rest


TITLE = "K. Multi-tenancy"

RECORD = "/@registry/collective.bpmproxy.tenant_ids"


def definition_options(page, base_url):
    page.goto(f"{base_url}/++add++Bpm Proxy", wait_until="load")
    page.wait_for_timeout(1000)
    field = page.locator("#form-widgets-process_definition_key")
    if not field.count():
        return []
    return field.locator("option").evaluate_all(
        "options => options.map((o) => o.value)"
    )


def run(session):
    check = session.checks.check
    base = session.base_url
    page, _ = session.page("manager")
    page.goto(base, wait_until="load")

    before = definition_options(page, base)
    check(
        "K1",
        "untenanted definitions are offered by default",
        fixtures.CONTACT_FORM in before,
        "; ".join(before)[:200],
    )

    # Restrict the site to a tenant nothing is deployed under.
    original = rest(page, base, RECORD)
    set_result = rest(
        page,
        base,
        "/@registry",
        "PATCH",
        {"collective.bpmproxy.tenant_ids": ["uitest-tenant"]},
    )
    check(
        "K1",
        "tenant_ids is writable through the registry",
        set_result["status"] in (200, 204),
        f"{set_result['status']} {set_result['body'][:160]}",
    )

    try:
        after = definition_options(page, base)
        # Definitions deployed without a tenant stay visible by design; what
        # must not appear is a definition belonging to another tenant. With
        # nothing deployed under "uitest-tenant" the list must not grow.
        check(
            "K2",
            "restricting tenants does not widen the vocabulary",
            set(after) <= set(before),
            f"gained: {sorted(set(after) - set(before))}",
        )
    finally:
        restore = (original["json"] or {}).get("value", [])
        rest(
            page,
            base,
            "/@registry",
            "PATCH",
            {"collective.bpmproxy.tenant_ids": restore},
        )

    restored = definition_options(page, base)
    check(
        "K1",
        "vocabulary restored after clearing tenant_ids",
        fixtures.CONTACT_FORM in restored,
        "; ".join(restored)[:200],
    )
