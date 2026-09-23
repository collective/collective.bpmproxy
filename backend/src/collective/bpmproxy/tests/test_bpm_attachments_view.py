from collective.bpmproxy.interfaces import ATTACHMENTS_DEFAULT_TYPE
from collective.bpmproxy.interfaces import BUSINESS_KEY_VARIABLE_NAME
from collective.bpmproxy.views.bpm_attachments_view import BpmProxyTaskAttachmentsView
from generic_camunda_client import ApiException
from unittest.mock import MagicMock
from unittest.mock import patch
from zope.publisher.interfaces import NotFound
import unittest


class TestBpmProxyTaskAttachmentsView(unittest.TestCase):
    def setUp(self):
        self.context_wrapper = MagicMock()
        self.context = MagicMock()
        self.context.attachments_enabled = True
        self.context_wrapper.context = self.context
        self.context_wrapper.task_id = "task_123"
        self.request = MagicMock()

    def test_call_attachments_disabled(self):
        self.context.attachments_enabled = False
        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        self.assertEqual(view(), "")

    @patch("collective.bpmproxy.views.bpm_attachments_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_available_tasks")
    def test_call_task_not_found_on_context(
        self, mock_get_tasks, mock_camunda_client, mock_iuuid
    ):
        mock_task = MagicMock()
        mock_task.id = "other_task"
        mock_get_tasks.return_value = [mock_task]

        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        with self.assertRaises(NotFound):
            view()

    @patch("collective.bpmproxy.views.bpm_attachments_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_task_variables")
    def test_call_missing_business_key(
        self, mock_get_vars, mock_get_tasks, mock_camunda_client, mock_iuuid
    ):
        mock_task = MagicMock()
        mock_task.id = "task_123"
        mock_get_tasks.return_value = [mock_task]

        mock_get_vars.return_value = {}

        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        with self.assertRaises(NotFound):
            view()

    @patch("collective.bpmproxy.views.bpm_attachments_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_task_variables")
    def test_call_invalid_business_key(
        self, mock_get_vars, mock_get_tasks, mock_camunda_client, mock_iuuid
    ):
        mock_task = MagicMock()
        mock_task.id = "task_123"
        mock_get_tasks.return_value = [mock_task]

        mock_get_vars.return_value = {BUSINESS_KEY_VARIABLE_NAME: "foo:bar"}

        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        with self.assertRaises(NotFound):
            view()

    @patch("collective.bpmproxy.views.bpm_attachments_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_task_variables")
    def test_call_invalid_uuid(
        self, mock_get_vars, mock_get_tasks, mock_camunda_client, mock_iuuid
    ):
        mock_task = MagicMock()
        mock_task.id = "task_123"
        mock_get_tasks.return_value = [mock_task]

        mock_get_vars.return_value = {BUSINESS_KEY_VARIABLE_NAME: "prefix:not-a-uuid"}

        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        with self.assertRaises(NotFound):
            view()

    @patch("collective.bpmproxy.views.bpm_attachments_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_task_variables")
    def test_call_task_not_found_on_attachments_key(
        self, mock_get_vars, mock_get_tasks, mock_camunda_client, mock_iuuid
    ):
        mock_task = MagicMock()
        mock_task.id = "task_123"

        mock_other_task = MagicMock()
        mock_other_task.id = "other"

        mock_get_tasks.side_effect = [[mock_task], [mock_other_task]]

        mock_get_vars.return_value = {
            BUSINESS_KEY_VARIABLE_NAME: "prefix:00000000-0000-0000-0000-000000000000"
        }

        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        with self.assertRaises(NotFound):
            view()

    @patch("collective.bpmproxy.views.bpm_attachments_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_task_variables")
    def test_call_existing_container(
        self, mock_get_vars, mock_get_tasks, mock_camunda_client, mock_iuuid
    ):
        mock_task = MagicMock()
        mock_task.id = "task_123"

        mock_get_tasks.side_effect = [[mock_task], [mock_task]]

        mock_get_vars.return_value = {
            BUSINESS_KEY_VARIABLE_NAME: "prefix:00000000-0000-0000-0000-000000000000"
        }

        mock_container = MagicMock()
        mock_container.absolute_url.return_value = "http://container"
        self.context.get.return_value = mock_container

        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        view()

        self.request.response.redirect.assert_called_once_with(
            "http://container/++add++" + ATTACHMENTS_DEFAULT_TYPE
        )

    @patch("collective.bpmproxy.views.bpm_attachments_view.IRoleManager")
    @patch("collective.bpmproxy.views.bpm_attachments_view.IOwned")
    @patch("collective.bpmproxy.views.bpm_attachments_view.createContentInContainer")
    @patch("collective.bpmproxy.views.bpm_attachments_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_task_variables")
    def test_call_create_container(
        self,
        mock_get_vars,
        mock_get_tasks,
        mock_camunda_client,
        mock_iuuid,
        mock_create,
        mock_iowned,
        mock_irole,
    ):
        mock_task = MagicMock()
        mock_task.id = "task_123"

        mock_get_tasks.side_effect = [[mock_task], [mock_task]]

        mock_get_vars.return_value = {
            BUSINESS_KEY_VARIABLE_NAME: "prefix:00000000-0000-0000-0000-000000000000"
        }

        self.context.get.return_value = None

        mock_container = MagicMock()
        mock_container.absolute_url.return_value = "http://container"
        mock_create.return_value = mock_container

        mock_iowned.return_value._deleteOwnershipAfterAdd = MagicMock()
        mock_irole_inst = MagicMock()
        mock_irole_inst.get_local_roles.return_value = [("role1", "dummy")]
        mock_irole.return_value = mock_irole_inst

        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        view()

        self.request.response.redirect.assert_called_once_with(
            "http://container/++add++" + ATTACHMENTS_DEFAULT_TYPE
        )

        mock_create.assert_called_once()
        mock_irole_inst.manage_delLocalRoles.assert_called_once()
        self.assertTrue(mock_container.__ac_local_roles_block__)
        mock_container.reindexObject.assert_called_once()

    @patch("collective.bpmproxy.views.bpm_attachments_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_view.get_available_tasks")
    def test_call_api_exception(self, mock_get_tasks, mock_camunda_client, mock_iuuid):
        mock_get_tasks.side_effect = ApiException(status=500, reason="Internal Error")

        view = BpmProxyTaskAttachmentsView(self.context_wrapper, self.request)
        with self.assertRaises(NotFound):
            view()
