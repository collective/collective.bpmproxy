"""Install the renovation case demo and its recording-only demo users.

Run it against a stopped instance with zconsole, after bootstrap_site.py,
e.g.

    make bootstrap-site
    make bootstrap-renovation-demo

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

PROFILE = "collective.bpmproxy:renovation_demo"

# Recording-only demo accounts, one per persona in the browser scenario.
DEMO_USERS = {
    "owner": ("owner", "Renovation Owners"),
    "contractor": ("contractor", "Renovation Contractors"),
    "inspector": ("inspector", "Renovation Inspectors"),
}

GROUPS = tuple({group_id for _, group_id in DEMO_USERS.values()})


def ensure_groups():
    for group_id in GROUPS:
        if api.group.get(group_id) is None:
            api.group.create(groupname=group_id, title=group_id)


def create_demo_case(site):
    case = api.content.create(
        container=site,
        type="Renovation Project",
        id="renovation-project-demo",
        title="Demo renovation project",
    )
    case.manage_setLocalRoles("Renovation Contractors", ["Contributor", "Editor"])
    case.manage_setLocalRoles("Renovation Owners", ["Reviewer"])
    case.manage_setLocalRoles("Renovation Inspectors", ["Reviewer"])
    case.reindexObjectSecurity()



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

    # Delete the previous case before reapplying the profile so the fixture is
    # recreated at the workflow's initial state.
    if "renovation-project-demo" in site:
        print("Removing existing 'renovation-project-demo' for a clean run ...")
        api.content.delete(obj=site["renovation-project-demo"])

    # The profile is an *extension* profile of the already-installed
    # collective.bpmproxy package, so it's (re-)applied via the profile id
    # directly rather than install_product(), and reapplying it is safe --
    # GenericSetup steps here are idempotent by name (groups, workflow
    # bindings, content rules) other than the demo project itself, above.
    print(f"Applying {PROFILE} ...")
    setup_tool = api.portal.get_tool("portal_setup")
    setup_tool.runAllImportStepsFromProfile(f"profile-{PROFILE}")

    ensure_groups()

    for username, (password, group_id) in DEMO_USERS.items():
        if site.acl_users.getUserById(username) is None:
            print(f"Creating '{username}' (member of {group_id}) ...")
            site.acl_users.userFolderAddUser(username, password, ["Member"], [])
            api.group.add_user(groupname=group_id, username=username)
        else:
            print(f"'{username}' already exists")

    create_demo_case(site)

    transaction.commit()
    print("Done.")


main(app)  # noqa: F821 -- zconsole provides "app"
