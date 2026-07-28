from collective.bpmproxy.views.bpm_attachments_orphans_view import (
    BpmAttachmentsOrphansView,
)
from unittest.mock import MagicMock
from unittest.mock import patch
import unittest


class TestBpmAttachmentsOrphansView(unittest.TestCase):
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.plone.api")
    def test_call_no_admin_group(self, mock_api):
        context = MagicMock()
        request = MagicMock()

        mock_group = MagicMock()
        mock_group.getId.return_value = "some_other_group"
        mock_api.group.get_groups.return_value = [mock_group]

        view = BpmAttachmentsOrphansView(context, request)
        result = view()

        self.assertEqual(result, "[]")
        request.response.setHeader.assert_called_once_with(
            "Content-Type", "application/json"
        )

    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.parents")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.plone.api")
    def test_call_with_admin_group_no_tasks(
        self, mock_api, mock_get_tasks, mock_iuuid, mock_parents, mock_camunda_client
    ):
        context = MagicMock()
        request = MagicMock()

        mock_group = MagicMock()
        mock_group.getId.return_value = "camunda-admin"
        mock_api.group.get_groups.return_value = [mock_group]

        mock_pc = MagicMock()
        mock_api.portal.get_tool.return_value = mock_pc

        mock_brain = MagicMock()
        mock_ob = MagicMock()
        mock_ob.id = "ob_id"
        mock_ob.absolute_url.return_value = "http://ob_url"
        mock_brain.getObject.return_value = mock_ob

        mock_pc.return_value = [mock_brain]

        mock_parent_context = MagicMock()
        mock_parents.return_value = [mock_parent_context]
        mock_iuuid.return_value = "parent_uuid"

        mock_get_tasks.return_value = []

        mock_client_ctx = MagicMock()
        mock_camunda_client.return_value.__enter__.return_value = mock_client_ctx

        view = BpmAttachmentsOrphansView(context, request)
        result = view()

        self.assertEqual(result, '["http://ob_url"]')
        mock_get_tasks.assert_called_once_with(
            mock_client_ctx, context_key="parent_uuid", attachments_key="ob_id"
        )

    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.parents")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.IUUID")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.plone.api")
    def test_call_with_admin_group_has_tasks(
        self, mock_api, mock_get_tasks, mock_iuuid, mock_parents, mock_camunda_client
    ):
        context = MagicMock()
        request = MagicMock()

        mock_group = MagicMock()
        mock_group.getId.return_value = "camunda-admin"
        mock_api.group.get_groups.return_value = [mock_group]

        mock_pc = MagicMock()
        mock_api.portal.get_tool.return_value = mock_pc

        mock_brain = MagicMock()
        mock_ob = MagicMock()
        mock_ob.id = "ob_id"
        mock_ob.absolute_url.return_value = "http://ob_url"
        mock_brain.getObject.return_value = mock_ob

        mock_pc.return_value = [mock_brain]

        mock_parent_context = MagicMock()
        mock_parents.return_value = [mock_parent_context]
        mock_iuuid.return_value = "parent_uuid"

        mock_get_tasks.return_value = ["task1"]

        mock_client_ctx = MagicMock()
        mock_camunda_client.return_value.__enter__.return_value = mock_client_ctx

        view = BpmAttachmentsOrphansView(context, request)
        result = view()

        self.assertEqual(result, "[]")
