# Renovation bot

This directory is a [purjo](https://datakurre.github.io/purjo/) Robot
Framework task package. Copy `secrets.example.json` to `secrets.json` and set
`PLONE_AUTHORIZATION` to the authorization value used by the Plone REST API
for the `renovation-bot` Site Administrator account created by the
`collective.bpmproxy:renovation_demo` profile.

Also copy `secrets.example.env` to `secrets.env` — a separate mechanism, for
purjo's own connection to Operaton's engine-rest (purjo is built directly on
`operaton-tasks`, which reads these as process env vars, not purjo secrets).
The devenv fixture requires OAuth2 (Keycloak-issued) tokens there, not Basic
Auth, so this file isn't optional; see its comments for details.

It maps a single external topic, `Plone Workflow Transition`, to one Robot
task (`Transition content`) that resolves a Plone content UUID and POSTs the
given workflow transition to it. All three of the demo's BPMN processes
(`../renovation-project/renovation-plan-review.bpmn`,
`renovation-work-and-extra-work.bpmn`, `renovation-final-review.bpmn`) share
this same topic on their one external service task each, passing a different
`transition` input parameter per call site.

Run `pur serve .` against an Operaton instance with those three processes
deployed. Use `uv lock` to create or refresh `uv.lock`, `pur wrap` to build a
deployable `robot.zip`, and `pur serve robot.zip` to serve the wrapped
package.
