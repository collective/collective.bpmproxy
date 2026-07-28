from collective.bpmproxy.adapters.security import AttachmentsLocalRoleProvider
from unittest.mock import MagicMock
from unittest.mock import patch
import unittest


class TestSecurity(unittest.TestCase):
    def test_attachments_local_role_provider_getRoles_no_proxy(self):
        class MockContext:
            id = "mock_id"

        context = MockContext()
        with (
            patch("collective.bpmproxy.adapters.security.parents", return_value=[]),
            patch("plone.api.portal.getRequest"),
            patch("plone.api.user.get"),
        ):
            provider = AttachmentsLocalRoleProvider(context)
            # bypass cache for test
            roles = provider.getRoles.__wrapped__(provider, "test_user")
            self.assertEqual(roles, ())

    def test_attachments_local_role_provider_getRoles_with_proxy(self):
        class MockContext:
            id = "mock_id"

        context = MockContext()
        proxy = MagicMock()

        with (
            patch(
                "collective.bpmproxy.adapters.security.parents", return_value=[proxy]
            ),
            patch("plone.api.portal.getRequest"),
            patch("plone.api.user.get", return_value=True),
            patch("collective.bpmproxy.adapters.security.camunda_client"),
            patch(
                "collective.bpmproxy.adapters.security.get_available_tasks",
                return_value=[True],
            ),
            patch("collective.bpmproxy.adapters.security.IUUID", return_value="uuid"),
        ):
            provider = AttachmentsLocalRoleProvider(context)
            roles = provider.getRoles.__wrapped__(provider, "test_user")
            self.assertEqual(roles, ("Contributor", "Editor"))

    def test_attachments_local_role_provider_getRoles_with_proxy_no_tasks(self):
        class MockContext:
            id = "mock_id"

        context = MockContext()
        proxy = MagicMock()

        with (
            patch(
                "collective.bpmproxy.adapters.security.parents", return_value=[proxy]
            ),
            patch("plone.api.portal.getRequest"),
            patch("plone.api.user.get", return_value=True),
            patch("collective.bpmproxy.adapters.security.camunda_client"),
            patch(
                "collective.bpmproxy.adapters.security.get_available_tasks",
                return_value=[],
            ),
            patch("collective.bpmproxy.adapters.security.IUUID", return_value="uuid"),
        ):
            provider = AttachmentsLocalRoleProvider(context)
            roles = provider.getRoles.__wrapped__(provider, "test_user")
            self.assertEqual(roles, ())

    def test_getAllRoles(self):
        class MockContext:
            pass

        context = MockContext()
        with (
            patch("collective.bpmproxy.adapters.security.parents", return_value=[]),
            patch("plone.api.portal.getRequest"),
        ):
            provider = AttachmentsLocalRoleProvider(context)
            self.assertEqual(provider.getAllRoles(), [])
