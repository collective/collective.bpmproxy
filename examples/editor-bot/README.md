# Editor bot

This directory is a [purjo](https://datakurre.github.io/purjo/) Robot
Framework task package. Copy `secrets.example.json` to `secrets.json`, add an
OpenAI key, and run `pur serve .` against the Operaton instance containing
`../empire-insider/FromIdeaToArticle.bpmn`.

Use `uv lock` to create or refresh `uv.lock`, `pur wrap` to build a deployable
`robot.zip`, and `pur serve robot.zip` to serve the wrapped package.

## Both bots are required

The two example processes each need topics from *both* task packages, so
`make run` here is not enough on its own -- run `make run` in the other bot's
directory too:

| Process | Needs from `editor-bot` | Needs from `plone-bot` |
| --- | --- | --- |
| `FromIdeaToArticle.bpmn` | the six `GPT *` topics | `Plone Submit Content` |
| `ReviewAssistant.bpmn` | `GPT Create Article` | `Plone Get Content`, `Plone Update Text` |
