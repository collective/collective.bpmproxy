from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
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
        from collective.bpmproxy.views.bpm_form_view import BpmProxyStartFormView

        view = getMultiAdapter(
            (self.portal["front-page"], self.portal.REQUEST), name="view"
        )
        self.assertNotIsInstance(view, BpmProxyStartFormView)


class ViewsFunctionalTest(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
