# AGENTS.md — collective.bpmproxy

## Project Overview

**collective.bpmproxy** is a Plone CMS add-on that integrates [Camunda Platform 7](https://camunda.com/platform-7/) — a BPMN 2.0 process engine — into Plone Classic UI. It acts as a proxy layer so that Plone users interact with Camunda processes (workflows, tasks, forms) entirely through the Plone interface, never touching Camunda directly.

- **License:** GPLv2
- **Author:** Asko Soukka (`asko.soukka@iki.fi`)
- **Repository:** <https://github.com/collective/collective.bpmproxy>

### Current Status: Migrations Landed (staged in working tree)

Four major changes are complete on disk (staged, not yet committed):

1. **Camunda 7 (Micronaut) → Operaton (Spring Boot).** The old `camunda/` app was replaced by `fixture/operaton/`, a Spring Boot 4 app on Operaton 2.1.0 (a Camunda 7-compatible fork). Runtime verified.
2. **devenv + Keycloak OIDC.** The repo-level dev environment is now [devenv](https://devenv.sh) (`devenv.nix`): PostgreSQL, Keycloak (realm `plone` from `devenv/keycloak/realm-plone.json`, port 8082), Mailpit, and the Operaton app as managed processes. The Operaton **webapps** authenticate via OIDC against Keycloak (Spring profile `oauth2`, `operaton-bpm-spring-boot-starter-security`); Plone→Operaton REST calls keep the custom ed25519-JWT filter. docker-compose has been retired.
3. **Plone 5 Classic → Plone 6, Cookieplone-aligned.** Buildout/`setup.py` replaced by `pyproject.toml` (hatchling) + root `Makefile`; tests run under `pytest` (pytest-plone + gocept.pytestlayer over the classic layers); ruff/pre-commit/towncrier; modern GitHub Actions.
4. **Rollup → Vite, plus a modeler control panel.** The frontend moved out of `browser/static/` into a top-level `frontend-classic/` package built by `frontend-classic/build.mjs`. New REST services (`@bpmproxy-deploy`, `@bpmproxy-deployments`) and an optional `collective.bpmproxy.modeler` add-on provide a BPMN/DMN/Form modeler control panel that deploys straight to Operaton. `scripts/e2e_smoke.py` drives it in a real browser (`make e2e`).

### High-Level Features

- **BPM Proxy content type** — Publish a Camunda BPMN process as a Plone page. Users start process instances and complete tasks via Camunda Forms rendered inside Plone.
- **Task portlet** — Lists available user tasks from running Camunda processes (all or filtered by context/process).
- **Signal portlet** — Button to broadcast a named BPMN signal to Camunda from any Plone page, with JSON payload support.
- **Content rule action** — Automatically sends BPMN signals to Camunda in response to Plone workflow events (published, submitted, retracted, rejected, deleted, modified).
- **Plone form mapping** — Maps Plone `++add++` and `++edit++` forms as Camunda user task forms. Completing a Plone add/edit form automatically completes the corresponding Camunda task.
- **File attachments** — `Bpm Attachments` and `Bpm Attachment` content types allow file uploads scoped to specific process instances with dynamic security.
- **Multi-tenancy** — Tenant IDs configurable per Plone site via the configuration registry.
- **Anonymous user support** — Anonymous visitors get UUID-based pseudo-identities for interacting with processes.
- **BPMN diagram viewer** — Optional interactive BPMN 2.0 diagram display with current-task highlighting using `bpmn-js`.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│                Plone CMS                     │
│                                              │
│  ┌────────────────┐  ┌────────────────────┐  │
│  │  BPM Proxy     │  │  Content Rules     │  │
│  │  Content Type  │  │  (BpmSignalAction) │  │
│  └──────┬─────────┘  └────────┬───────────┘  │
│         │                     │              │
│  ┌──────▼─────────────────────▼───────────┐  │
│  │  Views: @@view, @@bpm-task             │  │
│  │  Portlets: Tasks, Signal               │  │
│  │  Viewlets: Attachments, Tasks          │  │
│  └──────────────────┬─────────────────────┘  │
│  ┌──────────────────▼─────────────────────┐  │
│  │  client.py  (generic-camunda-client)   │  │
│  │  JWT signed with ed25519 private key   │  │
│  └──────────────────┬─────────────────────┘  │
│  ┌──────────────────▼─────────────────────┐  │
│  │  utils.py  (form prep, validation,     │  │
│  │  variable inference, side-effect mgr)  │  │
│  └──────────────────┬─────────────────────┘  │
└─────────────────────┼────────────────────────┘
                      │ HTTP + JWT Bearer Token
                      ▼
┌──────────────────────────────────────────────┐
│         Operaton (Camunda 7 fork)            │
│         (Spring Boot / Java 17)              │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ JWTAuthenticationProvider              │  │
│  │ JWTIdentityService                     │  │
│  │ (verifies JWT, maps Plone users/       │  │
│  │  groups/tenants into Operaton identity)│  │
│  └────────────────────────────────────────┘  │
│                                              │
│  REST API: /engine-rest  (port 8081)         │
│  Cockpit:  /camunda      (port 8081)         │
│  Database: PostgreSQL                        │
└──────────────────────────────────────────────┘
```

### Authentication Flow

**Plone → Operaton REST (`/engine-rest/*`), all profiles:**

1. Plone signs a JWT with an **ed25519 private key** containing `sub` (userId), `groups`, `tenant_ids`, and a 1-hour expiration.
2. The JWT is sent as a `Bearer` token in HTTP requests to Operaton's REST API via `generic-camunda-client`.
3. Operaton's bundled **JWTAuthenticationProvider** (custom Java plugin) verifies the JWT with the corresponding **ed25519 public key** and maps the claims into Operaton's native identity system.

**Operaton WebApps (Cockpit/Tasklist/Admin/Welcome), `oauth2` Spring profile:**

1. Browser access to `/operaton/**` triggers Spring Security OAuth2 login (authorization code + PKCE) against Keycloak (`spring.security.oauth2.client.*` in `application.yml`; issuer overridable via `KEYCLOAK_ISSUER_URI`).
2. The Operaton OAuth2 identity provider (`operaton.bpm.oauth2.identity-provider`) maps `preferred_username` and the `groups` claim (Keycloak group-membership mapper) into the webapp identity; `operaton.bpm.oauth2.sso-logout` enables OIDC RP-initiated logout.
3. Engine authorization is enabled (`operaton.bpm.authorization.enabled`); group `camunda-admin` is granted engine-wide admin via `AdministratorAuthorizationPlugin` (matches `CAMUNDA_ADMIN_GROUP` on the Plone side). Without the `oauth2` profile the security starter backs off to a permit-all chain and the webapps keep Operaton's own form login.

### Business Key Linkage

Process instances are linked to Plone content via the Camunda `businessKey` field. The format is `{content_uuid}:{instance_uuid}`, binding a process instance to both a specific Plone content item and a unique attachment container.

---

## Directory Structure

```
collective.bpmproxy/
├── pyproject.toml                        # PEP 621 metadata (hatchling), pytest/ruff/towncrier config
├── Makefile                              # Developer tasks: install/test/lint/format/i18n/frontend-build/start
├── tox.ini                               # pip-based test matrix (py310–313 × Plone 6.1, applies Plone's constraints URL directly)
├── uv.lock                               # uv project lockfile (`make lock` to regenerate)
├── .pre-commit-config.yaml               # Ruff hooks
├── devenv.nix / devenv.yaml              # devenv.sh environment: postgres, keycloak, mailpit, operaton
├── devenv/keycloak/realm-plone.json      # Keycloak dev realm: client "operaton", group camunda-admin, users
├── frontend-classic/                     # Vite sources + build.mjs for the Classic UI bundles
├── frontend/                             # Placeholder for future Volto add-on (README documents REST needs)
├── scripts/                              # bootstrap_site.py (dev site), e2e_smoke.py (browser smoke test)
├── news/                                 # towncrier changelog fragments
├── README.md                             # Comprehensive user documentation
├── CHANGES.rst / CONTRIBUTORS.rst / DEVELOP.rst
├── LICENSE.GPL / LICENSE.rst             # GPLv2 license
│
├── fixture/operaton/                     # Custom Operaton container app (Spring Boot/Java), replaces old camunda/
│   ├── pom.xml                           # Maven: Spring Boot 4 + Operaton BOM 2.1.0 (artifact plone-operaton-app)
│   ├── Makefile                          # Container build targets (build/dist/push/fetch-plugins), Nix-driven
│   ├── flake.nix / flake.lock            # Nix reproducible packaging (nixpkgs release-26.05, mvn2nix from gitlab:vasara-bpm/mvn2nix)
│   ├── shell.nix / default.nix           # flake-compat shims for non-flake Nix users
│   ├── mvn2nix-lock.json                 # Generated Maven dependency lockfile consumed by flake.nix
│   ├── mvnw / mvnw.cmd                   # Maven wrapper
│   ├── src/main/java/com/example/camunda/  # Package not yet renamed to org.operaton-style naming
│   │   ├── Application.java             # @SpringBootApplication @EnableProcessApplication entry point
│   │   ├── ProcessEngineConfig.java     # Spring @Configuration: ProcessEnginePlugin bean (Spin, Connect, parse listeners, JWT), registers JWT filter on /engine-rest/*
│   │   ├── Engine.java                  # ProcessEngine factory + auto-migration (Spring @EventListener(PostDeployEvent))
│   │   ├── EngineBpmnParseListener.java # Custom BPMN parse listener registration
│   │   ├── EngineRequireDecisionListener.java  # DMN result validation
│   │   ├── EngineTaskBusinessKeyListener.java  # Copies businessKey to task variables
│   │   ├── JWTAuthenticationProvider.java      # JWT Bearer token verification (jakarta.servlet)
│   │   └── JWTIdentityService.java             # Maps JWT claims → Operaton identities
│   ├── src/main/resources/
│   │   ├── application.yml              # operaton.bpm.* + spring.datasource.* config, admin user, REST, history
│   │   ├── banner.txt                   # Spring Boot startup banner
│   │   ├── logback.xml                  # Logging configuration
│   │   ├── mail-config.properties       # Mail connector config
│   │   └── META-INF/resources/webjars/operaton/app/{admin,cockpit,tasklist,welcome}/  # Cockpit/Admin/Tasklist/Welcome plugin JS (from datakurre/operaton-cockpit-plugins, rewrite branch)
│   └── src/test/java/.../ApplicationTest.java  # Spring Boot context test (H2)
│
├── docs/
│   ├── conf.py                           # Sphinx documentation config
│   ├── index.rst                         # Sphinx index page
│   └── token-simulator-button.png        # Screenshot for README
│
├── examples/                             # Ready-to-deploy BPMN example processes
│   ├── approval-process/                 # Approval with DMN reviewer selection + email
│   ├── contact-form/                     # ML-powered contact form triage
│   ├── empire-insider/                   # GPT article generation + review assistant
│   ├── published-lifecycle/              # Published document lifecycle management
│   ├── request-for-quote/                # Quote request with DMN options
│   ├── editor-bot/                       # Robocorp RPA bot: OpenAI/DALL-E integration
│   ├── plone-bot/                        # Robocorp RPA bot: Plone REST API operations
│   └── ClassificationRobot.zip           # ML classification bot archive
│
├── .github/workflows/plone-package.yml   # GitHub Actions CI
├── .gitlab-ci.yml                        # GitLab CI pipeline
├── .travis.yml                           # Travis CI (legacy)
│
└── src/collective/bpmproxy/              # ← Main Python package
    ├── __init__.py                       # i18n MessageFactory
    ├── client.py                         # Camunda REST API client (JWT, generic-camunda-client)
    ├── utils.py                          # Form preparation, validation, variable inference,
    │                                     #   SideEffectDataManager, parent traversal
    ├── interfaces.py                     # Constants, enums, browser layer interface
    ├── configure.zcml                    # Root ZCML wiring
    ├── permissions.zcml                  # Custom permission definitions
    ├── setuphandlers.py                  # Post-install: camunda-admin group, registry config
    ├── testing.py                        # Plone test layers and fixtures
    │
    ├── content/                          # Dexterity content type schemas
    │   ├── bpm_proxy.py                  # IBpmProxy schema (process key, diagram, attachments, vars)
    │   ├── bpm_attachments.py            # IBpmAttachments marker (folder container)
    │   └── bpm_attachment.py             # IBpmAttachment schema (file upload)
    │
    ├── views/                            # Browser views (main UI logic)
    │   ├── bpm_form_view.py              # BpmProxyStartFormView + BpmProxyTaskFormView
    │   ├── bpm_form_view.pt              # Shared TAL template for forms + diagram
    │   ├── bpm_attachments_view.py       # Task attachment upload routing
    │   ├── bpm_attachments_listing.py    # Attachment listing view
    │   ├── bpm_attachments_orphans_view.py  # Orphan attachment finder (admin only)
    │   └── configure.zcml                # View URL registrations
    │
    ├── portlets/                         # Plone portlets
    │   ├── tasks.py                      # TasksPortlet + RedirectView (task list + routing)
    │   ├── tasks.pt                      # Tasks portlet template
    │   ├── signal.py                     # SignalPortlet + SignalForm (button to fire signals)
    │   └── configure.zcml                # Portlet registrations
    │
    ├── actions/                          # Content rule actions
    │   ├── signal.py                     # BpmSignalAction + executor (JSON payload, interpolation)
    │   ├── templates/signal.pt           # Action configuration form template
    │   └── configure.zcml                # Action registration
    │
    ├── adapters/                         # Zope adapters
    │   ├── security.py                   # AttachmentsLocalRoleProvider (dynamic Contributor/Editor)
    │   ├── substitutions.py              # String substitutions: ${uuid}, ${parent_uuid}, ${came_from}
    │   ├── patterns.py                   # PatternsSettings for pat-code-editor
    │   └── configure.zcml                # Adapter registrations
    │
    ├── subscribers/                      # Event subscribers
    │   ├── tasks.py                      # Auto-complete tasks on content add/edit
    │   └── configure.zcml                # Subscriber registrations
    │
    ├── viewlets/                         # Plone viewlets
    │   ├── bpm_attachments_viewlet.py    # Shows attachment list on task form
    │   ├── bpm_attachments_viewlet.pt    # Attachment viewlet template
    │   ├── bpm_attachments_tasks_viewlet.py  # Shows tasks on attachment containers
    │   ├── bpm_attachments_tasks_viewlet.pt  # Tasks viewlet template
    │   ├── bpm_attachments_common.py     # Shared viewlet utilities
    │   └── configure.zcml                # Viewlet registrations
    │
    ├── vocabularies/                     # Dynamic Zope vocabularies
    │   ├── available_process_definitions.py  # Queries Camunda for deployed processes
    │   ├── task_attachments.py           # Lists attachments in current task context
    │   └── configure.zcml                # Vocabulary factory registrations
    │
    ├── browser/                          # Browser resources
    │   ├── configure.zcml                # Browser layer, jbot, static resource registration
    │   ├── overrides/                    # z3c.jbot template overrides
    │   ├── controlpanel.py               # BPMN/DMN deployments control panel view
    │   ├── controlpanel.pt               # ... and its template (tabs + deployments table)
    │   └── static/                       # Build output of frontend-classic/ (committed)
    │       ├── form.js / form.css        # Camunda Forms viewer, on Bpm Proxy views
    │       ├── diagram.js / diagram.css  # BPMN diagram viewer
    │       └── modeler.js / modeler.css  # BPMN + DMN modelers and form playground
    │
    ├── profiles/                         # GenericSetup profiles
    │   ├── default/                      # Install profile
    │   │   ├── metadata.xml              # Version 1003, dependencies
    │   │   ├── browserlayer.xml          # Register ICollectiveBpmproxyLayer
    │   │   ├── types.xml                 # Content type registrations
    │   │   ├── types/                    # FTI definitions
    │   │   │   ├── Bpm_Proxy.xml
    │   │   │   ├── Bpm_Attachment.xml
    │   │   │   └── Bpm_Attachments.xml
    │   │   ├── registry/
    │   │   │   ├── main.xml              # tenant_ids registry record
    │   │   │   ├── bundles.xml           # JS/CSS resource bundle registration
    │   │   │   └── plone.xml             # Plone registry overrides
    │   │   ├── contentrules.xml          # 7 predefined BPMN signal content rules
    │   │   ├── rolemap.xml              # Permission → role mappings
    │   │   ├── portlets.xml             # Portlet registrations
    │   │   ├── catalog.xml              # Catalog indexes
    │   │   ├── workflows.xml            # Workflow bindings
    │   │   └── workflows/bpm_attachments_workflow/definition.xml
    │   └── uninstall/
    │       └── browserlayer.xml          # Remove browser layer
    │
    ├── locales/                          # i18n translations
    │   ├── collective.bpmproxy.pot       # Message catalog template
    │   ├── en/LC_MESSAGES/               # English translations
    │   └── update.py / update.sh         # Translation extraction scripts
    │
    └── tests/                            # Test suite
        ├── test_setup.py                 # Install/uninstall integration tests
        ├── test_ct_bpm_proxy.py          # BPM Proxy content type tests
        ├── test_ct_bpm_attachment.py     # BPM Attachment tests
        ├── test_ct_bpm_attachments.py    # BPM Attachments container tests
        ├── test_tasks.py                 # Task subscriber tests
        ├── test_view_view.py             # View rendering tests
        ├── test_viewlet_bpm_attachments_viewlet.py  # Viewlet tests
        ├── test_vocab_available_process_definitions.py  # Vocabulary tests
        ├── test_robot.py                 # Robot Framework runner
        └── robot/                        # Robot Framework acceptance tests
            ├── test_ct_bpm_proxy.robot
            ├── test_ct_bpm_attachment.robot
            ├── test_ct_bpm_attachments.robot
            └── test_example.robot
```

---

## Key Modules Reference

### `client.py` — Camunda REST API Client

Central module wrapping `generic-camunda-client` with JWT authentication. All functions automatically inject the current Plone user's identity into JWT tokens.

| Function | Purpose |
|---|---|
| `get_api_url()` | Returns Camunda REST API URL from `CAMUNDA_API_URL` env var |
| `get_token(username, groups, tenant_ids)` | Creates EdDSA JWT with 1-hour expiry |
| `get_authorization()` | Returns `Bearer <jwt>` for current Plone user (or anonymous UUID) |
| `camunda_client()` | Context manager yielding an authenticated API client |
| `camunda_admin_client(username, tenant_ids)` | Context manager yielding a `camunda-admin` privileged client |
| `get_start_form(client, definition_key, ...)` | Fetches deployed Camunda form + prepares it with defaults |
| `get_task_form(client, task_id, ...)` | Fetches task form + prepares with current variables |
| `get_available_tasks(client, context_key, attachments_key, for_display)` | Queries tasks, filtered by business key, with optional display name resolution |
| `get_next_tasks(client, process_id)` | Gets tasks for a process instance (for post-submit redirect) |
| `submit_start_form(client, definition_key, business_key, form_variables, process_variables, context)` | Starts process with string-interpolated variables |
| `submit_task_form(client, task_id, form_variables)` | Completes a task with submitted data |
| `get_task_variables(client, task_id)` | Gets all variables (with special Json type handling) |
| `get_diagram_xml(client, definition_id, definition_key, tenant_id)` | Returns BPMN 2.0 XML for diagram rendering |

**Environment Variables:**
- `CAMUNDA_API_URL` — Camunda REST API URL (default: `http://localhost:8081/engine-rest`)
- `CAMUNDA_API_PRIVATE_KEY` — Path to ed25519 private key PEM, or the key content itself

---

### `utils.py` — Utilities

| Function/Class | Purpose |
|---|---|
| `get_tenant_ids()` | Reads `collective.bpmproxy.tenant_ids` from Plone registry |
| `infer_variable(value)` / `infer_variables(data)` | Converts Python values to Camunda typed variables (Json, Boolean, Integer, Date, String). Includes ISO date/time parsing. |
| `flatten_variables(variables)` | Converts Camunda variable objects back to flat Python dict with date formatting |
| `prepare_camunda_form(schema_json, default_data, default_values, context)` | Processes a Camunda form JSON schema: applies string interpolation, resolves Plone vocabulary lookups (via `properties.vocabulary`), populates defaults. Returns `(data, options, schema)` tuple. |
| `validate_camunda_form(data_json, schema_json, context)` | Server-side validation: required, pattern, min/max value, min/max length, vocabulary membership |
| `interpolate(value, interpolator)` | Recursively applies `plone.stringinterp` substitutions |
| `parents(context, iface)` | Generator walking the Acquisition chain, optionally filtering by interface |
| `SideEffectDataManager` | `IDataManager` implementation for deferring Camunda API calls to transaction `tpc_finish` phase. Uses `ThreadPoolExecutor` to avoid blocking on commit. Prevents premature API calls if transaction rolls back. |
| `is_valid_uuid(uuid_to_test)` | UUID v4 format validation |

---

### `interfaces.py` — Constants and Interfaces

| Symbol | Value/Type | Purpose |
|---|---|---|
| `ICollectiveBpmproxyLayer` | Browser layer interface | Scopes views/portlets to installed add-on |
| `CAMUNDA_API_URL_ENV` | `"CAMUNDA_API_URL"` | Environment variable name |
| `CAMUNDA_API_URL_DEFAULT` | `"http://localhost:8081/engine-rest"` | Default API URL |
| `CAMUNDA_API_PRIVATE_KEY_ENV` | `"CAMUNDA_API_PRIVATE_KEY"` | Environment variable name |
| `CAMUNDA_ADMIN_USER` | `"admin"` | Admin username for privileged calls |
| `CAMUNDA_ADMIN_GROUP` | `"camunda-admin"` | Camunda admin group ID |
| `PLONE_ADMIN_GROUP` | `"Administrators"` | Plone admin group |
| `ANONYMOUS_USER_PREFIX` | `"anonymous-"` | Prefix for anonymous user IDs |
| `ANONYMOUS_USER_ANNOTATION_KEY` | `"collective.bpmproxy.anonymous"` | Request annotation for anonymous tokens |
| `BUSINESS_KEY_VARIABLE_NAME` | `"businessKey"` | Camunda task variable injected by engine listener |
| `FORM_DATA_KEY` | `"collective-bpmproxy-form-data"` | HTML form field name for submitted JSON data |
| `PLONE_TASK_VIEW` | `"@@bpm-task"` | URL segment for task form view |
| `PENDING_TASKS_MAX_RESULTS` | `25` | Max tasks returned in unfiltered queries |
| `HTTPMethod` | Enum class | `GET`, `POST` |
| `PloneNotificationLevel` | Enum class | `INFO`, `WARN`, `ERROR` |

---

### `content/` — Dexterity Content Types

**`IBpmProxy`** (`bpm_proxy.py`) — Main content type for publishing processes:

| Field | Type | Purpose |
|---|---|---|
| `process_definition_key` | `Choice` | Selects a Camunda process (vocabulary: `collective.bpmproxy.AvailableProcessDefinitions`) |
| `diagram_enabled` | `Bool` | Toggle interactive BPMN diagram display |
| `attachments_enabled` | `Bool` | Toggle file attachment support per task |
| `process_variables` | `JSONField` | Initial variables sent when starting processes. Values support `plone.stringinterp` substitutions (default: `{"portalUrl": "${portal_url}"}`) |
| `default_values` | `JSONField` | Default form field values. Supports substitutions (default: `{"authorEmail": "${user_email}", "authorFullName": "${user_fullname}"}`) |

**`IBpmAttachments`** (`bpm_attachments.py`) — Folder-like container scoped to a process instance (by UUID). Uses `IFolder` marker.

**`IBpmAttachment`** (`bpm_attachment.py`) — File upload schema with `title`, `description`, and `file` (NamedBlobFile).

---

### `views/` — Browser Views

| View | URL Pattern | For | Purpose |
|---|---|---|---|
| `BpmProxyStartFormView` | `@@view` | `IBpmProxy` | Default view. GET: renders start form + task list + optional diagram. POST: validates, starts process, redirects to first task. |
| `BpmProxyTaskFormView` | `@@bpm-task/{task_id}` | `IUUIDAware` | Traversable view. GET: renders task form + variables. POST: validates, completes task, redirects to next task or context. Supports `@@edit` and `++add++` form key delegation. |
| `BpmProxyNavigationBreadcrumbs` | `@@breadcrumbs_view` | `IUUIDAware` | Extends breadcrumbs to include task title when viewing a task. |
| `BpmProxyTaskAttachmentsView` | `@@add-attachment` | `BpmProxyTaskFormView` | Lazily creates attachment container (with role blocking), redirects to `++add++Bpm Attachment`. |
| `AttachmentsListing` | `@@contentlistings` / `@@folderListing` | `IBpmAttachments` | Folder listing for attachment containers. |
| `BpmAttachmentsOrphansView` | `@@bpm-proxy-orphan-attachments` | `ISiteRoot` | Returns JSON list of orphan attachment containers (requires `camunda-admin` group). |

---

### `portlets/` — Plone Portlets

**TasksPortlet** (`tasks.py`):
- Displays pending BPM tasks filtered by context UUID and/or process definition key.
- Includes `RedirectView` (`@@redirect-to-bpm-task/{task_id}`) that resolves a task's business key to a Plone URL and redirects.

**SignalPortlet** (`signal.py`):
- Renders a z3c.form button that fires a BPMN signal with interpolated JSON payload.
- After signal dispatch, checks for newly created tasks and redirects to first available.

---

### `actions/` — Content Rule Actions

**`BpmSignalAction`** (`signal.py`):
- Registered as `plone.actions.BpmSignal`.
- Schema: `name` (signal name, supports `${uuid}` interpolation), `payload` (JSON with substitution variables).
- Executor defers signal dispatch to `tpc_finish` via `SideEffectDataManager`.
- Sends signals per tenant and also without tenant ID.
- Has dedicated add/edit form views with custom template.

---

### `adapters/` — Zope Adapters

**`AttachmentsLocalRoleProvider`** (`security.py`):
- Adapts `IBpmAttachments`.
- Dynamically grants `Contributor` and `Editor` roles to users who have active Camunda tasks on the parent BPM Proxy that reference the specific attachment container.
- Results are per-request cached via `plone.memoize`.

**String Substitutions** (`substitutions.py`):
- `${uuid}` — Content UUID
- `${parent_uuid}` — Parent content UUID
- `${came_from}` — Sanitized `came_from` request parameter (must be within portal)

**`PatternsSettings`** (`patterns.py`):
- Configures `pat-code-editor` widget attributes for JSONField inputs.

---

### `subscribers/` — Event Subscribers

**`completeEditTask`** (`tasks.py`):
- Listens for `IObjectModifiedEvent` on Dexterity content.
- If a Camunda task has `form_key == "@@edit"` and is associated with the modified object, it auto-completes the task.
- Uses `SideEffectDataManager` to defer completion to transaction commit.

**`completeAddTask`** (`tasks.py`):
- Listens for `IObjectAddedEvent`.
- If a Camunda task has `form_key == "++add++{portal_type}"` matching the added object, it auto-completes the task.

---

### `viewlets/` — Plone Viewlets

**`BpmAttachmentsViewlet`**: Displays attachment list on task form views when `attachments_enabled` is true.

**`BpmAttachmentsTasksViewlet`**: Displays available tasks on attachment container views, with links to the parent BPM Proxy's task view.

---

### `vocabularies/` — Dynamic Vocabularies

**`AvailableProcessDefinitions`** (named `collective.bpmproxy.AvailableProcessDefinitions`):
- Queries Camunda for all latest process definitions, filtered by configured tenant IDs.
- Token format: `{key}:{tenant_id}` (or just `{key}` if no tenant).

**`TaskAttachments`** (named `collective.bpmproxy.TaskAttachments`):
- Lists attachments in the current task's attachment container.

---

### `frontend-classic/` — Frontend Bundles

Sources live in `frontend-classic/src/`; `frontend-classic/build.mjs` (Vite's JS
API) writes the output into `browser/static/`, which is committed so the sdist
ships working resources. `make frontend-build` / `make frontend-watch`.

**Three entries, each a self-contained IIFE.** Plone's resource registry renders
bundles as plain `<script src>` — there is no way to ask it for
`type="module"` — so an ES module entry would die with a SyntaxError, and shared
chunks could not be loaded at all. Each entry therefore inlines its
dependencies, `base: './'` keeps asset URLs relative, and `build.mjs` drops the
EOT/SVG font faces library mode would otherwise inline as unusable data URIs.
Library mode also does not substitute `process.env`, so `build.mjs` defines it.

| Entry | Source | Loaded by |
|---|---|---|
| `form` | `src/form.ts` | Bpm Proxy views, via the `bpmproxy_form_required` request flag |
| `diagram` | `src/diagram.ts` | ditto, `bpmproxy_diagram_required` |
| `modeler` | `src/controlpanel.ts` (BPMN modeler + DMN modeler + form playground) | the modeler control panel, `bpmproxy_modeler_required` |

1. **Form rendering** (`form.ts`): finds `#collective-bpmproxy-form`, instantiates a `Form` from `@bpmn-io/form-js-viewer`, imports schema + data from `data-*` attributes, and wires up submit to serialize form data into a hidden input.
2. **Diagram rendering** (`diagram.ts`): finds `#collective-bpmproxy-diagram`, instantiates a `NavigatedViewer` with `ModelingModule`, imports BPMN XML from `data-bpmn20_xml`, and optionally highlights the current task element in yellow via `data-element`.
3. **Modeling** (`modeler.ts`, `dmn.ts`, `form-playground.ts`): the control panel editors, each a no-op when its container element is absent. Deploying posts to `@bpmproxy-deploy`.

---

### `services/` — REST API

`plone.restapi` services on the site root, all requiring **`cmf.ManagePortal`**:
deleting a deployment cascades into its running process instances, and only
Plone administrators end up in the `camunda-admin` group whose JWT the engine
accepts for deployment.

| Service | Method | Purpose |
|---|---|---|
| `@bpmproxy-deploy` | POST | Deploy BPMN/DMN/Form XML (`{"xml": ..., "name": ...}`) |
| `@bpmproxy-deployments` | GET | List engine deployments |
| `@bpmproxy-deployments` | DELETE | Delete one deployment, cascading |

Browser calls must send `Accept: application/json`; plone.rest routes on that
header, and without it the request is an ordinary traversal and 404s.

---

## Configuration

### Plone Registry Keys

| Key | Type | Default | Purpose |
|---|---|---|---|
| `collective.bpmproxy.tenant_ids` | `List` of `TextLine` | Empty | Camunda multi-tenancy identifiers for this Plone site |

### Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `CAMUNDA_API_URL` | Yes | `http://localhost:8081/engine-rest` | Camunda Platform 7 REST API URL |
| `CAMUNDA_API_PRIVATE_KEY` | Yes | _(none)_ | Path to ed25519 private key PEM file (or raw key content) |

### Custom Permissions

| Permission | Granted To |
|---|---|
| `collective.bpmproxy: Add Bpm Proxy` | Contributor, Manager, Site Administrator |
| `collective.bpmproxy: Add Bpm Attachments` | Contributor, Manager, Site Administrator |

### Post-Install Setup

The `post_install` handler:
1. Creates a `camunda-admin` Plone group (member of `Administrators`).
2. Adds `Bpm Attachment` to `plone.types_use_view_action_in_listings`.

---

## Predefined Content Rules

Registered in `contentrules.xml`, these rules broadcast BPMN signals to Camunda:

| Rule ID | Title | Trigger | Signal Name |
|---|---|---|---|
| `collective-bpmproxy-published-any` | Published any | Workflow: publish/publish_externally/publish_internally | `plone-content-published` |
| `collective-bpmproxy-submitted-any` | Submitted any | Workflow: submit | `plone-content-submitted` |
| `collective-bpmproxy-published-one` | Published one | Workflow: publish/* | `plone-content-published:${uuid}` |
| `collective-bpmproxy-retracted-one` | Retracted one | Workflow: retract | `plone-content-retracted:${uuid}` |
| `collective-bpmproxy-rejected-one` | Rejected one | Workflow: reject | `plone-content-rejected:${uuid}` |
| `collective-bpmproxy-deleted-one` | Deleted one | `IObjectRemovedEvent` | `plone-content-deleted:${uuid}` |
| `collective-bpmproxy-modified-one` | Modified one | `IObjectModifiedEvent` | `plone-content-modified:${uuid}` |

All rules send payload: `{'uuid': '${uuid}', 'portalUrl': '${portal_url}'}`.

The `*-one` variants include `${uuid}` in the signal name, enabling per-object signal subscriptions in BPMN processes.

---

## devenv / Operaton Setup

### Services (`devenv.nix`)

Managed by [devenv](https://devenv.sh); `devenv up` starts:

| Process | Port | Purpose |
|---|---|---|
| `operaton` | `8081` | The Spring Boot app from `fixture/operaton/`, run via `./mvnw spring-boot:run` with `SPRING_PROFILES_ACTIVE=oauth2` and `PLONE_PUBLIC_KEY` pointing at the repo-root ed25519 public key. Waits for Keycloak to serve the realm before starting (issuer metadata is resolved at boot). |
| `keycloak` | `8082` | OIDC provider for the Operaton webapps. Imports realm `plone` from `devenv/keycloak/realm-plone.json` on startup (`export = true` allows exporting UI edits back). Admin console: `admin`/`admin` (master realm). |
| `postgres` | `5432` | Process state database (role `postgres`/`postgres` created via `initialScript`). |
| `mailpit` | `8025` (web), `1025` (SMTP) | Debug mail server (replaces mailhog). |

`devenv up` is wrapped by `make services` at the repo root. `devenv shell` additionally provides JDK 17 + Maven + Python, generates the ed25519 keypair if missing (`enterShell`), and exports `CAMUNDA_API_URL` / `CAMUNDA_API_PRIVATE_KEY` / `PLONE_PUBLIC_KEY` / `KEYCLOAK_ISSUER_URI`. Plone itself is started manually (`make start`, port 8080), which builds `backend/.venv` on first run.

`env` also pins `UV_PROJECT_ENVIRONMENT = backend/.venv`, `UV_PYTHON_DOWNLOADS = never`, `UV_PYTHON_PREFERENCE = system` (matching [`plone/2025.ploneconf.org`](https://github.com/plone/2025.ploneconf.org/blob/main/backend/devenv.nix)) — without this, `languages.python.uv` defaults the venv to a devenv-internal shared location that gets reprovisioned between shell sessions, which previously caused console-scripts (`mkwsgiinstance`, etc.) to intermittently go missing while package metadata still looked satisfied.

**Keycloak dev realm** (`devenv/keycloak/realm-plone.json`): confidential client `operaton` (secret `operaton-secret`, redirect URIs `http://localhost:8081/*`, post-logout redirect configured) with a client-level `oidc-group-membership-mapper` emitting group names into a `groups` claim (`full.path=false`); group `camunda-admin`; users `admin`/`admin` (member of `camunda-admin`) and `user`/`user` (no groups → welcome app only).

### Custom Operaton Application (`fixture/operaton/`)

A **Spring Boot 4** (`spring-boot.version = 4.0.6`) Java 17 application on **Operaton 2.1.0** (imports `org.operaton.bpm:operaton-bom` alongside the `spring-boot-dependencies` BOM), replacing the old Micronaut/Camunda 7.20.0 app. Maven artifact `plone-operaton-app` version `0.1` (must match `flake.nix` `packages.jar`).

**Engine Plugins:**
- `ProcessEngineConfig.java` — Spring `@Configuration` exposing: a `ProcessEnginePlugin` bean that registers custom parse listeners and `JWTIdentityService`; an `AdministratorAuthorizationPlugin` bean granting engine-wide admin to group `camunda-admin`; and a `FilterRegistrationBean` registering `JWTAuthenticationProvider` on `/engine-rest/*`.
- `Engine.java` — Runs automatic process instance migration when process definitions are redeployed (Spring `@EventListener(PostDeployEvent.class)`), sets up default authorizations.
- `EngineTaskBusinessKeyListener.java` — Copies `businessKey` from the execution to a local task variable on user task creation.
- `EngineRequireDecisionListener.java` — Forces DMN business rule tasks to return non-null/non-empty results (throws `BpmnError "DecisionError"` otherwise). Still keeps the legacy `http://camunda.org/schema/1.0/bpmn` namespace for backwards compatibility.

**Security:**
- `JWTAuthenticationProvider.java` — Verifies `Authorization: Bearer <token>` using ed25519 public key (BouncyCastle EdDSA) on `/engine-rest/*`. Uses `jakarta.servlet`.
- `JWTIdentityService.java` — Extracts `sub`, `groups`, `tenant_ids` from JWT claims and sets Operaton's transient authentication.
- `operaton-bpm-spring-boot-starter-security` — under the `oauth2` Spring profile, OIDC login for the webapps (client registration `keycloak`, `operaton.bpm.oauth2.identity-provider` with `group-name-attribute: groups`, SSO logout). Without the profile the starter's `OperatonBpmSpringSecurityDisableAutoConfiguration` installs a permit-all chain — do **not** add a custom `SecurityFilterChain` bean for that case, it conflicts.

**Configuration (`application.yml`):**
- Config root is `operaton.bpm.*`
- Admin: `admin`/`admin`, firstName `Operaton`
- `operaton.bpm.authorization.enabled: true` (note: `generic-properties.properties.authorization-enabled` is silently ignored by the starter — don't move it back)
- REST API: `/engine-rest`; webapps: `/operaton` (Operaton default)
- History: `full` with TTL `P7D`, batch cleanup window `22:00-06:00`
- `spring.datasource.*` PostgreSQL datasource
- A second profile-scoped document (`spring.config.activate.on-profile: oauth2`) holds the OAuth2 client registration (env overrides: `KEYCLOAK_ISSUER_URI`, `KEYCLOAK_CLIENT_SECRET`, `OPERATON_POST_LOGOUT_REDIRECT_URI`)

**Maven Dependencies:** `operaton-bpm-spring-boot-starter-webapp`/`-starter-rest`/`-starter-security`, `spring-boot-starter-web`, `operaton-spin-core`/`operaton-spin-dataformat-json-jackson`, `operaton-engine-plugin-spin`/`-connect`, `postgresql`, BouncyCastle (`bcpkix-jdk15to18`), Nimbus JOSE JWT, `operaton-bpm-junit5` + H2 (test).

**Cockpit/Admin/Tasklist/Welcome UI:** The old bundled Camunda 7 webapp resources (~22MB) were removed; plugin JS for these apps is fetched from `datakurre/operaton-cockpit-plugins` (rewrite branch) via the `fetch-plugins` Makefile target. The `*-nologin.js` plugins hide the built-in sign-in form, which is consistent with OIDC login.

### Build & Packaging (Nix)

`fixture/operaton/flake.nix` defines the reproducible build/packaging for this app:
- `nixpkgs` pinned to `release-26.05` (plus a `nixpkgs-unstable` input), `flake-utils`, `flake-compat`.
- `mvn2nix` sourced from **`gitlab:vasara-bpm/mvn2nix`** — used with `pkgs.buildMavenRepositoryFromLockFile` against `mvn2nix-lock.json` to build an offline Maven repo, so `mvn package` needs no network access.
- `packages.jar` — the built Spring Boot jar; `packages.default` — a launcher script wrapping the jar with `temurin-jre-bin-17`; `packages.image` — a `dockerTools.streamLayeredImage` container (`datakurre/plone-operaton`).
- `devShells.default` — `jdk17`, `maven`, the `mvn2nix` CLI itself, plus `jq`, `entr`, `poetry`, `cachix`, `jfrog-cli`.
- `Makefile` wraps this: `make build` (`nix build`), `make dist`/`make push` (build+tag+push the container image via podman), `make fetch-plugins` (Cockpit/Admin/Tasklist/Welcome JS), and a `nix-%` pattern rule to run any target inside `nix develop`.

**Important:** after any `pom.xml` change, regenerate the lockfile (`nix develop --command make mvn2nix-lock.json` in `fixture/operaton/`) or `nix build`/the container image will fail.

The repo-level dev environment is `devenv.nix` at the root (see [devenv / Operaton Setup](#devenv--operaton-setup)); the app-scoped `fixture/operaton/flake.nix` remains for building/packaging the container image.

---

## Dependencies

### Runtime (Python)

| Package | Purpose |
|---|---|
| `generic-camunda-client` | Type-safe Python client for Camunda REST API |
| `pyjwt` | JWT creation (EdDSA algorithm) |
| `cryptography` | Ed25519 key loading |
| `plone.api >= 1.8.4` | Plone programmatic API |
| `plone.app.caching` | `doNotCache` for form views |
| `plone.app.dexterity` | Dexterity content type framework |
| `plone.restapi` | RESTful API for Plone |
| `python-dateutil` | ISO date parsing for variable inference |
| `pytz` | Timezone conversions |
| `z3c.jbot` | Template overrides |

### Test

| Package | Purpose |
|---|---|
| `pytest` / `pytest-cov` | Test runner and coverage |
| `pytest-plone` | Pytest fixtures over Plone test layers |
| `gocept.pytestlayer` | Lets pytest run classic layer-based unittest suites |
| `plone.app.testing` | Test fixtures and layers |
| `plone.testing >= 5.0.0` | Base testing infrastructure |
| `plone.app.contenttypes` | Default content types for testing |
| `plone.app.robotframework[debug]` | Robot Framework acceptance tests |

### Dev tooling (`[dependency-groups].dev`)

| Package | Purpose |
|---|---|
| `ruff` | Linting and formatting (`make lint` / `make format`) |
| `i18ndude` | Locale extraction (`make i18n`) |

### Frontend (npm)

| Package | Purpose |
|---|---|
| `@bpmn-io/form-js-viewer` | Camunda Form JSON renderer |
| `bpmn-js` | BPMN 2.0 diagram viewer |
| `vite` (library mode, IIFE) | Module bundler |
| `typescript` | TypeScript compiler |

---

## Testing

### Test Suite

| Test File | Coverage |
|---|---|
| `test_setup.py` | Add-on install/uninstall, browser layer registration |
| `test_ct_bpm_proxy.py` | BPM Proxy content type CRUD |
| `test_ct_bpm_attachment.py` | BPM Attachment content type |
| `test_ct_bpm_attachments.py` | BPM Attachments container |
| `test_tasks.py` | Task event subscribers |
| `test_view_view.py` | View rendering |
| `test_viewlet_bpm_attachments_viewlet.py` | Viewlet behavior |
| `test_vocab_available_process_definitions.py` | Vocabulary factory |
| `test_robot.py` | Robot Framework runner (excluded from pytest collection; known follow-up) |
| `robot/*.robot` | Browser acceptance tests |

The classic zope test layers in `testing.py` are reused: `gocept.pytestlayer` lets pytest run the existing `unittest`-style tests, while `tests/conftest.py` exposes `pytest-plone` fixtures for new pytest-style tests.

### Running Tests

```bash
# Default addopts (pyproject.toml) already exclude tests marked "operaton",
# so plain `make test` only runs the offline unit tests.
make test

# Start all services (Operaton, Keycloak, Postgres) in the background
devenv processes up -d
# (Or use 'devenv up &' if 'processes up -d' times out)

# Run full test suite (waits for Operaton to become ready automatically)
devenv test

# Via make (from root or backend directory; uv resolves/installs on demand)
make test
make lint

# Directly (from backend directory)
cd backend
uv run pytest

# With coverage (from backend directory)
cd backend
uv run pytest --cov=src

# Full matrix (py310–313, from backend directory; applies Plone's official
# constraints URL directly, independently of uv.lock)
cd backend
tox
```

### CI/CD

- **GitHub Actions** (`.github/workflows/plone-package.yml`): `lint` (ruff via uvx), `test` (Python 3.10–3.13 matrix, `uv sync --extra test`, pytest), `build` (`uv build` + `twine check`). Triggers on `master`/`main`.

---

## Development Setup

Two terminals, both inside `make shell` (== `devenv shell`; installs
JDK/Maven/Python, generates the ed25519 keys if missing, exports
`CAMUNDA_API_URL` / `CAMUNDA_API_PRIVATE_KEY`):

```bash
# Terminal 1: start the services (PostgreSQL, Keycloak realm "plone", Mailpit, Operaton)
make shell
make services   # -> devenv up

# Terminal 2: uv-sync dependencies (if needed) and start Plone (port 8080)
make shell
make start

# Then: install via Plone's add-on control panel, deploy BPMN diagrams via Modeler
# (Operaton Cockpit: http://localhost:8081/operaton — login admin/admin via Keycloak)
```

`make start` is idempotent: `uv sync` no-ops quickly once dependencies are
current, and the Plone instance is only created once. `devenv.nix` pins
`UV_PROJECT_ENVIRONMENT` to `backend/.venv` (see [devenv / Operaton
Setup](#devenv--operaton-setup)) — without that, `languages.python.uv`
would default it to a devenv-internal shared location that gets
reprovisioned between shell sessions, which is what previously caused
console-scripts like `mkwsgiinstance` to intermittently go missing.

Manual key generation (done automatically by `make shell`):

```bash
openssl genpkey -algorithm ed25519 -out ec-ed25519-priv-key.pem
openssl pkey -in ec-ed25519-priv-key.pem -pubout -out ec-ed25519-pub-key.pem
```

### Frontend Development

```bash
make frontend-build   # npm install + build into browser/static/ (committed)
make frontend-watch   # rebuild on change
```

### End-to-end smoke test

With the services and Plone running (`make services`, `make start`):

```bash
make bootstrap-site   # once, with Plone stopped: site + add-on + test users
make e2e              # scripts/e2e_smoke.py, screenshots into var/e2e
```

It drives a real browser through the control panel — bundles booting, the
modelers rendering, deploy/list/delete against the engine, the Bpm Proxy view's
form and diagram — and cleans up what it deploys. This is the check that catches
what the pytest suite cannot: a bundle that does not parse, a font that does not
decode, a fetch missing its `Accept` header.

---

## Examples

### Approval Process (`examples/approval-process/`)
DMN-based reviewer selection, email notifications, daily reminders, multi-outcome review (approve/decline/request-changes with 7-day timeout).

### Contact Form with ML Triage (`examples/contact-form/`)
Parallel processing: visitor thank-you + backend ML classification (spam/mood/topic), DMN team routing, manual triage fallback, classifier retraining.

### Empire Insider (`examples/empire-insider/`)
Two processes: (1) GPT-powered article scaffolding with DALL-E images, iterative review, Plone content creation. (2) Signal-triggered review assistant with GPT revision support and lifecycle signal monitoring.

### Published Document Lifecycle (`examples/published-lifecycle/`)
Post-publication management: social media sharing tasks, periodic content update prompts, daily status monitoring, automatic termination on unpublish.

### Request for Quote (`examples/request-for-quote/`)
DMN-driven option calculation, session timeout, parallel visitor/admin flows, email notification.

### Editor Bot (`examples/editor-bot/`)
Robocorp RPA bot: OpenAI article generation, title/keyword/description creation, DALL-E image generation.

### Plone Bot (`examples/plone-bot/`)
Robocorp RPA bot: Plone REST API operations (get/create/update content, workflow transitions, image upload).

---

## Key Design Decisions

1. **Proxy pattern** — Plone never exposes Camunda UI directly. All interaction is mediated through Plone views, ensuring consistent authentication, theming, and permissions.
2. **JWT-based trust with short-lived tokens** — Asymmetric key authentication avoids storing Camunda credentials. The EdDSA algorithm provides modern, compact signatures.
3. **Transaction-safe side effects** — Camunda API calls (signals, task completions from subscribers) are deferred to `tpc_finish` via `SideEffectDataManager`, preventing premature API calls if the Zope transaction rolls back.
4. **Dynamic security** — `AttachmentsLocalRoleProvider` queries Camunda in real-time to grant temporary upload permissions only to users with active tasks referencing the attachment container.
5. **Business key binding** — The `{content_uuid}:{instance_uuid}` pattern links Camunda process instances to Plone content while supporting multiple concurrent instances per content item.
6. **Form rendering delegation** — Camunda form JSON schemas are rendered client-side by `@bpmn-io/form-js-viewer`, keeping server-side logic minimal while supporting rich form interactions.
7. **String interpolation throughout** — Signal names, payloads, process variables, and form defaults all support `plone.stringinterp` substitutions (`${uuid}`, `${portal_url}`, `${user_email}`, etc.).
8. **Graceful anonymous support** — Anonymous users get stable UUID-based identities stored in request annotations, enabling public-facing workflows.
