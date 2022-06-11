# -*- coding: utf-8 -*-
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING  # noqa
from plone import api
from plone.app.testing import setRoles, TEST_USER_ID
from plone.dexterity.interfaces import IDexterityFTI
from zope.component import createObject, queryUtility

import unittest


try:
    from plone.dexterity.schema import portalTypeToSchemaName
except ImportError:
    # Plone < 5
    from plone.dexterity.utils import portalTypeToSchemaName


class BpmAttachmentIntegrationTest(unittest.TestCase):

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        portal_types = self.portal.portal_types
        parent_id = portal_types.constructContent(
            'Bpm Attachments',
            self.portal,
            'parent_container',
            title='Parent container',
        )
        self.parent = self.portal[parent_id]

    def test_ct_bpm_attachment_schema(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Attachment')
        schema = fti.lookupSchema()
        schema_name = portalTypeToSchemaName('Bpm Attachment')
        self.assertIn(schema_name.lstrip('plone_0_'), schema.getName())

    def test_ct_bpm_attachment_fti(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Attachment')
        self.assertTrue(fti)

    def test_ct_bpm_attachment_factory(self):
        fti = queryUtility(IDexterityFTI, name='Bpm Attachment')
        factory = fti.factory
        obj = createObject(factory)


    def test_ct_bpm_attachment_adding(self):
        setRoles(self.portal, TEST_USER_ID, ['Contributor'])
        obj = api.content.create(
            container=self.parent,
            type='Bpm Attachment',
            id='bpm_attachment',
        )


        parent = obj.__parent__
        self.assertIn('bpm_attachment', parent.objectIds())

        # check that deleting the object works too
        api.content.delete(obj=obj)
        self.assertNotIn('bpm_attachment', parent.objectIds())

    def test_ct_bpm_attachment_globally_not_addable(self):
        setRoles(self.portal, TEST_USER_ID, ['Contributor'])
        fti = queryUtility(IDexterityFTI, name='Bpm Attachment')
        self.assertFalse(
            fti.global_allow,
            u'{0} is globally addable!'.format(fti.id)
        )
