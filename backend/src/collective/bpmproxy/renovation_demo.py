"""Setup helpers for the optional renovation-project demo profile."""

from collective.bpmproxy.portlets.message import Assignment as MessageAssignment
from collective.bpmproxy.portlets.tasks import Assignment as TasksAssignment
from plone.portlets.interfaces import IPortletAssignmentMapping
from plone.portlets.interfaces import IPortletManager
from zope.component import getMultiAdapter
from zope.component import getUtility
import plone.api


OWNERS_GROUP = "Renovation Owners"
CONTRACTORS_GROUP = "Renovation Contractors"
INSPECTORS_GROUP = "Renovation Inspectors"


def _ensure_group(group_id, title):
    if not plone.api.group.get(group_id):
        plone.api.group.create(groupname=group_id, title=title)


def install(context):
    portal = plone.api.portal.get()

    _ensure_group(OWNERS_GROUP, "Renovation Owners")
    _ensure_group(CONTRACTORS_GROUP, "Renovation Contractors")
    _ensure_group(INSPECTORS_GROUP, "Renovation Inspectors")

    if not plone.api.user.get(username="renovation-bot"):
        bot = plone.api.user.create(
            username="renovation-bot",
            email="renovation-bot@example.com",
            properties={"fullname": "Renovation Bot"},
        )
        plone.api.group.add_user(groupname="Site Administrators", user=bot)

    if "renovation-project-demo" in portal:
        return

    project = plone.api.content.create(
        container=portal,
        type="Renovation Project",
        id="renovation-project-demo",
        title="Demo renovation project",
    )
    project.site_address = "1 Demo Street"

    project.manage_setLocalRoles(CONTRACTORS_GROUP, ["Contributor", "Editor"])
    project.manage_setLocalRoles(OWNERS_GROUP, ["Reviewer"])
    project.manage_setLocalRoles(INSPECTORS_GROUP, ["Reviewer"])
    project.reindexObjectSecurity()

    # "Request extra work" has no Plone workflow transition behind it -- it's
    # dispatched directly via the Message portlet. Unlike the Tasks portlet's
    # signal-based aggregation (safe there since every consumer is a
    # process-definition start event), this one must correlate to exactly
    # this project's own running Work & Extra-Work instance -- otherwise a
    # broadcast would also fire "Approve extra work" in any other
    # concurrently-running renovation project. correlationKeys targets the
    # "uuid" process variable that Activity_bind_key sets once at process
    # start (renovation-work-and-extra-work.bpmn) and never overwrites.
    manager = getUtility(IPortletManager, name="plone.rightcolumn")
    mapping = getMultiAdapter((project, manager), IPortletAssignmentMapping)
    mapping["renovation-tasks"] = TasksAssignment(
        header="Project tasks", use_context=True
    )
    mapping["renovation-extra-work-message"] = MessageAssignment(
        header="Request extra work",
        name="renovation-extra-work-requested",
        correlationKeys={"uuid": "${uuid}"},
        payload={"uuid": "${uuid}"},
        review_states=["in_progress"],
    )
