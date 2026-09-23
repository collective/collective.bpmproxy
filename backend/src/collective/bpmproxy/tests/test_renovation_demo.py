from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from plone import api
from plone.app.testing import applyProfile
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.contentrules.engine.interfaces import IRuleStorage
from plone.dexterity.interfaces import IDexterityFTI
from plone.portlets.interfaces import IPortletManager
from plone.uuid.interfaces import IUUID
from Products.CMFCore.WorkflowCore import WorkflowException
from unittest.mock import patch
from zope.component import getUtility
from zope.component import queryUtility
import pytest
import unittest


pytestmark = pytest.mark.renovation


class RenovationDemoProfileTest(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        applyProfile(self.portal, "collective.bpmproxy:renovation_demo")
        self.workflow_tool = api.portal.get_tool("portal_workflow")

    def test_case_type_is_a_folder(self):
        fti = queryUtility(IDexterityFTI, name="Renovation Project")
        self.assertIsNotNone(fti)
        self.assertEqual(fti.icon_expr, "string:contenttype/folder")
        self.assertEqual(tuple(fti.allowed_content_types), ("Document",))

    def test_workflow_bound_to_case(self):
        self.assertEqual(
            self.workflow_tool.getChainFor("Renovation Project"),
            ("renovation_project_workflow",),
        )
        self.assertEqual(
            set(
                self.workflow_tool.getWorkflowById("renovation_project_workflow").states
            ),
            {"open", "closed"},
        )

    def test_default_profile_bindings_untouched(self):
        self.assertEqual(
            self.workflow_tool.getChainFor("Bpm Attachments"),
            ("bpm_attachments_workflow",),
        )

    def test_tasks_portlet_is_assigned_by_case_content_type(self):
        from collective.bpmproxy.portlets.tasks import Assignment as TasksAssignment

        manager = getUtility(IPortletManager, name="plone.rightcolumn")
        mapping = manager["content_type"]["Renovation Project"]
        assignments = [
            assignment
            for assignment in mapping.values()
            if isinstance(assignment, TasksAssignment)
        ]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].header, "Case tasks")
        self.assertTrue(assignments[0].use_context)

        page_mapping = manager["content_type"]["Document"]
        page_assignments = [
            assignment
            for assignment in page_mapping.values()
            if isinstance(assignment, TasksAssignment)
        ]
        self.assertEqual(len(page_assignments), 1)
        self.assertEqual(page_assignments[0].header, "Page review tasks")
        self.assertTrue(page_assignments[0].use_context)

    def test_case_creation_rule_is_a_message(self):
        storage = queryUtility(IRuleStorage)
        rule = storage.get("renovation-case-created")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.event.__name__, "IObjectAddedEvent")
        self.assertEqual(rule.conditions[0].check_types, {"Renovation Project"})
        self.assertEqual(rule.actions[0].element, "plone.actions.BpmMessage")
        self.assertEqual(rule.actions[0].name, "renovation-case-created")
        self.assertEqual(rule.actions[0].correlationKeys, {})

    def test_case_closed_rule_is_a_correlated_message(self):
        storage = queryUtility(IRuleStorage)
        expected = {"renovation-case-closed": "close-case"}
        for name, transition in expected.items():
            rule = storage.get(name)
            self.assertIsNotNone(rule, name)
            self.assertEqual(rule.actions[0].element, "plone.actions.BpmMessage")
            self.assertEqual(rule.actions[0].name, name)
            workflow = next(c for c in rule.conditions if hasattr(c, "wf_transitions"))
            self.assertEqual(set(workflow.wf_transitions), {transition})
            self.assertEqual(rule.actions[0].correlationKeys, {"caseUuid": "${uuid}"})

    def test_document_rule_is_scoped_to_case_children(self):
        storage = queryUtility(IRuleStorage)
        rule = storage.get("renovation-case-document-created")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.actions[0].element, "plone.actions.BpmMessage")
        self.assertEqual(
            rule.actions[0].correlationKeys, {"caseUuid": "${parent_uuid}"}
        )
        self.assertIn("Renovation Project", rule.conditions[1].tales_expression)

    def test_direct_document_creation_schedules_case_message(self):
        case = api.content.create(
            container=self.portal,
            type="Renovation Project",
            id="document-case",
            title="Document case",
        )
        with patch("collective.bpmproxy.actions.message.join_side_effect") as join:
            api.content.create(
                container=case,
                type="Document",
                id="case-document",
                title="Case document",
            )

        self.assertTrue(join.called)
        args = join.call_args.kwargs["args"]
        self.assertEqual(args[0], "renovation-case-document-created")
        self.assertEqual(args[2], {"caseUuid": IUUID(case)})

    def test_case_has_one_close_transition(self):
        workflow = self.workflow_tool.getWorkflowById("renovation_project_workflow")
        self.assertEqual(set(workflow.transitions), {"close-case"})


class RenovationWorkflowPermissionTest(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        applyProfile(self.portal, "collective.bpmproxy:renovation_demo")
        self.workflow_tool = api.portal.get_tool("portal_workflow")
        self.case = api.content.create(
            container=self.portal,
            type="Renovation Project",
            id="permission-case",
            title="Permission case",
        )

    def test_submit_plan_requires_request_review(self):
        self.case.manage_delLocalRoles([TEST_USER_ID])
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        with patch("collective.bpmproxy.client.join_side_effect"):
            with self.assertRaises(WorkflowException):
                self.workflow_tool.doActionFor(self.case, "submit-plan")
