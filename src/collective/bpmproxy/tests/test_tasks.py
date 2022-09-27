# -*- coding: utf-8 -*-
from collective.bpmproxy.testing import (
    COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING,
    COLLECTIVE_BPMPROXY_INTEGRATION_TESTING,
)
from plone.app.testing import setRoles, TEST_USER_ID
from plone.portlets.interfaces import IPortletType
from zope.component import getUtility

import unittest


class PortletIntegrationTest(unittest.TestCase):

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.app = self.layer['app']
        self.request = self.app.REQUEST
        setRoles(self.portal, TEST_USER_ID, ['Manager'])

    def test_tasks_is_registered(self):
        portlet = getUtility(
            IPortletType,
            name='collective.bpmproxy.portlets.Tasks',
        )
        self.assertEqual(portlet.addview, 'collective.bpmproxy.portlets.Tasks')


class PortletFunctionalTest(unittest.TestCase):

    layer = COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
