# Renovation case-management scenario

This is the reproducible case-management example for the
`collective.bpmproxy:renovation_demo` profile. A folderish Renovation Project
is a Plone case. Creating the case starts one Operaton process with a signal;
the case UUID correlates all later messages and task queries.

The example demonstrates both directions of synchronization:

- Plone workflow transitions notify the running case process with correlated
  BPMN messages.
- BPMN external tasks apply workflow transitions back to Plone.
- A BPMN `++add++Document` task opens the native Plone creation form and is
  completed by the existing add-task subscriber.
- Direct Document creation during work emits a case-correlated message and
  starts a non-interrupting document-review subprocess.
- The case Message portlet starts a repeatable extra-work approval subprocess.

## Assets

The case coordinator process is:

```text
examples/renovation-project/renovation-case.bpmn
```

The called page-review process is:

```text
examples/renovation-project/renovation-page-review.bpmn
```

Forms are:

```text
renovation-owner-approval.form
renovation-inspector-approval.form
```

## Prerequisites

Run from the repository root:

```sh
devenv up -d
until curl -sf http://127.0.0.1:8081/engine-rest/engine >/dev/null; do sleep 5; done
make bootstrap-site
make start
until curl -sf http://127.0.0.1:8080/Plone >/dev/null; do sleep 3; done
```

Deploy the case process:

```sh
cd examples/renovation-project
cp secrets.example.env secrets.env
make deploy
cd ../..
```

Stop the Plone process, install the demo profile so its creation signal starts the
deployed process, and start Plone again:

```sh
make bootstrap-renovation-demo
make start
until curl -sf http://127.0.0.1:8080/Plone >/dev/null; do sleep 3; done
```

The bootstrap script creates the groups, demo users, and fresh
`renovation-project-demo` case. The profile's content-type portlet assignments
provide aggregate case tasks on the case and page-review tasks on Documents. The browser
scenario assumes this prepared state and does not modify deployments or
recreate the case.

## Personas

| User | Role |
| --- | --- |
| `owner` | Renovation Owners |
| `contractor` | Renovation Contractors |
| `inspector` | Renovation Inspectors |
| `admin` | Operaton Cockpit observer |

## Scenario

1. Contractor adds a Document directly inside the case.
2. The child-created message starts a child page-review process with parallel owner and inspector tasks.
3. Owner and inspector complete the document review independently.
4. A case manager closes the Plone case through its `close-case` workflow transition.
5. The close message reaches the main case process and ends it.

Run the browser smoke test with:

```sh
playwright-python scripts/e2e_renovation_project.py
```

## Resetting

Delete the Operton deployment, stop Plone, redeploy the BPMN, and rerun
`make bootstrap-renovation-demo` to delete and recreate the demo case, groups,
roles, and portlets. Since this is a disposable example, no migration or
upgrade path is provided.
