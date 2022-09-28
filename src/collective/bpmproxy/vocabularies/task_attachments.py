# -*- coding: utf-8 -*-
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.views.bpm_attachments_listing import AttachmentsListing
from plone.uuid.interfaces import IUUID
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm, SimpleVocabulary

import generic_camunda_client
import plone.api


class VocabItem(object):
    def __init__(self, token, value):
        self.token = token
        self.value = value


@implementer(IVocabularyFactory)
class TaskAttachments(object):
    """ """

    def __call__(self, context):
        request = plone.api.portal.getRequest()
        try:
            attachments = context[request.PUBLISHED.attachments_key]
        except (AttributeError, KeyError):
            return SimpleVocabulary([])

        listing = AttachmentsListing(attachments, context.REQUEST)()

        terms = []
        for item in listing:
            uuid = item.uuid()
            terms.append(SimpleTerm(value=uuid, token=uuid, title=item.title))

        return SimpleVocabulary(terms)


TaskAttachmentsFactory = TaskAttachments()
