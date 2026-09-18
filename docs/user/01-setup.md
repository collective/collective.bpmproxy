# Setting up

`collective.bpmproxy` needs three things running: a Plone site with the add-on
installed, an Operaton engine, and a shared key pair the two use to trust each
other.

## Start the services

From the repository root, in one terminal:

```shell
devenv up -d          # PostgreSQL, Keycloak, Mailpit, Operaton
devenv processes wait # block until Operaton answers its readiness probe
```

| Service | URL |
| --- | --- |
| Plone | <http://localhost:8080/Plone> |
| Operaton REST | <http://localhost:8081/engine-rest> |
| Operaton Cockpit | <http://localhost:8081/operaton/app/cockpit/default/> |
| Keycloak | <http://localhost:8082> |
| Mailpit | <http://localhost:8025> |

Then, in a second terminal:

```shell
make start            # Plone on :8080
```

## Signing keys

Plone signs every engine request with an ed25519 private key; Operaton verifies
it with the matching public key. `devenv shell` generates both on first entry
if they are missing:

```shell
openssl genpkey -algorithm ed25519 -out ec-ed25519-priv-key.pem
openssl pkey -in ec-ed25519-priv-key.pem -pubout -out ec-ed25519-pub-key.pem
```

Plone reads `CAMUNDA_API_URL` and `CAMUNDA_API_PRIVATE_KEY`; Operaton reads
`PLONE_PUBLIC_KEY`. All three are exported by the dev shell.

If Plone raises `AssertionError: Connection is a "hop-by-hop" header`, Operaton
could not read the public key — check `PLONE_PUBLIC_KEY`.

## Install the add-on

In Site Setup → Add-ons, install **collective.bpmproxy**. Installing it:

- creates the `camunda-admin` group, which contains `Administrators`;
- registers the `Bpm Proxy`, `Bpm Attachments` and `Bpm Attachment` types;
- installs seven content rules that broadcast BPMN signals;
- adds the `collective.bpmproxy.tenant_ids` registry record.

Install **collective.bpmproxy.modeler** as well for the in-Plone BPMN, DMN and
form modeler described in [the next page](02-deploying-processes.md).

Only members of `camunda-admin` can deploy: the engine accepts a Plone user's
token only if that token carries engine rights.
