"""Setup tests for this package."""

from collective.bpmproxy.testing import (  # noqa: E501
    COLLECTIVE_BPMPROXY_INTEGRATION_TESTING,
)
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.base.utils import get_installer
import unittest


class TestSetup(unittest.TestCase):
    """Test that collective.bpmproxy is properly installed."""

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        self.installer = get_installer(self.portal, self.layer["request"])

    def test_product_installed(self):
        """Test if collective.bpmproxy is installed."""
        self.assertTrue(self.installer.is_product_installed("collective.bpmproxy"))

    def test_browserlayer(self):
        """Test that ICollectiveBpmproxyLayer is registered."""
        from collective.bpmproxy.interfaces import ICollectiveBpmproxyLayer
        from plone.browserlayer import utils

        self.assertIn(ICollectiveBpmproxyLayer, utils.registered_layers())

    def test_setuphandlers(self):
        from collective.bpmproxy.interfaces import ATTACHMENTS_DEFAULT_TYPE
        from collective.bpmproxy.setuphandlers import HiddenProfiles
        from collective.bpmproxy.setuphandlers import post_install
        from collective.bpmproxy.setuphandlers import uninstall

        # Test HiddenProfiles
        hidden = HiddenProfiles().getNonInstallableProfiles()
        self.assertIn("collective.bpmproxy:uninstall", hidden)

        # Test post_install adds type to registry when missing
        types = api.portal.get_registry_record(
            "plone.types_use_view_action_in_listings", default=[]
        )
        if ATTACHMENTS_DEFAULT_TYPE in types:
            types.remove(ATTACHMENTS_DEFAULT_TYPE)
            api.portal.set_registry_record(
                "plone.types_use_view_action_in_listings", types
            )

        post_install(self.portal)

        types = api.portal.get_registry_record(
            "plone.types_use_view_action_in_listings", default=[]
        )
        self.assertIn(ATTACHMENTS_DEFAULT_TYPE, types)

        # Test uninstall
        uninstall(self.portal)


class TestUninstall(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.installer = get_installer(self.portal, self.layer["request"])
        roles_before = api.user.get_roles(TEST_USER_ID)
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.installer.uninstall_product("collective.bpmproxy")
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if collective.bpmproxy is cleanly uninstalled."""
        self.assertFalse(self.installer.is_product_installed("collective.bpmproxy"))

    def test_browserlayer_removed(self):
        """Test that ICollectiveBpmproxyLayer is removed."""
        from collective.bpmproxy.interfaces import ICollectiveBpmproxyLayer
        from plone.browserlayer import utils

        self.assertNotIn(ICollectiveBpmproxyLayer, utils.registered_layers())
