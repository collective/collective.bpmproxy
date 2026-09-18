from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from collective.bpmproxy.tests.helpers import process_context_behavior_enabled
from collective.bpmproxy.viewlets.bpm_attachments_tasks_viewlet import (
    BpmAttachmentsTasksViewlet,
)
from collective.bpmproxy.viewlets.bpm_attachments_viewlet import BpmAttachmentsViewlet
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.dexterity.utils import createContentInContainer
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


class TestBpmAttachmentsTasksViewletNestedProcessContexts(unittest.TestCase):
    """Nested process contexts are now possible since process_context is a
    behavior, not just Bpm Proxy's own schema. This is the case that
    motivated taking the *nearest* ancestor instead of the outermost one --
    covered here with real nested content, not a mocked parents().
    """

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    @patch("collective.bpmproxy.viewlets.bpm_attachments_tasks_viewlet.camunda_client")
    @patch(
        "collective.bpmproxy.viewlets.bpm_attachments_tasks_viewlet.get_available_tasks"
    )
    def test_nested_process_context_uses_the_inner_one(
        self, mock_get_available_tasks, mock_camunda_client
    ):
        portal = self.layer["portal"]
        setRoles(portal, TEST_USER_ID, ["Manager"])
        mock_get_available_tasks.return_value = ["task1"]

        with process_context_behavior_enabled("Folder"):
            outer = api.content.create(portal, "Folder", "outer")
            inner = api.content.create(outer, "Folder", "inner")
            attachments = createContentInContainer(
                inner, "Bpm Attachments", checkConstraints=False, id="attachments"
            )

            viewlet = BpmAttachmentsTasksViewlet(
                attachments, portal.REQUEST, MagicMock(), MagicMock()
            )
            viewlet.update()

            # Not the outer folder: the nearest process context is "inner".
            self.assertEqual(viewlet.base_url, inner.absolute_url())
            self.assertEqual(viewlet.tasks, ["task1"])
            self.assertEqual(
                mock_get_available_tasks.call_args.kwargs["context_key"],
                api.content.get_uuid(inner),
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
