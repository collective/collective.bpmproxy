# Limitations of the development fixture

The Operaton instance under `fixture/operaton/` is a development fixture, not a
production engine. A few things the shipped examples use are deliberately not
configured, and processes that rely on them will appear to stall.

## No mail connector

Send tasks that use a `camunda:connector` mail extension have no implementation
behind them. The task will fail rather than send, and in some branches that
rolls the completing transaction back.

Mailpit is available at <http://localhost:8025> for anything that does send
mail through ordinary SMTP.

## No scripting engine

`camunda:script` and script-valued input parameters (for example the Python
snippet in `examples/request-for-quote`) have no engine to run in. Use an
expression instead, or precompute the value.

## Candidate groups must exist in Plone

Examples written against a hosted Camunda use candidate groups such as
`Site Administrators`. The local fixture's identities come from Plone, so a
candidate group must be a Plone group that actually exists — otherwise the task
is created but nobody can claim it.

## When the engine is unreachable

If the engine cannot be reached, the process definition vocabulary comes back
empty rather than raising, so add and edit forms still render. A Bpm Proxy
whose process cannot be loaded will not show a start form.

The deployments service answers HTTP 500 with an `error` body when the engine
is down — most often because its PostgreSQL went away. Check
`.devenv/run/processes/logs/operaton.stdout.log`.
