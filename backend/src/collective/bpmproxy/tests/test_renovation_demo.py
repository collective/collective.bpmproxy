from collective.bpmproxy.behaviors.process_context import IProcessContext
from collective.bpmproxy.subscribers.tasks import completeAddTask
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from plone import api
from plone.app.testing import applyProfile
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.contentrules.engine.interfaces import IRuleStorage
from plone.dexterity.interfaces import IDexterityFTI
from Products.CMFCore.WorkflowCore import WorkflowException
from unittest.mock import MagicMock
from unittest.mock import patch
from zope.component import queryUtility
import unittest


class RenovationDemoProfileTest(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        applyProfile(self.portal, "collective.bpmproxy:renovation_demo")
        self.workflow_tool = api.portal.get_tool("portal_workflow")

    def test_renovation_project_type_has_behaviors(self):
        fti = queryUtility(IDexterityFTI, name="Renovation Project")
        self.assertIsNotNone(fti)
        self.assertNotIn("collective.bpmproxy.process_context", fti.behaviors)
        self.assertIn("collective.bpmproxy.renovation_project", fti.behaviors)

    def test_demo_groups_created(self):
        for group_id in (
            "Renovation Owners",
            "Renovation Contractors",
            "Renovation Inspectors",
        ):
            self.assertIsNotNone(api.group.get(group_id), group_id)

    def test_demo_project_created(self):
        self.assertIn("renovation-project-demo", self.portal)
        project = self.portal["renovation-project-demo"]
        self.assertFalse(IProcessContext.providedBy(project))
        self.assertEqual(
            api.content.get_state(project),
            "drafting_plan",
        )

    def test_extra_work_portlet_uses_correlated_message(self):
        from collective.bpmproxy.portlets.message import Assignment as MessageAssignment
        from plone.portlets.interfaces import IPortletAssignmentMapping
        from plone.portlets.interfaces import IPortletManager
        from zope.component import getMultiAdapter
        from zope.component import getUtility

        project = self.portal["renovation-project-demo"]
        manager = getUtility(IPortletManager, name="plone.rightcolumn")
        mapping = getMultiAdapter((project, manager), IPortletAssignmentMapping)
        assignment = mapping["renovation-extra-work-message"]
        self.assertIsInstance(assignment, MessageAssignment)
        self.assertEqual(assignment.correlationKeys, {"uuid": "${uuid}"})

    def test_workflow_bound_to_renovation_project(self):
        chain = self.workflow_tool.getChainFor("Renovation Project")
        self.assertEqual(chain, ("renovation_project_workflow",))

    def test_default_profile_bindings_untouched(self):
        # Regression test: installing renovation_demo on top of default
        # must not disturb default's own workflow bindings.
        chain = self.workflow_tool.getChainFor("Bpm Attachments")
        self.assertEqual(chain, ("bpm_attachments_workflow",))

    def test_submit_plan_requires_request_review_permission(self):
        project = api.content.create(
            container=self.portal,
            type="Renovation Project",
            id="project-1",
            title="Project 1",
        )
        # Strip the local "Owner" role Dexterity auto-grants to the
        # creator, so the guard is exercised on the *global* role only.
        project.manage_delLocalRoles([TEST_USER_ID])
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        with self.assertRaises(WorkflowException):
            self.workflow_tool.doActionFor(project, "submit-plan")

        setRoles(self.portal, TEST_USER_ID, ["Editor"])
        self.workflow_tool.doActionFor(project, "submit-plan")
        self.assertEqual(api.content.get_state(project), "plan_review")

    def test_bpm_transitions_require_review_portal_content_permission(self):
        project = api.content.create(
            container=self.portal,
            type="Renovation Project",
            id="project-2",
            title="Project 2",
        )
        setRoles(self.portal, TEST_USER_ID, ["Editor"])
        self.workflow_tool.doActionFor(project, "submit-plan")

        setRoles(self.portal, TEST_USER_ID, ["Member"])
        with self.assertRaises(WorkflowException):
            self.workflow_tool.doActionFor(project, "approve-plan")

        setRoles(self.portal, TEST_USER_ID, ["Reviewer"])
        self.workflow_tool.doActionFor(project, "approve-plan")
        self.assertEqual(api.content.get_state(project), "in_progress")

    def test_full_lifecycle_and_rejection_paths(self):
        project = api.content.create(
            container=self.portal,
            type="Renovation Project",
            id="project-3",
            title="Project 3",
        )
        setRoles(self.portal, TEST_USER_ID, ["Editor", "Reviewer"])

        self.workflow_tool.doActionFor(project, "submit-plan")
        self.assertEqual(api.content.get_state(project), "plan_review")

        self.workflow_tool.doActionFor(project, "reject-plan")
        self.assertEqual(api.content.get_state(project), "drafting_plan")

        self.workflow_tool.doActionFor(project, "submit-plan")
        self.workflow_tool.doActionFor(project, "approve-plan")
        self.assertEqual(api.content.get_state(project), "in_progress")

        self.workflow_tool.doActionFor(project, "submit-for-final-review")
        self.assertEqual(api.content.get_state(project), "final_review")

        self.workflow_tool.doActionFor(project, "reject-final-review")
        self.assertEqual(api.content.get_state(project), "in_progress")

        self.workflow_tool.doActionFor(project, "submit-for-final-review")
        self.workflow_tool.doActionFor(project, "close-project")
        self.assertEqual(api.content.get_state(project), "closed")

    def test_content_rules_wired_to_transitions(self):
        rule_storage = queryUtility(IRuleStorage)
        expected = {
            "renovation-plan-submitted": {"submit-plan"},
            "renovation-work-phase-started": {"approve-plan", "reject-final-review"},
            "renovation-final-review-requested": {"submit-for-final-review"},
            "renovation-plan-rejected": {"reject-plan"},
            "renovation-project-closed": {"close-project"},
        }
        for rule_name, wf_transitions in expected.items():
            rule = rule_storage.get(rule_name)
            self.assertIsNotNone(rule, rule_name)
            conditions = [c.wf_transitions for c in rule.conditions]
            self.assertEqual(set(conditions[0]), wf_transitions)
            self.assertEqual(rule.actions[0].element, "plone.actions.BpmSignal")


class RenovationWorkLogAutoCompleteTest(unittest.TestCase):
    """Regression test for the Work Log auto-complete UUID-prefix gotcha:
    content added directly to the project's own UUID auto-completes the
    matching Camunda task, but content added to a nested container (with
    a different UUID) must not.
    """

    @patch("collective.bpmproxy.subscribers.tasks.ICollectiveBpmproxyLayer")
    @patch("collective.bpmproxy.subscribers.tasks.camunda_client")
    @patch("collective.bpmproxy.subscribers.tasks.get_available_tasks")
    @patch("collective.bpmproxy.subscribers.tasks.IUUID")
    def test_add_document_to_project_matches_task(
        self, mock_iuuid, mock_get_tasks, mock_camunda_client, mock_layer
    ):
        mock_layer.providedBy.return_value = True
        project = MagicMock()
        document = MagicMock()
        document.portal_type = "Document"

        mock_iuuid.return_value = "project-uuid"
        task = MagicMock()
        task.form_key = "++add++Document"
        mock_get_tasks.return_value = [task]

        event = MagicMock()
        event.newParent = project

        completeAddTask(document, event)

        mock_get_tasks.assert_called_once()
        self.assertEqual(mock_get_tasks.call_args.kwargs["context_key"], "project-uuid")

    @patch("collective.bpmproxy.subscribers.tasks.ICollectiveBpmproxyLayer")
    @patch("collective.bpmproxy.subscribers.tasks.camunda_client")
    @patch("collective.bpmproxy.subscribers.tasks.get_available_tasks")
    @patch("collective.bpmproxy.subscribers.tasks.IUUID")
    def test_add_document_to_nested_folder_does_not_match(
        self, mock_iuuid, mock_get_tasks, mock_camunda_client, mock_layer
    ):
        mock_layer.providedBy.return_value = True
        folder = MagicMock()
        document = MagicMock()
        document.portal_type = "Document"

        mock_iuuid.return_value = "folder-uuid"
        task = MagicMock()
        task.form_key = "++add++Document"
        # The task's business key is scoped to the *project's* uuid, not
        # this nested folder's -- Operaton wouldn't return it for a query
        # scoped to the folder's own uuid.
        mock_get_tasks.return_value = []

        event = MagicMock()
        event.newParent = folder

        completeAddTask(document, event)

        mock_get_tasks.assert_called_once()
        self.assertEqual(mock_get_tasks.call_args.kwargs["context_key"], "folder-uuid")
