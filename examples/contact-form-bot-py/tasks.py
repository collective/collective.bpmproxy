"""operaton-tasks worker for the contact-form's "contact-form-email" topic.

Built on https://pypi.org/project/operaton-tasks/.
Runs with:

    uv run --env-file secrets.env --with="operaton-tasks[cli]" operaton-tasks serve tasks.py

or via `make serve` in this directory.
"""

from email.message import EmailMessage
from operaton.tasks.types import CompleteExternalTaskDto
from operaton.tasks.types import ExternalTaskComplete
from operaton.tasks.types import LockedExternalTaskDto
import operaton.tasks
import os
import smtplib


MAILPIT_SMTP_HOST = os.environ.get("MAILPIT_SMTP_HOST", "127.0.0.1")
MAILPIT_SMTP_PORT = int(os.environ.get("MAILPIT_SMTP_PORT", "1025"))
MAILPIT_FROM_ADDRESS = os.environ.get("MAILPIT_FROM_ADDRESS", "support@example.com")


@operaton.tasks.task("contact-form-email", localVariables=False)
async def send_contact_email(task: LockedExternalTaskDto) -> ExternalTaskComplete:
    """Read inquiry details and reply message from process variables, then send via SMTP."""
    variables = task.variables or {}
    try:
        sender_email = variables["senderEmail"].value
        reply_message = variables["replyMessage"].value
    except KeyError as exc:
        raise RuntimeError(f"Missing required process variable: {exc}") from exc

    sender_name = getattr(variables.get("senderName"), "value", None) or "Inquirer"
    subject = getattr(variables.get("subject"), "value", None) or "Contact inquiry"

    msg = EmailMessage()
    msg["From"] = MAILPIT_FROM_ADDRESS
    msg["To"] = f"{sender_name} <{sender_email}>"
    msg["Subject"] = f"Re: {subject}"
    msg.set_content(reply_message)

    with smtplib.SMTP(MAILPIT_SMTP_HOST, MAILPIT_SMTP_PORT, timeout=10) as smtp:
        smtp.send_message(msg)

    return ExternalTaskComplete(
        task=task,
        response=CompleteExternalTaskDto(workerId=task.workerId),
    )
