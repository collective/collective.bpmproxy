# Contact Form Email Worker

An `operaton-tasks` worker in pure Python that handles the `contact-form-email` topic of the `example-contact-form` process, sending reply emails to the recipient via Mailpit SMTP (`127.0.0.1:1025`).

## Deploying the Process

Deploying `../contact-form/contact-form.bpmn` and its forms uses
[purjo](https://datakurre.github.io/purjo/), authenticating to Operaton's
`engine-rest` the same OAuth2 (Keycloak-issued) way `examples/renovation-bot`
does — Basic Auth isn't an alternative against this devenv fixture.

1. Prepare `secrets.env` (same file `make serve` uses):
   ```sh
   cp secrets.example.env secrets.env
   ```
2. Deploy:
   ```sh
   make deploy
   ```
   or directly with uv:
   ```sh
   uv run --env-file secrets.env --with=purjo pur operaton deploy ../contact-form/contact-form.bpmn ../contact-form/contact-form-start.form ../contact-form/contact-form-review.form ../contact-form/contact-form-delegated.form
   ```

## Running the Worker

1. Prepare `secrets.env`:
   ```sh
   cp secrets.example.env secrets.env
   ```
2. Start the worker:
   ```sh
   make serve
   ```
   or directly with uv:
   ```sh
   uv run --env-file secrets.env --with="operaton-tasks[cli]" operaton-tasks serve tasks.py
   ```

## Checking Delivered Emails

Mailpit is available locally:
- Web UI: <http://localhost:8025>
- REST API: <http://localhost:8025/api/v1/messages>
