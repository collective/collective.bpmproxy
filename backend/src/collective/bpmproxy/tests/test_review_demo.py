from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from plone import api
from plone.app.contentrules.rule import get_assignments
from plone.app.testing import applyProfile
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.contentrules.engine.interfaces import IRuleStorage
from zope.component import queryUtility
import unittest


class ReviewDemoProfileTest(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        applyProfile(self.portal, "collective.bpmproxy:review_demo")

    def test_reviewers_group_created(self):
        self.assertIsNotNone(api.group.get("Reviewers"))

    def test_reviewers_group_can_review(self):
        group = api.group.get("Reviewers")
        self.assertIn("Reviewer", api.group.get_roles(group=group))

    def test_tasks_portlet_on_site_root(self):
        from plone.portlets.interfaces import IPortletAssignmentMapping
        from plone.portlets.interfaces import IPortletManager
        from zope.component import getMultiAdapter
        from zope.component import getUtility

        manager = getUtility(IPortletManager, name="plone.rightcolumn")
        mapping = getMultiAdapter((self.portal, manager), IPortletAssignmentMapping)
        self.assertIn("review-tasks", mapping)

    def test_review_bot_user_created(self):
        bot = api.user.get("review-bot")
        self.assertIsNotNone(bot)
        groups = [g.getId() for g in api.group.get_groups(user=bot)]
        self.assertIn("Site Administrators", groups)
        self.assertIn("Reviewers", groups)

    def test_content_rules_registered(self):
        rule_storage = queryUtility(IRuleStorage)
        self.assertIsNotNone(rule_storage)

        # 1. plone-content-submitted-to-review
        rule_submit = rule_storage.get("plone-content-submitted-to-review")
        self.assertIsNotNone(rule_submit)
        self.assertTrue(rule_submit.enabled)
        transitions = [c.wf_transitions for c in rule_submit.conditions]
        self.assertEqual(transitions[0], {"submit"})
        self.assertEqual(rule_submit.actions[0].element, "plone.actions.BpmMessage")
        self.assertEqual(
            rule_submit.actions[0].name, "plone-content-submitted-to-review"
        )

        # 2. plone-content-retracted
        rule_retract = rule_storage.get("plone-content-retracted")
        self.assertIsNotNone(rule_retract)
        self.assertTrue(rule_retract.enabled)
        transitions = [c.wf_transitions for c in rule_retract.conditions]
        self.assertEqual(transitions[0], {"retract"})
        self.assertEqual(rule_retract.actions[0].element, "plone.actions.BpmSignal")
        self.assertEqual(
            rule_retract.actions[0].name, "plone-content-retracted:${uuid}"
        )

    def test_content_rules_assigned_to_site_root(self):
        rule_storage = queryUtility(IRuleStorage)
        portal_path = "/".join(self.portal.getPhysicalPath())
        for rule_name in (
            "plone-content-submitted-to-review",
            "plone-content-retracted",
        ):
            rule = rule_storage.get(rule_name)
            assignments = get_assignments(rule)
            self.assertIn(portal_path, assignments)
