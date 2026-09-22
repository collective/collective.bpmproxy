"""Create the recording users for the contact-form demo.

Run against a stopped Plone instance after ``bootstrap_site.py``:

    make bootstrap-site
    make bootstrap-contact-form-demo

The contact-form example has no add-on profile of its own.  It only needs an
Administrator who can triage the review task and an ordinary Member who can
receive the delegated task.
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

USERS = {
    "reception": ("reception", ("Member",)),
    "specialist": ("specialist", ("Member",)),
}


def main(app):
    app = makerequest(app)

    admin = app.acl_users.getUserById(ADMIN_USER)
    if admin is None:
        raise RuntimeError(f"Plone admin user {ADMIN_USER!r} does not exist")
    newSecurityManager(None, admin.__of__(app.acl_users))

    site = getattr(app, SITE_ID)
    setSite(site)

    installer = get_installer(site, app.REQUEST)
    if not installer.is_product_installed("collective.bpmproxy"):
        raise RuntimeError(
            "collective.bpmproxy is not installed -- run 'make bootstrap-site' first"
        )

    for username, (password, roles) in USERS.items():
        if site.acl_users.getUserById(username) is None:
            print(f"Creating '{username}' ...")
            site.acl_users.userFolderAddUser(username, password, list(roles), [])
        else:
            print(f"'{username}' already exists")
        site.acl_users.source_users.updateUserPassword(username, password)

    # contact-form.bpmn hardcodes the built-in Administrators group as the
    # candidate group for its first user task.
    api.group.add_user(groupname="Administrators", username="reception")
    api.user.grant_roles(username="reception", roles=["Site Administrator"])
    print("Added 'reception' to Administrators")

    transaction.commit()
    print("Done.")


main(app)  # noqa: F821 -- zconsole provides "app"
