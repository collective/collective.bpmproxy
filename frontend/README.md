# frontend/ — future Volto add-on

This directory is a placeholder for a future [Volto](https://github.com/plone/volto)
add-on (`volto-bpmproxy` or similar) providing the React frontend for
`collective.bpmproxy`. The Plone Classic UI integration (browser views,
portlets, viewlets in `src/collective/bpmproxy/`) remains the primary frontend
until this add-on exists.

## REST API surface needed for Volto

The Volto add-on will need `plone.restapi` endpoints (services) covering what
the Classic UI does server-side today:

| Capability | Classic UI implementation today | Needed REST endpoint |
|---|---|---|
| Task listing | `TasksPortlet` (`portlets/tasks.py`) queries Operaton for pending user tasks filtered by context UUID / process key | `GET .../@bpmproxy-tasks?context={uuid}&process={key}` |
| Start form schema + defaults | `BpmProxyStartFormView` (`views/bpm_form_view.py`) fetches the deployed Camunda Form JSON, applies `plone.stringinterp` defaults | `GET .../@bpmproxy-start-form` |
| Start process / submit form | POST handling in `BpmProxyStartFormView` with server-side validation (`utils.validate_camunda_form`) | `POST .../@bpmproxy-start-form` |
| Task form schema + variables | `BpmProxyTaskFormView` (`@@bpm-task/{task_id}`) | `GET .../@bpmproxy-task/{task_id}` |
| Complete task | POST handling in `BpmProxyTaskFormView` | `POST .../@bpmproxy-task/{task_id}` |
| Signal dispatch | `SignalPortlet` (`portlets/signal.py`) fires a named BPMN signal with interpolated JSON payload | `POST .../@bpmproxy-signal` |
| BPMN diagram | `get_diagram_xml` (`client.py`) returns BPMN 2.0 XML rendered by `bpmn-js` | `GET .../@bpmproxy-diagram` |
| Attachments | `Bpm Attachments` / `Bpm Attachment` content plus dynamic local roles (`adapters/security.py`) | standard `plone.restapi` content endpoints |

Client-side rendering building blocks already used by the Classic UI bundle
(`src/collective/bpmproxy/browser/static/`) and reusable in Volto:

- `@bpmn-io/form-js-viewer` — renders Camunda Form JSON schemas
- `bpmn-js` — BPMN 2.0 diagram viewer with current-task highlighting
