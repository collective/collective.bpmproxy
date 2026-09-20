"""Install the renovation-project demo and its recording-only demo users.

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

# Recording-only demo accounts, one per persona in
# docs/renovation-project-scenario.md. Not created by the profile itself --
# it only creates the *groups* -- so the recording script has someone to log
# in as for each of them.
DEMO_USERS = {
    "owner": ("owner", "Renovation Owners"),
    "contractor": ("contractor", "Renovation Contractors"),
    "inspector": ("inspector", "Renovation Inspectors"),
}

# The profile creates "renovation-bot" with a random password (it's a
# service account, never meant to be typed in). Reset it here to a known
# value so examples/renovation-bot/secrets.json can authenticate as it.
RENOVATION_BOT_PASSWORD = os.environ.get("RENOVATION_BOT_PASSWORD", "renovation-bot")


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

    # Delete a pre-existing demo project *before* reapplying the profile, so
    # its post_handler (renovation_demo.install()) recreates it fresh --
    # groups, roles and portlets included -- rather than leaving a project
    # from a previous, possibly-closed recording run in place. install() only
    # creates the project when it's absent, so this is what makes re-running
    # this script (and the recording) idempotent across a project's full
    # workflow lifecycle, including its terminal "closed" state that has no
    # transition back to "drafting_plan".
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

    for username, (password, group_id) in DEMO_USERS.items():
        if site.acl_users.getUserById(username) is None:
            print(f"Creating '{username}' (member of {group_id}) ...")
            site.acl_users.userFolderAddUser(username, password, ["Member"], [])
            api.group.add_user(groupname=group_id, username=username)
        else:
            print(f"'{username}' already exists")

    if site.acl_users.getUserById("renovation-bot") is not None:
        site.acl_users.source_users.updateUserPassword(
            "renovation-bot", RENOVATION_BOT_PASSWORD
        )
        print("Reset 'renovation-bot' password for the recording's purjo worker")
    else:
        print(
            "WARNING: 'renovation-bot' user not found -- "
            f"did {PROFILE} install correctly?"
        )

    transaction.commit()
    print("Done.")


main(app)  # noqa: F821 -- zconsole provides "app"
