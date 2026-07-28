from collective.bpmproxy.modeler.upgrades import remove_legacy_modeler_records
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from plone.app.testing import applyProfile
from plone.registry import field
from plone.registry import Record
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
import unittest


class TestModelerUpgrades(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.registry = getUtility(IRegistry)

    def test_removes_pre_1004_records(self):
        legacy = "plone.bundles/collective-bpmproxy-modeler.enabled"
        keep = "plone.bundles/collective.bpmproxy.form.enabled"
        self.registry.records[legacy] = Record(field.Bool(title="Enabled"), True)

        remove_legacy_modeler_records()

        self.assertNotIn(legacy, self.registry.records)
        self.assertIn(keep, self.registry.records)

    def test_is_idempotent(self):
        remove_legacy_modeler_records()
        remove_legacy_modeler_records()


class TestModelerProfile(unittest.TestCase):
    """The modeler add-on is optional, so no other test installs it."""

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        applyProfile(self.portal, "collective.bpmproxy.modeler:default")
        self.registry = getUtility(IRegistry)

    def test_registers_single_modeler_bundle(self):
        prefix = "plone.bundles/collective.bpmproxy.modeler"
        self.assertEqual(
            self.registry[f"{prefix}.jscompilation"],
            "++plone++collective.bpmproxy/modeler.js",
        )
        self.assertEqual(
            self.registry[f"{prefix}.csscompilation"],
            "++plone++collective.bpmproxy/modeler.css",
        )
        # Only loaded where the control panel asks for it
        self.assertEqual(
            self.registry[f"{prefix}.expression"],
            "python:request.get('bpmproxy_modeler_required', False)",
        )

    def test_registers_controlpanel(self):
        actions = self.portal.portal_controlpanel.listActions()
        self.assertIn(
            "collective.bpmproxy.modeler",
            [action.getId() for action in actions],
        )

    def test_uninstall_removes_the_bundle(self):
        applyProfile(self.portal, "collective.bpmproxy.modeler:uninstall")

        self.assertEqual(
            [
                name
                for name in self.registry.records.keys()
                if "bpmproxy" in name and "modeler" in name
            ],
            [],
        )

    def test_uninstall_removes_the_controlpanel(self):
        applyProfile(self.portal, "collective.bpmproxy.modeler:uninstall")

        actions = self.portal.portal_controlpanel.listActions()
        self.assertNotIn(
            "collective.bpmproxy.modeler",
            [action.getId() for action in actions],
        )
