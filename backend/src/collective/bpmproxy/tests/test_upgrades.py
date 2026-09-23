from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from collective.bpmproxy.upgrades import remove_legacy_bundle_records
from plone.app.testing import applyProfile
from plone.registry import field
from plone.registry import Record
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
import unittest


LEGACY_RECORDS = (
    "plone.bundles/collective.bpmproxy.enabled",
    "plone.bundles/collective.bpmproxy.jscompilation",
    "plone.bundles/collective.bpmproxy.csscompilation",
    "plone.bundles/collective.bpmproxy.expression",
)


class TestUpgrades(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.registry = getUtility(IRegistry)
        for name in LEGACY_RECORDS:
            self.registry.records[name] = Record(field.ASCIILine(title="Legacy"), "x")

    def test_removes_legacy_bundle_records(self):
        remove_legacy_bundle_records()

        for name in LEGACY_RECORDS:
            self.assertNotIn(name, self.registry.records)

    def test_keeps_the_bundles_that_replaced_it(self):
        """The renamed bundles nest under the old name, and deleting a whole
        registry key range would take them with it."""
        remove_legacy_bundle_records()

        for name in (
            "plone.bundles/collective.bpmproxy.form.jscompilation",
            "plone.bundles/collective.bpmproxy.diagram.jscompilation",
        ):
            self.assertIn(name, self.registry.records)
        self.assertEqual(
            self.registry["plone.bundles/collective.bpmproxy.form.jscompilation"],
            "++plone++collective.bpmproxy/form.js",
        )

    def test_is_idempotent(self):
        remove_legacy_bundle_records()
        remove_legacy_bundle_records()

    def test_uninstall_removes_every_bundle(self):
        applyProfile(self.portal, "collective.bpmproxy:uninstall")

        self.assertEqual(
            [
                name
                for name in self.registry.records.keys()
                if name.startswith("plone.bundles/collective.bpmproxy")
            ],
            [],
        )
