# -*- coding: utf-8 -*-
from collective.bpmproxy.content.bpm_attachments import IBpmAttachments  # NOQA E501
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING  # noqa
from plone import api
from plone.api.exc import InvalidParameterError
from plone.app.testing import setRoles, TEST_USER_ID
from plone.dexterity.interfaces import IDexterityFTI
from zope.component import createObject, queryUtility

import unittest


class BpmAttachmentsIntegrationTest(unittest.TestCase):

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        portal_types = self.portal.portal_types
        parent_id = portal_types.constructContent(
            'Bpm Proxy',
            self.portal,
            'parent_container',
            title='Parent container',
        )
        self.parent = self.portal[parent_id]

    def test_ct_bpm_attachments_schema(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Attachments')
        schema = fti.lookupSchema()
        self.assertEqual(IBpmAttachments, schema)

    def test_ct_bpm_attachments_fti(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Attachments')
        self.assertTrue(fti)

    def test_ct_bpm_attachments_factory(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Attachments')
        factory = fti.factory
        obj = createObject(factory)


    def test_ct_bpm_attachments_adding(self):
        setRoles(self.portal, TEST_USER_ID, ['Contributor'])
        obj = api.content.create(
            container=self.parent,
            type='Bpm Attachments',
            id='bpm_attachments',
        )


        parent = obj.__parent__
        self.assertIn('bpm_attachments', parent.objectIds())

        # check that deleting the object works too
        api.content.delete(obj=obj)
        self.assertNotIn('bpm_attachments', parent.objectIds())

    def test_ct_bpm_attachments_globally_not_addable(self):
        setRoles(self.portal, TEST_USER_ID, ['Contributor'])
        fti = queryUtility(IDexterityFTI, name='Bpm Attachments')
        self.assertFalse(
            fti.global_allow,
            u'{0} is globally addable!'.format(fti.id)
        )

    def test_ct_bpm_attachments_filter_content_type_true(self):
        setRoles(self.portal, TEST_USER_ID, ['Contributor'])
        fti = queryUtility(IDexterityFTI, name='Bpm Attachments')
        portal_types = self.portal.portal_types
        parent_id = portal_types.constructContent(
            fti.id,
            self.portal,
            'bpm_attachments_id',
            title='Bpm Attachments container',
        )
        self.parent = self.portal[parent_id]
        with self.assertRaises(InvalidParameterError):
            api.content.create(
                container=self.parent,
                type='Document',
                title='My Content',
            )
