# -*- coding: utf-8 -*-

from collective.bpmproxy.client import camunda_client
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
        with camunda_client() as client:
            definition_api = generic_camunda_client.ProcessDefinitionApi(client)
            definitions = definition_api.get_process_definitions(latest_version="true")
            items = [
                VocabItem(definition.key, definition.name) for definition in definitions
            ]

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
