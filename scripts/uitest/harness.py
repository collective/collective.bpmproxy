"""Shared browser plumbing for the uitest scenarios.

Consolidates what scripts/e2e_smoke.py and scripts/e2e_renovation_project.py
had each grown their own copy of: result collection, per-page console and
network watching, authenticated contexts, and REST calls issued from inside an
authenticated page.
"""

from playwright.sync_api import sync_playwright
import base64
import json
import pathlib


# Full HD for every context, viewport and screenshot. The recordings in
# docs/AGENTS.md already mandate this size; keeping stills identical means the
# guide and the walkthrough videos look like the same product.
VIEWPORT = {"width": 1920, "height": 1080}

BASE_URL = "http://localhost:8080/Plone"
OPERATON = "http://localhost:8081"
MAILPIT = "http://localhost:8025"

# Seeded by scripts/bootstrap_site.py.
USERS = {
    "manager": ("manager", "manager"),  # Manager, member of camunda-admin
    "editor": ("editor", "editor"),  # Site Administrator, no engine rights
    "admin": ("admin", "admin"),  # Zope root
}

# Everything this suite creates is named with this prefix so a crashed run can
# be swept without touching anything a human made.
PREFIX = "uitest-"

# Screenshots are deterministic only if animations and the caret are gone.
QUIET_CSS = """
    *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        caret-color: transparent !important;
    }
    /* Every rendered timestamp. The toolbar's pat-display-time clock is
       written by JavaScript at page load, so without this no two runs ever
       produce the same bytes. visibility rather than display, to keep the
       layout identical. */
    time, .pat-display-time { visibility: hidden !important; }
"""


def basic_auth(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


class Checks:
    """Collects results so one failure does not hide the rest."""

    def __init__(self):
        self.results = []
        self.current = ""

    def section(self, name):
        self.current = name
        print(f"\n--- {name} ---")

    def check(self, case, name, condition, detail=""):
        ok = bool(condition)
        self.results.append((ok, case, name, detail))
        line = f"{'PASS' if ok else 'FAIL'}  {case}  {name}"
        if detail and not ok:
            line += f" -- {detail}"
        print(line)
        return ok

    @property
    def failed(self):
        return [r for r in self.results if not r[0]]


class PageWatcher:
    """Console errors, uncaught exceptions and bad responses, per page."""

    # Plone and third-party noise that is not ours to fix and would otherwise
    # fail every single scenario.
    IGNORE = (
        "favicon.ico",
        "Download the React DevTools",
    )

    def __init__(self, page):
        self.errors = []
        self.warnings = []
        self.failed_requests = []
        self.http_errors = []
        page.on("console", self._on_console)
        page.on("pageerror", lambda exc: self.errors.append(f"pageerror: {exc}"))
        page.on("requestfailed", self._on_requestfailed)
        page.on("response", self._on_response)

    def _ignored(self, text):
        return any(needle in text for needle in self.IGNORE)

    def _on_console(self, msg):
        if self._ignored(msg.text):
            return
        if msg.type == "error":
            self.errors.append(f"console.error: {msg.text}")
        elif msg.type == "warning":
            self.warnings.append(msg.text)

    def _on_requestfailed(self, req):
        if not self._ignored(req.url):
            self.failed_requests.append(f"{req.url} {req.failure}")

    def _on_response(self, res):
        if res.status >= 400 and not self._ignored(res.url):
            self.http_errors.append(f"{res.status} {res.url}")

    def reset(self):
        self.errors.clear()
        self.warnings.clear()
        self.failed_requests.clear()
        self.http_errors.clear()

    @property
    def problems(self):
        return self.errors + self.failed_requests + self.http_errors


class Session:
    """Owns the browser and hands out watched, Full HD, authenticated pages."""

    def __init__(self, base_url, images, write_shots, headed):
        self.base_url = base_url.rstrip("/")
        self.images = pathlib.Path(images)
        self.write_shots = write_shots
        self.headed = headed
        self.checks = Checks()
        self.taken = set()
        self._contexts = []
        self._pw = None
        self.browser = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            headless=not self.headed,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        if self.write_shots:
            self.images.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for context in self._contexts:
            try:
                context.close()
            except Exception:
                pass
        if self.browser:
            self.browser.close()
        if self._pw:
            self._pw.stop()
        return False

    def context(self, user=None):
        kwargs = {
            "viewport": VIEWPORT,
            "device_scale_factor": 1,
            "reduced_motion": "reduce",
        }
        if user:
            username, password = USERS[user]
            kwargs["extra_http_headers"] = {
                "Authorization": basic_auth(username, password)
            }
        context = self.browser.new_context(**kwargs)
        context.add_init_script(
            "document.addEventListener('DOMContentLoaded', () => {"
            "  const s = document.createElement('style');"
            f"  s.textContent = {json.dumps(QUIET_CSS)};"
            "  document.head.appendChild(s);"
            "});"
        )
        self._contexts.append(context)
        return context

    def page(self, user=None):
        """A new page plus its watcher."""
        page = self.context(user).new_page()
        return page, PageWatcher(page)

    def no_problems(self, case, watcher, what):
        return self.checks.check(
            case,
            f"{what}: no console/network errors",
            not watcher.problems,
            "; ".join(watcher.problems)[:300],
        )


def rest(page, base_url, path, method="GET", body=None):
    """Call a plone.restapi service from inside an authenticated page.

    plone.rest routes on the Accept header -- without it the request is an
    ordinary traversal and 404s, which is the single most common way these
    endpoints appear broken.
    """
    return page.evaluate(
        """async ({url, method, body}) => {
            const init = {
                method: method,
                headers: {'Content-Type': 'application/json',
                          'Accept': 'application/json'},
            };
            if (body !== null) { init.body = JSON.stringify(body); }
            const res = await fetch(url, init);
            const text = await res.text();
            let parsed = null;
            try { parsed = JSON.parse(text); } catch (e) {}
            return {status: res.status, body: text, json: parsed};
        }""",
        {"url": f"{base_url}{path}", "method": method, "body": body},
    )


def shot(session, page, name, case="", full_page=False, mask=None):
    """Write a registered screenshot, if this run is writing screenshots.

    Refuses unknown names: an image that no doc page claims is drift, and the
    registry in shots.py is the single place that decides what exists.
    """
    from . import shots as registry

    if name not in registry.BY_NAME:
        raise KeyError(
            f"screenshot {name!r} is not declared in scripts/uitest/shots.py"
        )
    session.taken.add(name)
    if not session.write_shots:
        return None

    path = session.images / f"{name}.png"
    kwargs = {"path": str(path), "full_page": full_page}
    if mask:
        kwargs["mask"] = mask
        kwargs["mask_color"] = "#cccccc"
    page.screenshot(**kwargs)
    if case:
        session.checks.check(case, f"screenshot {name}", path.exists())
    return path


def api(page, url, method="GET"):
    """Call a *cross-origin* service without going through the page.

    An in-page fetch to another origin (Operaton on :8081, Mailpit on :8025)
    is blocked by CORS; Playwright's request context is not, so service
    reachability checks use this instead of rest().
    """
    response = page.request.fetch(url, method=method)
    text = response.text()
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    return {"status": response.status, "body": text, "json": parsed}


TITLE_SELECTORS = (
    "#form-widgets-IBasic-title",
    "#form-widgets-IDublinCore-title",
    "#form-widgets-title",
)


def title_field(page):
    """The add/edit form's title input, whichever behavior provides it."""
    for selector in TITLE_SELECTORS:
        field = page.locator(selector)
        if field.count():
            return field
    return None


# The Bpm Proxy type carries its schema directly, so its widgets are
# "form-widgets-<field>". On a type that gets the same fields from the
# process-context *behavior*, plone.autoform prefixes them with the behavior
# interface name. Scenarios should not care which they are looking at.
BEHAVIOR_PREFIX = "IProcessContextBehavior"


def widget(page, field):
    """The add/edit widget for a process-context field, however it is named."""
    for selector in (
        f"#form-widgets-{field}",
        f"#form-widgets-{BEHAVIOR_PREFIX}-{field}",
    ):
        located = page.locator(selector)
        if located.count():
            return located
    return None


def widget_selector(page, field):
    """As widget(), but returns the selector string (for check/check-box ids)."""
    for selector in (
        f"#form-widgets-{field}",
        f"#form-widgets-{BEHAVIOR_PREFIX}-{field}",
    ):
        if page.locator(selector).count():
            return selector
    return None
