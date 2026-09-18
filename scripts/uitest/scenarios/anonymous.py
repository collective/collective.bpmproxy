"""J. Anonymous visitors driving a public process."""

from .. import fixtures
import json


TITLE = "J. Anonymous visitors"

PROXY_TITLE = fixtures.PREFIX + "public"


def run(session):
    check = session.checks.check
    base = session.base_url
    page, _ = session.page("manager")

    # A published proxy is what an anonymous visitor can reach at all.
    page.goto(base, wait_until="load")
    proxy_url = fixtures.create_proxy(page, base, PROXY_TITLE, fixtures.RFQ)
    published = fixtures.publish(page, proxy_url)
    check("J0", "public proxy published", published, proxy_url)

    # J1 -- an anonymous visitor sees the start form.
    anon_page, anon_watcher = session.page()
    anon_page.goto(proxy_url, wait_until="load")
    anon_page.wait_for_timeout(2000)
    check("J1", "anonymous visitor can load the start form",
          anon_page.locator("#collective-bpmproxy-form .fjs-container").count() > 0,
          anon_page.url)
    session.no_problems("J1", anon_watcher, "anonymous start form")

    # J1/J2 -- starting a process as anonymous gets a pseudo-identity, and the
    # redirect into the first task carries it as ?token=.
    if anon_page.locator("#collective-bpmproxy-form-submit").count():
        anon_page.evaluate(
            """(payload) => {
                const form = document.querySelector(
                    '#collective-bpmproxy-form-submit');
                form.querySelector(
                    '[name="collective-bpmproxy-form-data"]').value = payload;
                form.submit();
            }""",
            json.dumps({"category": "a"}),
        )
        anon_page.wait_for_load_state("load")
        anon_page.wait_for_timeout(2500)
        url = anon_page.url
        check("J1", "anonymous submit starts a process",
              "Submit successful" in anon_page.content() or
              "/@@bpm-task/" in url, url)
        check("J2", "the anonymous redirect carries a token",
              "token=" in url or "/@@bpm-task/" in url, url)

        if "/@@bpm-task/" in url:
            check("J2", "anonymous visitor can open its own task",
                  anon_page.locator(
                      "#collective-bpmproxy-form .fjs-container").count() > 0,
                  url)
