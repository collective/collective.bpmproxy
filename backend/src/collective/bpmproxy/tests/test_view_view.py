from collective.bpmproxy.behaviors.process_context import IProcessContext
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from collective.bpmproxy.tests.helpers import process_context_behavior_enabled
from collective.bpmproxy.views.bpm_form_view import BpmProxyStartFormView
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from zope.component import getMultiAdapter
import unittest


class ViewsIntegrationTest(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        api.content.create(self.portal, "Folder", "other-folder")
        api.content.create(self.portal, "Document", "front-page")

    def test_view_is_registered(self):
        view = getMultiAdapter(
            (self.portal["other-folder"], self.portal.REQUEST), name="view"
        )
        self.assertTrue(view.__name__ == "view")
        # self.assertTrue(
        #     'Sample View' in view(),
        #     'Sample View is not found in view'
        # )

    def test_view_not_matching_interface(self):
        # In Plone 6 every content type has a "view"; assert that ours is
        # only used for Bpm Proxy content.
        view = getMultiAdapter(
            (self.portal["front-page"], self.portal.REQUEST), name="view"
        )
        self.assertNotIsInstance(view, BpmProxyStartFormView)

    def test_view_matches_any_behavior_enabled_type(self):
        # Not just Bpm Proxy: any type with the process_context behavior
        # enabled gets the same start-form view.
        with process_context_behavior_enabled("Folder"):
            enabled = api.content.create(self.portal, "Folder", "process-folder")
            self.assertTrue(IProcessContext.providedBy(enabled))

            view = getMultiAdapter((enabled, self.portal.REQUEST), name="view")
            self.assertIsInstance(view, BpmProxyStartFormView)

            # No process_definition_key set yet: renders without ever
            # needing a live engine, and tells the visitor so. The status
            # messages viewlet consumes IStatusMessage while rendering the
            # page, so check the rendered markup rather than the queue.
            rendered = view()
            self.assertTrue(rendered)
            self.assertIn("not configured yet", rendered)


class ViewsFunctionalTest(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
