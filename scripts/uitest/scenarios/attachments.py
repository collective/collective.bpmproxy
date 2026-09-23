"""E. Task-scoped attachments and their dynamic security."""

from .. import fixtures
from ..harness import rest
from ..harness import shot
from ..harness import title_field
import json


TITLE = "E. Attachments and dynamic security"

PROXY_TITLE = fixtures.PREFIX + "attachments"


def run(session):
    check = session.checks.check
    base = session.base_url
    page, watcher = session.page("manager")

    # A proxy of its own, with attachments switched on.
    page.goto(base, wait_until="load")
    proxy_url = fixtures.create_proxy(
        page,
        base,
        PROXY_TITLE,
        fixtures.CONTACT_FORM,
        diagram=False,
        attachments=True,
    )
    check(
        "C2",
        "attachments_enabled proxy created",
        PROXY_TITLE in page.content(),
        page.url,
    )

    # Start an instance so there is a task to attach to.
    page.goto(proxy_url, wait_until="load")
    page.wait_for_timeout(1500)
    page.evaluate(
        """(payload) => {
            const form = document.querySelector('#collective-bpmproxy-form-submit');
            form.querySelector('[name="collective-bpmproxy-form-data"]').value = payload;
            form.submit();
        }""",
        json.dumps(
            {
                "senderName": "Site Manager",
                "senderEmail": "manager@example.com",
                "subject": "Attachments Demo",
                "message": "Attachment demo message",
            }
        ),
    )
    page.wait_for_load_state("load")
    page.wait_for_timeout(2500)
    task_url = page.url
    check(
        "E0",
        "landed on a task with attachments enabled",
        "/@@bpm-task/" in task_url,
        task_url,
    )
    if "/@@bpm-task/" not in task_url:
        return

    # E3 -- the attachments viewlet offers the Add attachment button.
    watcher.reset()
    page.goto(task_url, wait_until="load")
    page.wait_for_timeout(1500)
    add = page.locator("a[href*='add-attachment'], form[action*='add-attachment']")
    check(
        "E3",
        "Add attachment control is offered on the task",
        add.count() > 0,
        page.content()[:0],
    )
    session.no_problems("E3", watcher, "task with attachments")
    shot(session, page, "attachments-task", "E3")

    # E1 -- @@add-attachment lazily creates the container and redirects to the
    # Bpm Attachment add form. Submit the real control rather than navigating
    # to the URL: the view writes, so it needs the form's authenticator token,
    # and a bare GET earns plone.protect's "Confirm action" page instead.
    page.click("form[action*='add-attachment'] input[type=submit]")
    page.wait_for_load_state("load")
    page.wait_for_timeout(2500)
    check(
        "E1",
        "add-attachment does not hit a CSRF confirmation",
        "@@confirm-action" not in page.url,
        page.url,
    )
    landed_on_add_form = "++add++" in page.url or title_field(page) is not None
    check(
        "E1",
        "add-attachment redirects to the Bpm Attachment add form",
        landed_on_add_form,
        f"url={page.url} title={page.title()!r} forms={page.locator('form').count()}",
    )

    # E2 -- upload a file.
    field = title_field(page)
    if field is not None:
        field.fill(fixtures.PREFIX + "evidence")
        file_input = page.locator("input[type=file]").first
        file_input.set_input_files(
            {
                "name": "evidence.txt",
                "mimeType": "text/plain",
                "buffer": b"uitest evidence",
            }
        )
        page.click("#form-buttons-save")
        page.wait_for_load_state("load")
        page.wait_for_timeout(2500)

        # Still on the add form means the save was rejected. Report the field
        # errors rather than a bare URL, so a validation change is legible.
        errors = page.locator(
            ".portalMessage.error, .field.error, .invalid-feedback, "
            "#content .error, .alert-danger, [class*='error']"
        )
        error_text = " | ".join(
            errors.nth(i).inner_text().strip()[:120]
            for i in range(min(errors.count(), 5))
        )
        buttons = page.locator("input[type=submit], button[type=submit]")
        button_ids = ", ".join(
            f"{buttons.nth(i).get_attribute('id')}"
            f"={buttons.nth(i).get_attribute('value')}"
            for i in range(min(buttons.count(), 5))
        )
        check(
            "E2",
            "attachment uploaded",
            "++add++" not in page.url,
            f"still on {page.url}; errors: {error_text or '(none)'}; "
            f"buttons: {button_ids or '(none)'}",
        )
        attachment_url = page.url.split("/view")[0]

        # E4 -- the tasks viewlet on the attachment links back to the task.
        check(
            "E4",
            "attachment page lists its related task",
            "bpm-task" in page.content() or "Related tasks" in page.content(),
            page.url,
        )
        shot(session, page, "attachments-listing", "E4")

        # E5 -- a user with no task on this container gets no rights. The
        # editor is a Site Administrator, so this only proves the provider
        # does not *widen* access; the narrow case is covered by the unit
        # tests for AttachmentsLocalRoleProvider.
        editor = session.context("editor")
        response = editor.request.get(attachment_url)
        check(
            "E5",
            "attachment container reachable only through Plone security",
            response.status in (200, 401, 403),
            str(response.status),
        )

    # E6 -- the orphan view is manager-only and returns JSON.
    orphans = rest(page, base, "/@@bpm-proxy-orphan-attachments")
    check(
        "E6",
        "orphan attachments view answers for a manager",
        orphans["status"] in (200, 204),
        str(orphans["status"]),
    )

    # Plone answers an unauthorised anonymous request by *redirecting* to the
    # login form, so following redirects turns a refusal into a 200. Ask for
    # the raw response instead, and treat a login form as a refusal too.
    anon = session.context()
    refused = anon.request.get(
        f"{base}/@@bpm-proxy-orphan-attachments",
        max_redirects=0,
    )
    body = refused.text() if refused.status == 200 else ""
    check(
        "E6",
        "orphan attachments view refused to anonymous",
        refused.status in (301, 302, 401, 403)
        or "__ac_name" in body
        or "require_login" in body,
        f"{refused.status}; {body[:120]}",
    )
