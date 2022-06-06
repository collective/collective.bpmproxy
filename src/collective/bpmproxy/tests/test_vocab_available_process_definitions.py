# -*- coding: utf-8 -*-
from collective.bpmproxy import _
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING  # noqa
from plone.app.testing import setRoles, TEST_USER_ID
from zope.component import getUtility
from zope.schema.interfaces import IVocabularyFactory, IVocabularyTokenized

import unittest


class AvailableProcessDefinitionsIntegrationTest(unittest.TestCase):

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_vocab_available_process_definitions(self):
        vocab_name = "collective.bpmproxy.AvailableProcessDefinitions"
        factory = getUtility(IVocabularyFactory, vocab_name)
        self.assertTrue(IVocabularyFactory.providedBy(factory))

        vocabulary = factory(self.portal)
        self.assertTrue(IVocabularyTokenized.providedBy(vocabulary))
        self.assertEqual(
            vocabulary.getTerm("sony-a7r-iii").title,
            _(u"Sony Aplha 7R III"),
        )
