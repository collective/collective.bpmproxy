# -*- coding: utf-8 -*-

# from plone import api
from collective.bpmproxy import _
from collective.bpmproxy.client import get_api_url, get_authorization
from plone.dexterity.interfaces import IDexterityContent
from zope.globalrequest import getRequest
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm, SimpleVocabulary

import generic_camunda_client


class VocabItem(object):
    def __init__(self, token, value):
        self.token = token
        self.value = value


@implementer(IVocabularyFactory)
class AvailableProcessDefinitions(object):
    """ """

    def __call__(self, context):
        # Just an example list of content for our vocabulary,
        # this can be any static or dynamic data, a catalog result for example.
        api = generic_camunda_client.Configuration(host=get_api_url())
        authorization = get_authorization()
        with generic_camunda_client.ApiClient(
            api,
            header_name=authorization and "Authorization" or None,
            header_value=authorization,
        ) as client:
            api = generic_camunda_client.ProcessDefinitionApi(client)
            definitions = api.get_process_definitions(latest_version="true")
            items = [
                VocabItem(definition.key, definition.name) for definition in definitions
            ]

        # Fix context if you are using the vocabulary in DataGridField.
        # See https://github.com/collective/collective.z3cform.datagridfield/issues/31:  # NOQA: 501
        if not IDexterityContent.providedBy(context):
            req = getRequest()
            context = req.PARENTS[0]

        # create a list of SimpleTerm items:
        terms = []
        for item in items:
            terms.append(
                SimpleTerm(
                    value=item.token,
                    token=str(item.token),
                    title=item.value,
                )
            )
        # Create a SimpleVocabulary from the terms list and return it:
        return SimpleVocabulary(terms)


AvailableProcessDefinitionsFactory = AvailableProcessDefinitions()
