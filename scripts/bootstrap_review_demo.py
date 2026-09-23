"""Install the review-process demo and its demo users.

Run it against a stopped instance with zconsole, after bootstrap_site.py,
e.g.

    make bootstrap-site
    make bootstrap-review-demo

It is idempotent: existing users/groups/profile installs are left alone.
"""

from AccessControl.SecurityManagement import newSecurityManager
from plone.base.utils import get_installer
from Testing.makerequest import makerequest
from zope.component.hooks import setSite
import os
import plone.api as api
import transaction


SITE_ID = os.environ.get("PLONE_SITE_ID", "Plone")
ADMIN_USER = os.environ.get("PLONE_ADMIN_USER", "admin")

PROFILE = "collective.bpmproxy:review_demo"

# Users offered by examples/review-process/review-select-reviewers.form
# (plus "author", who submits the content). The profile only creates the
# "Reviewers" group and "review-bot", so someone must exist to be selected
# as a reviewer and to log in as.
REVIEWERS = ("reviewer1", "reviewer2", "reviewer3", "editor")
AUTHOR = "author"
REVIEW_BOT_USER = "review-bot"

# The profile creates "review-bot" with a random password. Reset it to a
# known value so examples/review-bot-py/secrets.env can authenticate as it.
REVIEW_BOT_PASSWORD = os.environ.get("REVIEW_BOT_PASSWORD", "review-bot")


def ensure_user(site, username, roles=("Member",)):
    if site.acl_users.getUserById(username) is None:
        print(f"Creating '{username}' ...")
        site.acl_users.userFolderAddUser(username, username, list(roles), [])
    else:
        print(f"'{username}' already exists")


def main(app):
    app = makerequest(app)

    admin = app.acl_users.getUserById(ADMIN_USER)
    newSecurityManager(None, admin.__of__(app.acl_users))

    site = getattr(app, SITE_ID)
    setSite(site)

    installer = get_installer(site, app.REQUEST)
    if not installer.is_product_installed("collective.bpmproxy"):
        raise RuntimeError(
            "collective.bpmproxy is not installed -- run 'make bootstrap-site' first"
        )

    print(f"Applying {PROFILE} ...")
    api.portal.get_tool("portal_setup").runAllImportStepsFromProfile(
        f"profile-{PROFILE}"
    )
    site.manage_permission(
        "plone.restapi: Use REST API",
        roles=["Anonymous", "Manager", "Site Administrator"],
        acquire=False,
    )
    api.user.grant_roles(
        username=REVIEW_BOT_USER,
        roles=["Site Administrator"],
    )

    for username in REVIEWERS:
        ensure_user(site, username)
        api.group.add_user(groupname="Reviewers", username=username)
    ensure_user(site, AUTHOR, roles=("Member", "Contributor"))

    site.acl_users.source_users.updateUserPassword("review-bot", REVIEW_BOT_PASSWORD)
    print("Reset 'review-bot' password for the review worker")

    transaction.commit()
    print("Done.")


main(app)  # noqa: F821 -- zconsole provides "app"
