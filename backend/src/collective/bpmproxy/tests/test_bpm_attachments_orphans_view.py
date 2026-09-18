from collective.bpmproxy.interfaces import CAMUNDA_ADMIN_GROUP
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from collective.bpmproxy.tests.helpers import process_context_behavior_enabled
from collective.bpmproxy.views.bpm_attachments_orphans_view import (
    BpmAttachmentsOrphansView,
)
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.dexterity.utils import createContentInContainer
from unittest.mock import MagicMock
from unittest.mock import patch
import json
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


class TestBpmAttachmentsOrphansViewOnBehaviorEnabledContainer(unittest.TestCase):
    """The view now walks IProcessContext, not just Bpm Proxy -- cover a
    behavior-enabled container with real content, a real catalog query and
    a real parents() walk. Only the engine call itself is mocked.
    """

    layer = COLLECTIVE_BPMPROXY_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager", "Contributor"])
        if not api.group.get(CAMUNDA_ADMIN_GROUP):
            api.group.create(groupname=CAMUNDA_ADMIN_GROUP)
        api.group.add_user(groupname=CAMUNDA_ADMIN_GROUP, username=TEST_USER_NAME)

    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.get_available_tasks")
    def test_finds_orphans_under_a_behavior_enabled_container(
        self, mock_get_tasks, mock_camunda_client
    ):
        with process_context_behavior_enabled("Folder"):
            container = api.content.create(self.portal, "Folder", "container")
            attachments = createContentInContainer(
                container,
                "Bpm Attachments",
                checkConstraints=False,
                id="attachments",
            )

            mock_get_tasks.return_value = []  # no tasks -> orphaned

            view = BpmAttachmentsOrphansView(self.portal, self.portal.REQUEST)
            result = json.loads(view())

            self.assertEqual(result, [attachments.absolute_url()])
            self.assertEqual(
                mock_get_tasks.call_args.kwargs["context_key"],
                api.content.get_uuid(container),
            )

    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_attachments_orphans_view.get_available_tasks")
    def test_not_orphaned_when_tasks_exist(self, mock_get_tasks, mock_camunda_client):
        with process_context_behavior_enabled("Folder"):
            container = api.content.create(self.portal, "Folder", "container")
            createContentInContainer(
                container, "Bpm Attachments", checkConstraints=False, id="attachments"
            )

            mock_get_tasks.return_value = ["task1"]

            view = BpmAttachmentsOrphansView(self.portal, self.portal.REQUEST)
            result = json.loads(view())

            self.assertEqual(result, [])
