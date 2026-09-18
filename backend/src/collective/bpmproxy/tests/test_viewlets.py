from collective.bpmproxy.viewlets.bpm_attachments_tasks_viewlet import (
    BpmAttachmentsTasksViewlet,
)
from collective.bpmproxy.viewlets.bpm_attachments_viewlet import BpmAttachmentsViewlet
from unittest.mock import MagicMock
from unittest.mock import patch
import unittest


class TestBpmAttachmentsTasksViewlet(unittest.TestCase):
    @patch("collective.bpmproxy.viewlets.bpm_attachments_tasks_viewlet.parents")
    @patch("collective.bpmproxy.viewlets.bpm_attachments_tasks_viewlet.IUUID")
    @patch("collective.bpmproxy.viewlets.bpm_attachments_tasks_viewlet.camunda_client")
    @patch(
        "collective.bpmproxy.viewlets.bpm_attachments_tasks_viewlet.get_available_tasks"
    )
    def test_update(
        self, mock_get_available_tasks, mock_camunda_client, mock_IUUID, mock_parents
    ):
        viewlet = BpmAttachmentsTasksViewlet(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        viewlet.context = MagicMock()

        mock_bpm_proxy = MagicMock()
        mock_bpm_proxy.absolute_url.return_value = "http://example.com"

        mock_bpm_attachments = MagicMock()
        mock_bpm_attachments.id = "attach_123"

        def parents_side_effect(context, iface):
            from collective.bpmproxy.behaviors.process_context import IProcessContext
            from collective.bpmproxy.content.bpm_attachments import IBpmAttachments

            if iface == IProcessContext and context == viewlet.context:
                return [mock_bpm_proxy]
            elif iface == IBpmAttachments and context == viewlet.context:
                return [mock_bpm_attachments]
            elif iface == IProcessContext and context == mock_bpm_attachments:
                return [mock_bpm_proxy]
            return []

        mock_parents.side_effect = parents_side_effect

        mock_client_instance = MagicMock()
        mock_camunda_client.return_value.__enter__.return_value = mock_client_instance

        mock_get_available_tasks.return_value = ["task1", "task2"]
        mock_IUUID.return_value = "uuid-123"

        viewlet.update()

        self.assertEqual(viewlet.base_url, "http://example.com")
        self.assertEqual(viewlet.tasks, ["task1", "task2"])
        mock_get_available_tasks.assert_called_once_with(
            mock_client_instance,
            context_key="uuid-123",
            attachments_key="attach_123",
            for_display=True,
        )


class TestBpmAttachmentsViewlet(unittest.TestCase):
    def test_update(self):
        viewlet = BpmAttachmentsViewlet(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        self.assertIsNone(viewlet.update())

    @patch("plone.app.layout.viewlets.ViewletBase.render")
    def test_index_enabled(self, mock_render):
        viewlet = BpmAttachmentsViewlet(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        viewlet.view = MagicMock()
        viewlet.view.attachments_enabled = True
        mock_render.return_value = "rendered"

        self.assertEqual(viewlet.index(), "rendered")
        mock_render.assert_called_once()

    def test_index_disabled(self):
        viewlet = BpmAttachmentsViewlet(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        viewlet.view = MagicMock()
        viewlet.view.attachments_enabled = False

        self.assertEqual(viewlet.index(), "")

    def test_attachments_context_found(self):
        viewlet = BpmAttachmentsViewlet(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        viewlet.view = MagicMock()
        viewlet.view.attachments_key = "key1"

        mock_context = MagicMock()
        mock_context.__len__.return_value = 1

        viewlet.context = MagicMock()
        viewlet.context.get.return_value = mock_context

        self.assertEqual(viewlet.attachments_context, mock_context)

    def test_attachments_context_not_found_or_empty(self):
        viewlet = BpmAttachmentsViewlet(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        viewlet.view = MagicMock()
        viewlet.view.attachments_key = "key1"

        # None returned by get
        viewlet.context = MagicMock()
        viewlet.context.get.return_value = None
        self.assertIsNone(viewlet.attachments_context)

        # Empty context
        mock_context = MagicMock()
        mock_context.__len__.return_value = 0
        viewlet.context.get.return_value = mock_context
        self.assertIsNone(viewlet.attachments_context)
