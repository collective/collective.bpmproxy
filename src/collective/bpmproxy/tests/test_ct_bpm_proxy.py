# -*- coding: utf-8 -*-
from collective.bpmproxy.content.bpm_proxy import IBpmProxy  # NOQA E501
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING  # noqa
from plone import api
from plone.app.testing import setRoles, TEST_USER_ID
from plone.dexterity.interfaces import IDexterityFTI
from zope.component import createObject, queryUtility

import unittest


class BpmProxyIntegrationTest(unittest.TestCase):

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.parent = self.portal

    def test_ct_bpm_proxy_schema(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Proxy')
        schema = fti.lookupSchema()
        self.assertEqual(IBpmProxy, schema)

    def test_ct_bpm_proxy_fti(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Proxy')
        self.assertTrue(fti)

    def test_ct_bpm_proxy_factory(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Proxy')
        factory = fti.factory
        obj = createObject(factory)


    def test_ct_bpm_proxy_adding(self):
        setRoles(self.portal, TEST_USER_ID, ['Contributor'])
        obj = api.content.create(
            container=self.portal,
            type='Bpm Proxy',
            id='bpm_proxy',
        )


        parent = obj.__parent__
        self.assertIn('bpm_proxy', parent.objectIds())

        # check that deleting the object works too
        api.content.delete(obj=obj)
        self.assertNotIn('bpm_proxy', parent.objectIds())

    def test_ct_bpm_proxy_globally_addable(self):
        setRoles(self.portal, TEST_USER_ID, ['Contributor'])
        fti = queryUtility(IDexterityFTI, name='Bpm Proxy')
        self.assertTrue(
            fti.global_allow,
            u'{0} is not globally addable!'.format(fti.id)
        )
