"""Create the Plone site the end-to-end smoke test runs against.

Run it against a stopped instance with zconsole, e.g.

    make bootstrap-site

It is idempotent: an existing site is left alone, only missing add-on
profiles are installed.
"""

from AccessControl.SecurityManagement import newSecurityManager
from collective.bpmproxy.interfaces import PLONE_ADMIN_GROUP
from plone.base.utils import get_installer
from Products.CMFPlone.browser.admin import AddPloneSite
from Products.CMFPlone.factory import addPloneSite
from Testing.makerequest import makerequest
from zope.component.hooks import setSite
import os
import plone.api as api
import transaction


SITE_ID = os.environ.get("PLONE_SITE_ID", "Plone")
ADMIN_USER = os.environ.get("PLONE_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("PLONE_ADMIN_PASSWORD", "admin")
# A site manager, in the group post_install nests into "camunda-admin" -- the
# JWT of a user outside it carries no engine rights, so deployments from the
# control panel would be refused by Operaton with a 403.
MANAGER_USER = os.environ.get("PLONE_MANAGER_USER", "manager")
MANAGER_PASSWORD = os.environ.get("PLONE_MANAGER_PASSWORD", "manager")
# Used by the smoke test to check that the deployment endpoints are refused to
# everyone below a site manager.
EDITOR_USER = os.environ.get("PLONE_EDITOR_USER", "editor")
EDITOR_PASSWORD = os.environ.get("PLONE_EDITOR_PASSWORD", "editor")
PROFILES = ("collective.bpmproxy:default", "collective.bpmproxy.modeler:default")


def main(app):
    app = makerequest(app)

    admin = app.acl_users.getUserById(ADMIN_USER)
    if admin is None:
        # Only happens against a database that never booted with an inituser
        # file (a freshly wiped Data.fs, say).
        print(f"Creating Zope root user '{ADMIN_USER}' ...")
        app.acl_users._doAddUser(ADMIN_USER, ADMIN_PASSWORD, ["Manager"], [])
        admin = app.acl_users.getUserById(ADMIN_USER)
    newSecurityManager(None, admin.__of__(app.acl_users))

    site = getattr(app, SITE_ID, None)
    if site is None:
        print(f"Creating Plone site '{SITE_ID}' ...")
        site = addPloneSite(
            app,
            SITE_ID,
            title="Plone",
            # The same extensions @@plone-addsite installs: without the theme
            # the site has neither styling nor Plone's own JavaScript.
            extension_ids=AddPloneSite(app, app.REQUEST).default_extension_profiles,
        )
    else:
        print(f"Plone site '{SITE_ID}' already exists")

    setSite(site)

    installer = get_installer(site, app.REQUEST)
    for profile in PROFILES:
        package = profile.split(":")[0]
        if installer.is_product_installed(package):
            print(f"{package} already installed")
            continue
        print(f"Installing {profile} ...")
        installer.install_product(package)

    if site.acl_users.getUserById(MANAGER_USER) is None:
        print(f"Creating '{MANAGER_USER}' (Manager, Administrators) ...")
        site.acl_users.userFolderAddUser(
            MANAGER_USER, MANAGER_PASSWORD, ["Manager"], []
        )
        api.group.add_user(groupname=PLONE_ADMIN_GROUP, username=MANAGER_USER)

    if site.acl_users.getUserById(EDITOR_USER) is None:
        print(f"Creating '{EDITOR_USER}' (Site Administrator) ...")
        site.acl_users.userFolderAddUser(
            EDITOR_USER, EDITOR_PASSWORD, ["Site Administrator"], []
        )

    transaction.commit()
    print("Done.")


main(app)  # noqa: F821 -- zconsole provides "app"
