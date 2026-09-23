"""The deployment endpoints mutate the shared engine (deletes cascade into
running process instances), so they are for site managers only.

A Site Administrator has "Modify portal content" but not "Manage portal", so
it is the role that tells the two permissions apart.
"""

from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING
from plone.app.testing import setRoles
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from plone.testing.zope import Browser
import json
import transaction
import unittest


class TestServicesSecurity(unittest.TestCase):
    layer = COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Site Administrator"])
        # plone.restapi's own profile is not part of this layer, so grant its
        # permission here to make sure it is our permission that decides.
        self.portal.manage_permission(
            "plone.restapi: Use REST API",
            roles=["Authenticated", "Manager", "Site Administrator"],
            acquire=False,
        )
        transaction.commit()

    def browser(self, username, password):
        browser = Browser(self.layer["app"])
        browser.handleErrors = True
        browser.raiseHttpErrors = False
        browser.addHeader("Authorization", f"Basic {username}:{password}")
        browser.addHeader("Accept", "application/json")
        return browser

    def status(self, browser):
        return browser.headers["status"].split()[0]

    def test_deployments_listing_denied_for_site_administrator(self):
        browser = self.browser(TEST_USER_NAME, TEST_USER_PASSWORD)
        browser.open(f"{self.portal.absolute_url()}/@bpmproxy-deployments")
        self.assertEqual(self.status(browser), "401", browser.contents)

    def test_deploy_denied_for_site_administrator(self):
        browser = self.browser(TEST_USER_NAME, TEST_USER_PASSWORD)
        browser.post(
            f"{self.portal.absolute_url()}/@bpmproxy-deploy",
            json.dumps({"xml": "<bpmn/>", "name": "test"}),
            "application/json",
        )
        self.assertEqual(self.status(browser), "401", browser.contents)

    def test_deployments_listing_allowed_for_manager(self):
        browser = self.browser(SITE_OWNER_NAME, SITE_OWNER_PASSWORD)
        browser.open(f"{self.portal.absolute_url()}/@bpmproxy-deployments")
        # No engine in the test environment, so this gets as far as failing to
        # reach it: what matters is that it was not refused.
        self.assertNotIn(self.status(browser), ("401", "403"), browser.contents)
