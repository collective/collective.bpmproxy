from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from plone.app.testing import applyProfile
from plone.app.testing import setRoles
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.testing.zope import Browser
from zope.publisher.interfaces.browser import IBrowserView
import transaction
import unittest


class TestControlPanel(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_controlpanel_view(self):
        view = self.portal.restrictedTraverse("@@bpmproxy-modeler-controlpanel")
        self.assertTrue(IBrowserView.providedBy(view))

    def test_controlpanel_requests_modeler_bundle(self):
        """The modeler bundle is loaded through the registry, keyed on this
        request flag, so it stays off every other page."""
        view = self.portal.restrictedTraverse("@@bpmproxy-modeler-controlpanel")
        self.assertFalse(self.request.get("bpmproxy_modeler_required", False))
        view()
        self.assertTrue(self.request.get("bpmproxy_modeler_required"))


class TestControlPanelRendering(unittest.TestCase):
    """The control panel is registered on the site root, which used to fail
    because our breadcrumbs override also won there."""

    layer = COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.browser = Browser(self.layer["app"])
        self.browser.handleErrors = False
        self.browser.addHeader(
            "Authorization",
            f"Basic {SITE_OWNER_NAME}:{SITE_OWNER_PASSWORD}",
        )

    def test_controlpanel_renders(self):
        self.browser.open(
            f"{self.portal.absolute_url()}/@@bpmproxy-modeler-controlpanel"
        )
        self.assertIn("bpmproxy-deployments-app", self.browser.contents)

    def test_portal_root_renders(self):
        """Regression: our breadcrumbs override must not win on the site root."""
        self.browser.open(self.portal.absolute_url())
        self.assertIn("</html>", self.browser.contents)


class TestControlPanelResources(unittest.TestCase):
    """With the optional modeler add-on installed, the modeler bundle is
    loaded by the resource registry -- and only where it is asked for."""

    layer = COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        applyProfile(self.portal, "collective.bpmproxy.modeler:default")
        transaction.commit()

        self.browser = Browser(self.layer["app"])
        self.browser.handleErrors = False
        self.browser.addHeader(
            "Authorization",
            f"Basic {SITE_OWNER_NAME}:{SITE_OWNER_PASSWORD}",
        )

    def test_controlpanel_loads_modeler_bundle(self):
        self.browser.open(
            f"{self.portal.absolute_url()}/@@bpmproxy-modeler-controlpanel"
        )
        self.assertIn("modeler.js", self.browser.contents)
        self.assertIn("modeler.css", self.browser.contents)

    def test_other_pages_do_not_load_modeler_bundle(self):
        self.browser.open(self.portal.absolute_url())
        self.assertNotIn("modeler.js", self.browser.contents)
