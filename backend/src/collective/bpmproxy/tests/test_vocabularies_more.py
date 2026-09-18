from collective.bpmproxy.vocabularies import VocabItem
from collective.bpmproxy.vocabularies.available_process_definitions import (
    AvailableProcessDefinitionsFactory,
)
from collective.bpmproxy.vocabularies.task_attachments import TaskAttachmentsFactory
from unittest.mock import MagicMock
from unittest.mock import patch
import unittest


class TestAvailableProcessDefinitions(unittest.TestCase):
    def test_vocab_item_init(self):
        item = VocabItem("token1", "value1")
        self.assertEqual(item.token, "token1")
        self.assertEqual(item.value, "value1")

    @patch(
        "collective.bpmproxy.vocabularies.available_process_definitions.camunda_client"
    )
    @patch(
        "collective.bpmproxy.vocabularies.available_process_definitions.get_tenant_ids"
    )
    @patch("generic_camunda_client.ProcessDefinitionApi")
    def test_call_with_definitions(
        self, mock_process_definition_api, mock_get_tenant_ids, mock_camunda_client
    ):
        mock_client_instance = MagicMock()
        mock_camunda_client.return_value.__enter__.return_value = mock_client_instance

        mock_get_tenant_ids.return_value = ["tenant1", "tenant2"]

        mock_api_instance = MagicMock()
        mock_process_definition_api.return_value = mock_api_instance

        def1 = MagicMock()
        def1.key = "key1"
        def1.tenant_id = "tenant1"
        def1.name = "Name 1"

        def2 = MagicMock()
        def2.key = "key2"
        def2.tenant_id = ""
        def2.name = ""

        mock_api_instance.get_process_definitions.return_value = [def1, def2]

        context = MagicMock()
        vocab = AvailableProcessDefinitionsFactory(context)

        self.assertEqual(len(vocab), 2)

        terms = list(vocab)
        self.assertEqual(terms[0].value, "key1:tenant1")
        self.assertEqual(terms[0].title, "Name 1 [tenant1]")

        self.assertEqual(terms[1].value, "key2")
        self.assertEqual(terms[1].title, "n/a")

    @patch(
        "collective.bpmproxy.vocabularies.available_process_definitions.camunda_client"
    )
    @patch(
        "collective.bpmproxy.vocabularies.available_process_definitions.get_tenant_ids"
    )
    @patch("generic_camunda_client.ProcessDefinitionApi")
    def test_call_with_api_exception(
        self, mock_process_definition_api, mock_get_tenant_ids, mock_camunda_client
    ):
        mock_client_instance = MagicMock()
        mock_camunda_client.return_value.__enter__.return_value = mock_client_instance

        mock_get_tenant_ids.return_value = ["tenant1"]

        mock_api_instance = MagicMock()
        mock_process_definition_api.return_value = mock_api_instance

        import generic_camunda_client

        mock_api_instance.get_process_definitions.side_effect = (
            generic_camunda_client.rest.ApiException()
        )

        context = MagicMock()
        vocab = AvailableProcessDefinitionsFactory(context)

        self.assertEqual(len(vocab), 0)


class TestTaskAttachments(unittest.TestCase):
    @patch("plone.api.portal.getRequest")
    @patch("collective.bpmproxy.vocabularies.task_attachments.AttachmentsListing")
    def test_call_success(self, mock_attachments_listing, mock_getRequest):
        mock_request = MagicMock()
        mock_request.PUBLISHED.attachments_key = "attach_key"
        mock_getRequest.return_value = mock_request

        mock_context = MagicMock()
        mock_attachments = MagicMock()

        def context_getitem(key):
            if key == "attach_key":
                return mock_attachments
            raise KeyError(key)

        mock_context.__getitem__.side_effect = context_getitem

        mock_listing_instance = MagicMock()
        mock_attachments_listing.return_value = mock_listing_instance

        mock_item1 = MagicMock()
        mock_item1.uuid.return_value = "uuid1"
        mock_item1.title = "title1"

        mock_item2 = MagicMock()
        mock_item2.uuid.return_value = "uuid2"
        mock_item2.title = "title2"

        mock_listing_instance.return_value = [mock_item1, mock_item2]

        vocab = TaskAttachmentsFactory(mock_context)

        self.assertEqual(len(vocab), 2)
        terms = list(vocab)
        self.assertEqual(terms[0].value, "uuid1")
        self.assertEqual(terms[0].token, "uuid1")
        self.assertEqual(terms[0].title, "title1")

        self.assertEqual(terms[1].value, "uuid2")
        self.assertEqual(terms[1].token, "uuid2")
        self.assertEqual(terms[1].title, "title2")

    @patch("plone.api.portal.getRequest")
    def test_call_key_error(self, mock_getRequest):
        mock_request = MagicMock()
        mock_request.PUBLISHED.attachments_key = "attach_key"
        mock_getRequest.return_value = mock_request

        mock_context = MagicMock()
        mock_context.__getitem__.side_effect = KeyError("attach_key")

        vocab = TaskAttachmentsFactory(mock_context)
        self.assertEqual(len(vocab), 0)

    @patch("plone.api.portal.getRequest")
    def test_call_attribute_error(self, mock_getRequest):
        class MockRequest:
            @property
            def PUBLISHED(self):
                raise AttributeError("no PUBLISHED")

        mock_getRequest.return_value = MockRequest()
        mock_context = MagicMock()

        vocab = TaskAttachmentsFactory(mock_context)
        self.assertEqual(len(vocab), 0)
