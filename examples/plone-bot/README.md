# Plone bot

This directory is a [purjo](https://datakurre.github.io/purjo/) Robot
Framework task package. Copy `secrets.example.json` to `secrets.json` and set
`PLONE_AUTHORIZATION` to the authorization value used by the Plone REST API.

Run `pur serve .` against an Operaton instance containing either of the
`../empire-insider/ReviewAssistant.bpmn` or
`../empire-insider/FromIdeaToArticle.bpmn` processes. Use `uv lock` to create
or refresh `uv.lock`, `pur wrap` to build a deployable `robot.zip`, and
`pur serve robot.zip` to serve the wrapped package.

## Both bots are required

The two example processes each need topics from *both* task packages, so
`make run` here is not enough on its own -- run `make run` in the other bot's
directory too:

| Process | Needs from `editor-bot` | Needs from `plone-bot` |
| --- | --- | --- |
| `FromIdeaToArticle.bpmn` | the six `GPT *` topics | `Plone Submit Content` |
| `ReviewAssistant.bpmn` | `GPT Create Article` | `Plone Get Content`, `Plone Update Text` |
