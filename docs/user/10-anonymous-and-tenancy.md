# Anonymous visitors and tenants

## Public processes

A published Bpm Proxy works for visitors who are not logged in. Each anonymous
visitor is given a stable pseudo-identity of the form `anonymous-<uuid>`, which
the engine sees as the process initiator.

Because there is no session to hang that identity on, the redirect into the
visitor's first task carries it as a `token=` query parameter. Following that
link is what lets a visitor come back to their own task — and only their own.

This is what makes request/quote and contact-form style processes work without
asking the visitor to register.

## Tenants

Operaton supports multi-tenancy: a deployment can be tagged with a tenant id.
Set which tenants a Plone site may use in the configuration registry, under
`collective.bpmproxy.tenant_ids`.

With tenants configured, the process definition list on the Bpm Proxy add form
shows only definitions belonging to those tenants, plus definitions deployed
with no tenant at all. One engine can therefore serve several Plone sites
without either seeing the other's processes.

Definition tokens are `{key}:{tenant}` when a tenant is set, and just `{key}`
otherwise.
