"""Runner for the collective.bpmproxy browser test campaign.

    python -m scripts.uitest --no-shots           # fast assert-only (the fix loop)
    python -m scripts.uitest --check-docs         # write docs images + check drift
    python -m scripts.uitest --scenario portlets  # one area only

Assertions are always on. There is deliberately no mode that writes
screenshots without checking the page first: the whole point is that the
documentation can only be regenerated from a passing run.
"""

from . import fixtures
from . import shots as registry
from .harness import BASE_URL
from .harness import Session
import argparse
import importlib
import sys
import urllib.error
import urllib.request


# Order matters: install must run first, and the process-dependent areas need
# the deployments the earlier ones leave in place.
SCENARIOS = [
    "install",
    "modeler",
    "bpm_proxy",
    "tasks",
    "attachments",
    "portlets",
    "contentrules",
    "subscribers",
    "anonymous",
    "tenancy",
]

DOCS_DIR = "docs/user"
IMAGES_DIR = "docs/user/images"

REQUIRED = [
    ("Plone", BASE_URL),
    ("Operaton", "http://localhost:8081/engine-rest/engine"),
    ("Mailpit", "http://localhost:8025/"),
]

START_HINT = """
  Services not reachable. Start them with:

      devenv up -d                 # postgres, keycloak, mailpit, operaton
      make bootstrap-site          # once, with Plone stopped
      make start                   # Plone on :8080
"""


def reachable(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status < 500
    except urllib.error.HTTPError as exc:
        # 401 just means the endpoint wants credentials -- it is up.
        return exc.code < 500
    except Exception:
        return False


def preflight():
    down = [name for name, url in REQUIRED if not reachable(url)]
    if down:
        print(f"unreachable: {', '.join(down)}")
        print(START_HINT)
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=BASE_URL)
    parser.add_argument("--images", default=IMAGES_DIR)
    parser.add_argument("--docs", default=DOCS_DIR)
    parser.add_argument(
        "--no-shots",
        action="store_true",
        help="assert only; do not write screenshots",
    )
    parser.add_argument(
        "--check-docs",
        action="store_true",
        help="fail if docs/user and the shot registry have drifted apart",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=None,
        help="run only this scenario (repeatable)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="leave the created content and deployments in place",
    )
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    if not preflight():
        return 2

    selected = args.scenario or SCENARIOS
    unknown = [name for name in selected if name not in SCENARIOS]
    if unknown:
        print(f"unknown scenario(s): {', '.join(unknown)}")
        print(f"available: {', '.join(SCENARIOS)}")
        return 2

    base_url = args.url.rstrip("/")
    with Session(base_url, args.images, not args.no_shots, args.headed) as session:
        setup, _ = session.page("manager")
        setup.goto(base_url, wait_until="load")
        try:
            swept = fixtures.sweep(setup, base_url)
        except fixtures.EngineUnavailable as exc:
            print(f"\nENGINE UNAVAILABLE: {exc}")
            print("The Plone side is up but the engine is not usable. Check")
            print("`.devenv/run/processes/logs/operaton.stdout.log` -- most")
            print("often its PostgreSQL went away.")
            return 2
        print(
            f"swept {len(swept['content'])} content item(s), "
            f"{len(swept['deployments'])} deployment(s)"
        )

        for name in selected:
            module = importlib.import_module(f"{__package__}.scenarios.{name}")
            session.checks.section(module.TITLE)
            try:
                module.run(session)
            except Exception as exc:  # a crash is a failure, not an abort
                session.checks.check(
                    name, "scenario completed without raising", False, repr(exc)
                )
                import traceback

                traceback.print_exc()

        if not args.keep:
            fixtures.sweep(setup, base_url)

        checks = session.checks
        taken = session.taken

    print()
    problems = []

    if args.check_docs:
        problems = registry.check_docs(args.docs)
        missing = [
            shot.name
            for shot in registry.SHOTS
            if shot.name not in taken and (args.scenario is None)
        ]
        problems += [
            f"{name}: declared but never taken in this run" for name in missing
        ]
        for problem in problems:
            print(f"DOC DRIFT  {problem}")

    total = len(checks.results)
    if checks.failed:
        print(f"\n{len(checks.failed)} of {total} check(s) FAILED:")
        for _, case, name, detail in checks.failed:
            print(f"  {case}  {name}{f' -- {detail}' if detail else ''}")
        return 1
    if problems:
        print(f"\nall {total} checks passed, but the docs have drifted")
        return 1

    print(f"all {total} checks passed; {len(taken)} screenshot(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
