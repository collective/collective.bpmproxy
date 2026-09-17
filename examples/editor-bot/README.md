# Editor bot

This directory is a [purjo](https://datakurre.github.io/purjo/) Robot
Framework task package. Copy `secrets.example.json` to `secrets.json`, add an
OpenAI key, and run `pur serve .` against the Operaton instance containing
`../empire-insider/FromIdeaToArticle.bpmn`.

Use `uv lock` to create or refresh `uv.lock`, `pur wrap` to build a deployable
`robot.zip`, and `pur serve robot.zip` to serve the wrapped package.
