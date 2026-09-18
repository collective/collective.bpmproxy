from collective.bpmproxy.adapters.patterns import PatternsSettings
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from collective.bpmproxy.tests.helpers import process_context_behavior_enabled
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.base.interfaces import IPatternsSettings
from zope.component import getAdapters
import unittest


class TestPatternsSettings(unittest.TestCase):
    def test_patterns_settings(self):
        adapter = PatternsSettings("context", "request", "field")
        self.assertEqual(adapter.context, "context")
        self.assertEqual(adapter.request, "request")
        self.assertEqual(adapter.field, "field")

        result = adapter()
        self.assertEqual(
            result, {"data-pat-code-editor": "language: js; theme: tomorrow;"}
        )


class TestPatternsSettingsRegistration(unittest.TestCase):
    """The adapter is registered for="..behaviors.process_context.IProcessContext",
    not for Bpm Proxy specifically, so it must fire for any behavior-enabled
    type -- this is what Products.CMFPlone.patterns.view.PatternsSettingsView
    actually calls (with field=None) to build a page's global data-pat-*
    attributes.
    """

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def test_adapter_matches_a_behavior_enabled_non_bpm_proxy_type(self):
        portal = self.layer["portal"]
        setRoles(portal, TEST_USER_ID, ["Manager"])
        with process_context_behavior_enabled("Folder"):
            folder = api.content.create(portal, "Folder", "process-folder")
            adapters = dict(
                getAdapters((folder, portal.REQUEST, None), IPatternsSettings)
            )
            self.assertIn("collective_bpmproxy", adapters)
            self.assertEqual(
                adapters["collective_bpmproxy"](),
                {"data-pat-code-editor": "language: js; theme: tomorrow;"},
            )

    def test_adapter_does_not_match_a_plain_type(self):
        portal = self.layer["portal"]
        setRoles(portal, TEST_USER_ID, ["Manager"])
        document = api.content.create(portal, "Document", "plain-doc")
        adapters = dict(
            getAdapters((document, portal.REQUEST, None), IPatternsSettings)
        )
        self.assertNotIn("collective_bpmproxy", adapters)
