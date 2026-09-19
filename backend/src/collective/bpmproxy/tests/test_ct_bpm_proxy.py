from collective.bpmproxy.behaviors.process_context import IProcessContext
from collective.bpmproxy.behaviors.process_context import IProcessContextBehavior
from collective.bpmproxy.content.bpm_proxy import IBpmProxy  # NOQA E501
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING  # noqa
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.dexterity.interfaces import IDexterityFTI
from zope.component import createObject
from zope.component import queryUtility
import unittest


class BpmProxyIntegrationTest(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.parent = self.portal

    def test_ct_bpm_proxy_schema(self):
        fti = queryUtility(IDexterityFTI, name="Bpm Proxy")
        schema = fti.lookupSchema()
        self.assertEqual(IBpmProxy, schema)

    def test_ct_bpm_proxy_fti(self):
        fti = queryUtility(IDexterityFTI, name="Bpm Proxy")
        self.assertTrue(fti)

    def test_ct_bpm_proxy_factory(self):
        fti = queryUtility(IDexterityFTI, name="Bpm Proxy")
        factory = fti.factory
        self.assertIsNotNone(createObject(factory))

    def test_ct_bpm_proxy_adding(self):
        setRoles(self.portal, TEST_USER_ID, ["Contributor"])
        obj = api.content.create(
            container=self.portal,
            type="Bpm Proxy",
            id="bpm_proxy",
        )

        parent = obj.__parent__
        self.assertIn("bpm_proxy", parent.objectIds())

        # check that deleting the object works too
        api.content.delete(obj=obj)
        self.assertNotIn("bpm_proxy", parent.objectIds())

    def test_ct_bpm_proxy_globally_addable(self):
        setRoles(self.portal, TEST_USER_ID, ["Contributor"])
        fti = queryUtility(IDexterityFTI, name="Bpm Proxy")
        self.assertTrue(fti.global_allow, f"{fti.id} is not globally addable!")

    def test_existing_content_needs_no_upgrade_step_for_process_context(self):
        # IBpmProxy composes (IProcessContext, IProcessContextBehavior)
        # instead of declaring its own fields, but the field storage is
        # unchanged plain attributes on the object under the same names, and
        # Dexterity computes providedBy() from the FTI's schema at access
        # time rather than from a persisted marker -- so a site upgrading
        # collective.bpmproxy's code gets this "for free" on the next
        # request, with no GenericSetup upgrade step, re-import, or content
        # migration required. This asserts that expectation rather than
        # just documenting it.
        setRoles(self.portal, TEST_USER_ID, ["Contributor"])
        obj = api.content.create(
            container=self.portal,
            type="Bpm Proxy",
            id="bpm_proxy_upgrade_check",
        )
        # Simulate pre-existing data written under the old, non-behavior
        # schema: plain attributes, same names, no upgrade machinery
        # involved in setting them.
        obj.process_definition_key = "legacy-process"
        obj.diagram_enabled = True

        self.assertTrue(IProcessContext.providedBy(obj))
        self.assertTrue(IProcessContextBehavior.providedBy(obj))

        behavior = IProcessContextBehavior(obj)
        self.assertEqual(behavior.process_definition_key, "legacy-process")
        self.assertTrue(behavior.diagram_enabled)
