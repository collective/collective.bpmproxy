# -*- coding: utf-8 -*-

from collective.bpmproxy.client import camunda_client
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm, SimpleVocabulary

import generic_camunda_client

from collective.bpmproxy.utils import get_tenant_ids


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
            tenant_ids = get_tenant_ids()
            definitions = definition_api.get_process_definitions(
                latest_version="true",
                tenant_id_in=",".join(tenant_ids) or None,
                include_process_definitions_without_tenant_id="true",
            )
            items = [
                VocabItem(
                    ":".join(filter(bool, [definition.key, definition.tenant_id])),
                    definition.tenant_id
                    and (definition.name or "n/a") + " [" + definition.tenant_id + "]"
                    or (definition.name or "n/a"),
                )
                for definition in definitions
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
