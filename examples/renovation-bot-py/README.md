# Renovation bot (Python)

A pure-Python alternative to [`../renovation-bot/`](../renovation-bot/README.md),
built on [`operaton-tasks`](https://pypi.org/project/operaton-tasks/) —
the library purjo itself is built on — run ad hoc via
`uv run --with=operaton-tasks`, instead of purjo/Robot Framework.

It implements the exact same contract, against the exact same BPMN, as
`../renovation-bot/`: one external topic, `Plone Workflow Transition`, that
resolves a Plone content UUID and POSTs the given workflow transition to it.
All three of the demo's BPMN processes
(`../renovation-project/renovation-plan-review.bpmn`,
`renovation-work-and-extra-work.bpmn`, `renovation-final-review.bpmn`) share
this topic on their one external service task each, passing a different
`transition` input parameter per call site. `tasks.py` is the Python
equivalent of `../renovation-bot/tasks.robot`.

Deploy the three BPMN files first — `../renovation-bot/`'s `make deploy`
target already does this; both bots are interchangeable workers for the
same deployed processes, so only one needs to run at a time.

Copy `secrets.example.env` to `secrets.env` and fill in `PLONE_AUTHORIZATION`
(the authorization header value for the `renovation-bot` Site Administrator
account created by the `collective.bpmproxy:renovation_demo` profile — same
account `../renovation-bot/secrets.json` uses). The `OAUTH2_*` variables
already default to the `operaton-worker` service-account client from
`devenv/keycloak/realm-plone.json` — engine-rest in this fixture requires
OAuth2 (Keycloak-issued) tokens, not Basic Auth, so these aren't optional.
See the comments in `secrets.example.env` for details.

Run `make serve` to start the worker. `make test` imports `tasks.py` to
sanity-check it against an installed `operaton-tasks[cli]`.
