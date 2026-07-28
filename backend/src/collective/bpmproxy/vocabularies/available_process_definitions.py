from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.utils import get_tenant_ids
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary
import generic_camunda_client
import urllib3.exceptions


class VocabItem:
    def __init__(self, token, value):
        self.token = token
        self.value = value


@implementer(IVocabularyFactory)
class AvailableProcessDefinitions:
    """ """

    def __call__(self, context):
        with camunda_client() as client:
            definition_api = generic_camunda_client.ProcessDefinitionApi(client)
            tenant_ids = get_tenant_ids()
            try:
                definitions = definition_api.get_process_definitions(
                    latest_version="true",
                    tenant_id_in=",".join(tenant_ids) or None,
                    include_process_definitions_without_tenant_id="true",
                )
            except (
                generic_camunda_client.rest.ApiException,
                OSError,
                urllib3.exceptions.HTTPError,
            ):
                # Engine unreachable or credentials missing: degrade to an
                # empty vocabulary instead of breaking every edit form.
                definitions = []
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
