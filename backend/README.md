# collective.bpmproxy

Add-on for Plone that integrates [Operaton (a Camunda Platform 7 fork)](https://github.com/operaton/operaton).

__Note:__ the add-on requires its [bundled Operaton instance](#operaton-camunda-7-fork)
with a special authentication plugin authorizing requests from Plone as their initiating Plone users.
See installation instructions below.

Continue reading, as there are quite a few moving parts that need proper orchestration to get it working.

## Camunda Platform

Camunda is a server to run [BPMN 2.0](https://en.wikipedia.org/wiki/Business_Process_Model_and_Notation) processes.

Processes in this context means workflows that need certain degrees of interaction from different parties,
require running external/internal verifications, like:

- a student wants to enroll in a university degree
    - might require automatic checks to see if there are places available
    - might require the student to provide documents that need to be verified manually
- an employee requests a new laptop that requires approval from several managers
    - a manager needs to approve it
    - a check on the IT department storage might yield if there are ready available laptops
    - the account department might have to check their budget
- a review process of a news article that has to go through an approval process
    - a few quality checks might happen
    - a review from another journalist might be needed
    - the art department might suggest (with its internal process) the assets for the news article
    - the online department might want to update the SEO fields as well as timing the social media publication

See ready to test [examples](./examples/).

Camunda 7 provides an API and a web based UI to administrate the processes and tasks.

### Diagrams, decision tables, forms and processes

Camunda 7 differentiates between _designing the processes_,
with its own standalone designer, and _running those processes_.

Furthermore, a process is composed of the following pieces:

- main diagram: what you expect to see, a few boxes and lines that visually explain the process.
- decision tables: some decision tasks migth get a list of options to decide how to proceed,
  you can think of them like an `if/elif/else` or a `switch` programming instruction.
- forms: at any step of the process more information might be required,
  Camunda 7 provides a form generator that can render the forms with predefined data,
  and upon submission, the process continues.
- subdiagrams: a task within a diagram might be to fulfill another diagram,
  this way you have endless possibilities to expand your business processes.

To create diagrams and its related assets, you need to create them with a BPMN 2.0 compliant editor.

Camunda 7 provides already one such editor, see the [installation instructions](#install) below.

### Diagram examples

See the [examples](./examples/) folder for a few diagram examples to get you started.

### A note regarding the version

There is Camunda Platform 8, but they are like two completely different products.
Specially regarding __the license__.

Version 7 is completely open source and will remain like that forever.

### Camunda 7 resources

- [official website](https://camunda.com/platform-7/)
- [official documentation](https://docs.camunda.org/manual/latest/)
- [Training on BPMN](https://academy.camunda.com/camunda-bpmn) _(it might not be free)_
- [Training on DMN](https://academy.camunda.com/camunda-dmn) _(it might not be free)_

## Add-on high level features

Publish BPMN 2.0 processes from Camunda Platform 7,
and interact with the processes with Camunda Forms or BPMN signals.

- A custom content-type, "BPM Proxy" to publish an existing process
  with forms from a configured Camunda Platform 7 (later just "C7") instance
  as a CMS page with "sub pages" for currently open tasks in running instances of that process.

- A portlet to list all tasks available in every running process on the configured C7 instance.
  (Or just the tasks related to the current Plone page.)

- A Portlet to trigger BPMN signals at the configured C7 instance from Plone.

- A content-rule action to broadcast BPMN signals events at the configured C7 instance
  from configured events at Plone.

- Support to show related available user task forms also for pages of other types than BPM Proxy.

- Support to map `++add++` and `++edit++` forms as user task forms and complete user task from their completion.

## Installation

Given that this is an integration package, there are a few parts that need explanation:

- how to install and create __BPMN 2.0 diagrams__
- how to install and __Camunda Platform 7__
- how to integrate Camunda Platform 7 processes __with Plone__

As all topics are quite involved, it is easier to explain them separately.

### Processes Modeler

Camunda provides a stand alone application named `Desktop Modeler`.

Go to its [download website](https://camunda.com/download/modeler/)
and select the right version for your operating system.

Unzip the app and double click on the `camunda-modeler` binary.

An app will open and you will be able to __start modeling your processes!__

See the [`examples`](./examples/) folder for readily available to learn from.

#### Simulate processes

One designing diagrams, specially if they are involved,
it is important to ensure they work.

To lower the full round trip of designing a process, pushing it to Camunda,
testing it in a controlled environment and check if it works,
there is a __plugin__ for the Desktop Modeler that allows you
to __simulate your processes__ before you push them to Camunda.

This way you can much more easily iterate over your designs,
double check them with the end users that will use them, etc.

To install the plugin:

```shell
# Linux
cd ~/.config/camunda-modeler # note the leading dot in ".config"
# Mac OS X
cd ~/Library/Application Support/camunda-modeler
mkdir -p resources/plugins
cd resources/plugins
git clone https://github.com/camunda/camunda-modeler-token-simulation-plugin.git
```

__Note:__ if the Camunda Modeler folder does not exist,
be sure to open the Modeler app at least once. For Windows users,
please check where the configuration folder of apps is located.

Re-start the Modeler app and you should see at the top left of an BPMN diagram
the following image:

![Simulator button](docs/images/token-simulator-button.png?raw=true)

With this you can start simulating your process:

- click on the play button on the starting event
- click on the pause buttons found on all elements to stop the process at that point
- on gateways you are able to choose which branch it should go to

See the [plugin repository](https://github.com/camunda/camunda-modeler-token-simulation-plugin)
for more information about it.

#### Publish processes

Once your process is ready for more real testing,
the following steps are needed to get your process published:

- the diagram must be saved in your file system
- there should be no errors (see the bottom bar for the red circled error icon)
    - the most common error is that the `StartEvent` element must define a `<History time to live>`
        - for that click on the background canvas and select the `History cleanup` section on the right panel
        - set the `time to live` field to a number, like `1`
        - _if you don't see the right pane, go to the main menu -> `Window` -> `Toggle Properties Panel`_
- [Camunda needs to be running](#camunda-platform-7) so you can push your processes there!

Once these conditions are met, you are ready to click on the __rocket icon__
located at the bottom bar.

A small popup will show up to establish the connection to the Camunda server.

The `REST endpoint` field should say `http://localhost:8081/engine-rest`,
if it still shown an error message below the field,
double check that your Camunda instance runs fine.

On the `Authentication` section, select `HTTP Basic` and use `admin` for user and password.

__Note:__ if your model includes forms, decision tables and/or other models
you need to either upload them separately, or include them via the `Include additional files` section.

Once everything is set up properly, finally, push the `Deploy` button!

Head to the [Camunda Cockpit](#camunda-cockpit) to manage the processes.

### Operaton (Camunda 7 fork)

The development environment is managed with [devenv](https://devenv.sh)
(see [`devenv.nix`](./devenv.nix)) and provides the main pieces to get
Operaton working locally:

- Operaton itself (the Spring Boot application from [`fixture/operaton/`](./fixture/operaton/), on port `8081`)
- a PostgreSQL database server (where Operaton stores the tasks and processes)
- a Keycloak instance for OIDC login into the Operaton webapps
  (port `8082`, realm `plone` imported from
  [`devenv/keycloak/realm-plone.json`](./devenv/keycloak/realm-plone.json))
- a debug mail server for local development (a Mailpit instance at <http://localhost:8025>, to check the mails being sent by processes)

With [devenv installed](https://devenv.sh/getting-started/), open a terminal,
enter the dev shell and start the services:

```shell
make shell
make services
```

(`make shell` is just `devenv shell`.) The required
[authentication keys](#authentication-keys) are generated automatically on
first entering the shell.

Leave this terminal running; see [Plone integration](#plone-integration)
below for the second terminal that builds and starts Plone.

See the [troubleshooting sections if you are having problems](#troubleshooting).

#### Authentication keys

To get Plone and Camunda to talk to each other, they need to trust each other.

For that a pair of public/private keys are used.

__Plone__ needs a private key to communicate with Camunda via a JWT-authentication token,
see the [installation instructions for Plone](#plone-integration),
to generate it, run:

```shell
openssl genpkey -algorithm ed25519 -out ec-ed25519-priv-key.pem
```

__Operaton__ needs the public key to verify the JWT-authentication token coming from Plone,
to generate it, run:

```shell
openssl pkey -in ec-ed25519-priv-key.pem -pubout -out ec-ed25519-pub-key.pem
```

(`make shell` generates both keys automatically if they are missing.)

The private key, for Plone, needs to be within reach of the Plone instance,
while the public key needs to be readable by Operaton
(`make services` passes it via the `PLONE_PUBLIC_KEY` environment variable).

#### `engine-rest` authentication modes

Plone's own JWT is always tried first, in every configuration, and never
stops working regardless of anything below -- see
`JWTAuthenticationProvider`/`JWTIdentityService` in the fixture.

Beyond that, `engine-rest` accepts exactly one of two mutually exclusive
fallbacks, chosen by whether Operaton's own webapp login is configured for
Keycloak (`operaton.bpm.oauth2.identity-provider.enabled`, set by the
`oauth2` Spring profile -- which `devenv.nix` activates by default):

- **OAuth2 (Keycloak) enabled:** `engine-rest` also only accepts
  Keycloak-issued JWTs (validated against the realm's JWKS -- issuer,
  signature and expiry checked; audience is not, since the realm is
  dedicated to this deployment). Basic Auth no longer works at all in this
  mode, including the built-in `admin`/`admin` account. A Keycloak token
  authenticates as a **persistent** Operaton user: either the fixed
  username a client's token hardcodes via an `operaton_username` claim (see
  the `operaton-worker` service-account client below), or, for interactive
  logins with no such claim, `preferred_username`. Group membership comes
  from the token's `groups` claim when present (the realm's
  `oidc-group-membership-mapper`, the same one Cockpit's own OAuth2 login
  already relies on) -- and falls back to the resolved username's
  persistent group membership when it is absent.
- **OAuth2 disabled (the default Spring Boot profile, no `oauth2`):**
  `engine-rest` falls back to persistent HTTP Basic Auth, same as before
  this dual-mode existed.

An unrecognized or absent credential is rejected (401) in both modes --
there is no unauthenticated fallthrough.

This means any external tool that talks to `engine-rest` directly (not
through Plone) needs Keycloak credentials whenever the `oauth2` profile is
active, which it is by default in this devenv stack -- see
`examples/renovation-bot/` and `examples/renovation-bot-py/` for working
examples, and `examples/simple-process/README.md` for the resulting Camunda
Modeler caveat. `devenv/keycloak/realm-plone.json` defines an
`operaton-worker` client for exactly this: a confidential,
service-account-enabled (`client_credentials` grant) client whose tokens
carry a hardcoded `operaton_username: admin` claim.

#### Operaton cockpit

The Operaton cockpit, its web UI to manage processes, can be found at:

<http://localhost:8081/operaton/app/cockpit/default/>

Signing in happens through Keycloak (OIDC). The development realm ships two
accounts: `admin`/`admin` (member of `camunda-admin`, full access) and
`user`/`user` (regular user).

You should see a three pane layout with the middle column having entries of all your uploaded processes.

If you still haven't uploaded any, [learn how to do it](#publish-processes).

### Plone integration

With [processes created](#processes-modeler) and [Operaton running](#operaton-camunda-7-fork)
its time for the last piece of the puzzle.

If you are using pip and mxdev to install Plone 6,
please see [the Plone documentation](https://6.docs.plone.org/install/manage-add-ons-packages.html)
on how to add `collective.bpmproxy` to your setup.

You will need to set two environment variables on the shell
(`make shell` sets both automatically):

```shell
CAMUNDA_API_URL="http://localhost:8081/engine-rest"
CAMUNDA_API_PRIVATE_KEY="/FULL-PATH-TO-YOUR-PRIVATE-KEY/ec-ed25519-priv-key.pem"
```

For local development of this repository, open a second terminal (while
`make services` keeps running in the first one), enter the dev shell and
start Plone:

```shell
make shell
make start
```

`make start` installs the package with [uv](https://docs.astral.sh/uv/)
into `backend/.venv` (equivalent to `make install`; the venv location is
pinned in `devenv.nix`), then creates the Plone instance on first run and
starts it. Re-running it later just starts
Plone again.

You can run the automated tests with:

```shell
make test         # Runs the offline tests
make test-live    # Runs the tests requiring a live Operaton instance
make test-renovation  # Runs the renovation demo integration tests
```

Create a Plone (Classic UI) instance and install the `collective.bpmproxy` add-on.

There are two main ways to integrate BPMN processes with Plone:

- via a content type: then the BPMN process _needs_ a form as a first step
- via a signal: a Plone content rule needs to be installed globally or on a folder/document.
  `collective.bpmproxy` already provides a few content rules ready to be used

#### Content type integration

On the Plone Toolbar's `Add` menu you should see a new content type: `Bpm Proxy`.

This new content type allows to select (with autocompletion!) a process you want to manage.

After creating the document, fill it and monitor the process in [Camunda's Cockpit](#camunda-cockpit).

#### Folderish integration

The `Bpm Proxy` type's whole schema is also available as a reusable
Dexterity behavior, `collective.bpmproxy.process_context`
(`IProcessContext`/`IProcessContextBehavior`). Enable it on any
project-specific folderish Dexterity type to host a process directly on
that type, instead of on a dedicated `Bpm Proxy` page.

Configure the deployed process definition, optional diagram/attachments,
initial process variables, and start-form defaults on each instance. The
start form is available at the instance's normal `view` URL — that only
works because `views/configure.zcml` registers `view` for `IProcessContext`
generically, not for any one content type. Assign the Task list portlet with
**Show only tasks for the current context** enabled so only tasks belonging
to that instance are shown.

Each start creates the business key `<instance-UID>:<process-instance-UUID>`.
This keeps all process instances linked to the content while allowing
multiple concurrent instances. BPMN start and task forms can use the
configured Plone string substitutions and deployed form vocabularies; task
links return to the content through its UID.

A folderish content type does not have to use this behavior at all, though —
see `examples/renovation-project/` and `docs/renovation-project-scenario.md`
for a richer example where a plain Dexterity Container relies entirely on
the Task list and Message dispatch portlets, with every process
signal/message-started from Plone workflow transitions.

All BPM Proxy portlets can optionally be restricted to selected Plone review
states. The `Display for review states` field uses Plone's
`plone.app.vocabularies.WorkflowStates` vocabulary, so it includes states from
installed workflows, including custom workflow states. Leave the selection
empty to display the portlet for every review state. Visibility is evaluated
against the content item where the portlet is rendered; for an unfiltered Task
list (`Show only tasks for the current context` disabled), this is the current
page rather than the state of each individual task's linked content.

#### Content rules integration

For processes that should happen automatically _given a certain condition_,
install a `collective.bpmproxy` provided content rule with the following steps:

- go to the folder where the content rule should be applied
- on the Plone toolbar select the `Rules` option
- on the view that opens, select from the drop down the content rule that suits your needs
- configure the installed content rule as any other content rules

If, for example, you selected the rule `BPMN signal: submitted any`
your BPMN process needs to have a `Signal StartEvent` element
with a `Signal` configured to `plone-content-submitted`.

Open the [`examples/published-lifecycle`](./examples/published-lifecycle/example-published-lifecycle.bpmn)
diagram with the [Modeler app](#processes-modeler) for such an example: its
start event listens for the `plone-content-published` signal.

## Advanced topics

Note that you need to be already comfortable with Camunda 7 and designing processes,
but for the braves ones, here are some advanced topics:

- [Automation playground](https://datakurre.github.io/automation-playground/)

### Multi-tenancy support

Camunda 7 support multi-tenancy identifiers
allowing single process engine to support multiple independent customers.

Tenant id could be set in Camunda Modeler, when deploying models and their resources.
With `collective.bpmproxy` installed,
it is possible to define set of tenancy identifiers for the site
by setting configuration registry key `collective.bpmproxy.tenant_ids`.
Each Plone site will allow its users to access only those Camunda resources,
which are deployed or related to its tenant ids or no tenant ids at all.

### Engine authorization model

This is about *authorization* -- what an already-authenticated principal is
allowed to do. See [`engine-rest` authentication modes](#engine-rest-authentication-modes)
above for how a principal gets authenticated in the first place.

`operaton.bpm.authorization.enabled: true` is set, but it does less than it
looks like it does, and that is deliberate:

- Every authenticated principal (including an anonymous Plone visitor -- see
  `docs/user/10-anonymous-and-tenancy.md`) has a **global** grant to read
  and start any process definition. This is not scoped to a group, because
  the anonymous requester's identity carries no group at all to scope it to.
  The real access control is Plone's: whether a visitor can reach a Bpm
  Proxy's start form in the first place is a normal Plone View/Add
  permission check, before the engine is ever called. Every request the
  engine sees was signed by this add-on's own JWT, so "any authenticated
  principal" means "reached a Plone view that decided to call the engine" --
  narrowing the engine-side grant further would need a per-process-to-Plone-
  group mapping this add-on does not have, and would break the
  contact-form demo's anonymous requester in the process. See the
  comment on `Engine.defaultAuthorizations()` in the fixture if you are
  considering changing this.
- Authorization is still real for the resources it *is* scoped to: the
  `camunda-admin` group is what makes deployment and other admin-only
  actions actually admin-only (see `JWTIdentityService`), and it is what
  Cockpit's own admin-management views (Authorization/User/Group) filter by.
  A **non-admin token still gets HTTP 200** from list/count endpoints on
  those resources (e.g. `/authorization/count`) -- that is Camunda/Operaton's
  normal REST behavior for query endpoints (row-level filtering to what the
  caller is authorized to see, not a blanket 403) and was confirmed, not a
  gap: an admin token sees the real count, a non-admin token sees `0`/`[]`.

## Troubleshooting

A few of the installation errors that we have found and solved:

- `openssl` version: version `3.x` is reported to be working while anything below fails.
  `openssl` is needed to generate the [pair keys](#authentication-keys)
- If you see the following traceback in Plone
  `AssertionError: Connection is a "hop-by-hop" header; it cannot be used by a WSGI application (see PEP 3333)`
  look at the Operaton process log (`make services` output): Operaton is having
  a problem trying to read the public key (check the `PLONE_PUBLIC_KEY`
  environment variable).

If your problem is not listed here,
please take the time to [create an issue](https://github.com/collective/collective.bpmproxy/issues/new)!

## Contribute

- [Issue Tracker](https://github.com/collective/collective.bpmproxy/issues)
- [Source Code](https://github.com/collective/collective.bpmproxy)

## License

The project is licensed under the GPLv2.
