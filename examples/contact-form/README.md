# Contact Form Example

A contact form process demonstrating Plone-Camunda/Operaton integration with start forms, reviewer triage and delegation, and asynchronous external task email dispatch.

## Features

- **Start Form (`contact-form-start.form`)**: Allows anonymous visitors or logged-in users to submit a message (`senderName`, `senderEmail`, `subject`, `message`).
- **Review Task (`contact-form-review.form`)**: Assigned to Plone `Administrators`. Displays the submitted message and provides three decisions:
  - **Reply**: Enter a response message to reply via email.
  - **Delegate**: Assign the message to a specific Plone username (`assignedUser`).
  - **Abandon**: Close without sending a response.
- **Delegated Task (`contact-form-delegated.form`)**: Assigned to the chosen user (`${assignedUser}`) to review and either reply or abandon.
- **External Email Worker (`contact-form-email`)**: A service task handled by the Python worker in `examples/contact-form-bot-py`, which delivers reply emails to Mailpit SMTP (`127.0.0.1:1025`).

## Assets

- `contact-form.bpmn` — Process definition (`example-contact-form`)
- `contact-form-start.form` — Start form
- `contact-form-review.form` — Initial review & triage form
- `contact-form-delegated.form` — Delegated review form
