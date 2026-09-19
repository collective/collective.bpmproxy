{ pkgs, lib, config, ... }:

# Development environment for collective.bpmproxy. Two terminals, both
# inside `make shell` (== devenv shell; toolchain: JDK 21, Maven, Python,
# CAMUNDA_* env set):
#
#   make services  # -> devenv up: postgres + keycloak (realm "plone") + mailpit + operaton
#   make start     # -> uv-syncs dependencies if needed, then starts Plone
#
# Plone picks up CAMUNDA_API_URL and CAMUNDA_API_PRIVATE_KEY from the shell.
#
# Ports: Plone 8080 (manual), Operaton 8081, Keycloak 8082,
#        PostgreSQL 5432, Mailpit SMTP 1025 / UI 8025.
{
  env = {
    CAMUNDA_API_URL = "http://localhost:8081/engine-rest";
    CAMUNDA_API_PRIVATE_KEY = "${config.env.DEVENV_ROOT}/ec-ed25519-priv-key.pem";
    PLONE_PUBLIC_KEY = "${config.env.DEVENV_ROOT}/ec-ed25519-pub-key.pem";
    KEYCLOAK_ISSUER_URI = "http://localhost:8082/realms/plone";

    # Point playwright at the nix-provided browsers instead of ~/.cache.
    PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "true";

    # Pin the project venv to a stable, project-local path (matches
    # plone/2025.ploneconf.org's devenv.nix). Without this,
    # languages.python.uv defaults UV_PROJECT_ENVIRONMENT to a
    # devenv-internal shared location that gets reprovisioned between
    # shell sessions: package metadata survives but console-scripts
    # (mkwsgiinstance, runwsgi, ...) can silently go missing between
    # `devenv shell` sessions, which is what caused backend/Makefile's
    # install target to need a self-healing --reinstall check.
    # languages.python's own module also sets this env var (to that
    # shared location), so ours needs mkForce to win instead of erroring
    # as a conflicting definition. It already sets UV_PYTHON_DOWNLOADS =
    # "never" and UV_PYTHON_PREFERENCE = "only-system" itself (matching
    # the nix-managed pkgs.python312 below), so no need to redeclare those.
    UV_PROJECT_ENVIRONMENT = lib.mkForce "${config.env.DEVENV_ROOT}/backend/.venv";
  };

  packages = [
    pkgs.openssl
    pkgs.jq
    pkgs.curl
    # Browsers for `make e2e` (see the e2e-smoke script below).
    pkgs.playwright-driver.browsers
  ];

  languages.java = {
    enable = true;
    jdk.package = pkgs.jdk21;
    maven.enable = true;
  };

  languages.python = {
    enable = true;
    package = pkgs.python312;
    uv.enable = true;
  };

  languages.javascript = {
    enable = true;
    npm.enable = true;
  };

  # `make e2e`. The nixpkgs playwright package is already paired with the
  # driver in playwright-driver.browsers, so `playwright install` (which
  # downloads from a CDN) is neither needed nor wanted.
  scripts.e2e-smoke.exec = ''
    exec ${pkgs.python312.withPackages (ps: [ ps.playwright ])}/bin/python \
      "$DEVENV_ROOT/scripts/e2e_smoke.py" "$@"
  '';

  # `make ui-test` / `make screenshots`. The browser test campaign in
  # scripts/uitest/, run as a module so its relative imports resolve; same
  # nixpkgs playwright as e2e-smoke, so `playwright install` is never needed.
  scripts.ui-test.exec = ''
    cd "$DEVENV_ROOT"
    exec ${pkgs.python312.withPackages (ps: [ ps.playwright ])}/bin/python \
      -m scripts.uitest "$@"
  '';

  # The documented runner for the recording scripts (docs/AGENTS.md), e.g.
  # `playwright-python scripts/e2e_request_for_quote.py`. Same nixpkgs
  # playwright as e2e-smoke, and runs from the repo root because those scripts
  # resolve examples/ and docs/ relatively.
  scripts.playwright-python.exec = ''
    cd "$DEVENV_ROOT"
    exec ${pkgs.python312.withPackages (ps: [ ps.playwright ])}/bin/python "$@"
  '';

  services.postgres = {
    enable = true;
    listen_addresses = "127.0.0.1";
    port = 5432;
    # fixture/operaton/src/main/resources/application.yml connects as
    # postgres/postgres to the "postgres" database over TCP.
    initialScript = ''
      CREATE ROLE postgres SUPERUSER LOGIN PASSWORD 'postgres';
    '';
  };

  services.keycloak = {
    enable = true;
    initialAdminPassword = "admin";
    settings = {
      http-port = 8082;
      hostname = "http://localhost:8082";
    };
    realms.plone = {
      path = "devenv/keycloak/realm-plone.json";
      import = true;
      # No `export = true`: that spawns a `keycloak-realm-export-all`
      # process gated on the `keycloak` process exiting, which never
      # happens under `devenv up`, so it just sits "waiting" forever.
      # The generic `keycloak-realm-export plone <file>` script (via
      # services.keycloak.scripts.exportRealm, default true) stays
      # available in the shell for manual export when needed.
    };
  };

  services.mailpit.enable = true;

  processes.operaton = {
    exec = ''
      set -e
      cd "$DEVENV_ROOT/fixture/operaton"
      # Spring resolves the OIDC issuer metadata at startup, so wait for
      # Keycloak to actually serve the realm.
      until curl -sf "$KEYCLOAK_ISSUER_URI" > /dev/null; do sleep 2; done
      export SPRING_PROFILES_ACTIVE=postgres,oauth2
      exec ./mvnw -Dmaven.repo.local="$DEVENV_ROOT/tmp/.m2/repository" spring-boot:run
    '';
    process-compose = {
      depends_on = {
        postgres.condition = "process_healthy";
        keycloak.condition = "process_healthy";
      };
      # Spring Boot startup (Maven download + boot) is slow, and without a
      # probe process-compose only ever reports "Running", never "Ready".
      readiness_probe = {
        http_get = {
          host = "localhost";
          scheme = "http";
          path = "/engine-rest/engine";
          port = 8081;
        };
        initial_delay_seconds = 10;
        period_seconds = 5;
        timeout_seconds = 2;
        failure_threshold = 60;
      };
    };
  };

  enterShell = ''
    if [ ! -f "$CAMUNDA_API_PRIVATE_KEY" ]; then
      echo "Generating ed25519 JWT signing key pair ..."
      openssl genpkey -algorithm ed25519 -out "$CAMUNDA_API_PRIVATE_KEY"
      openssl pkey -in "$CAMUNDA_API_PRIVATE_KEY" -pubout -out "$PLONE_PUBLIC_KEY"
    fi
  '';

  enterTest = ''
    echo "Waiting for Operaton to become ready..."
    until curl -sf "http://localhost:8081/engine-rest/engine" > /dev/null; do
      sleep 2
    done
    echo "Operaton is ready. Running backend tests..."
    cd backend && uv run pytest --cov=src
  '';
}
