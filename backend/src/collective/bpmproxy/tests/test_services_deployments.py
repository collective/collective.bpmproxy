from collective.bpmproxy.services.deployments import DeploymentsDelete
from collective.bpmproxy.services.deployments import DeploymentsGet
from unittest import mock
import json
import unittest


class MockDeployment:
    id = "dep-123"
    name = "Test Deployment"
    source = "Plone Proxy"
    deployment_time = "2023-01-01T12:00:00"
    tenant_id = "tenant-1"


def make_service(factory, method, body=None):
    service = factory()
    service.context = mock.MagicMock()
    service.request = mock.MagicMock()
    service.request.method = method
    service.request.get.return_value = json.dumps(body or {})
    service.request.response = mock.MagicMock()
    return service


class TestServicesDeployments(unittest.TestCase):
    @mock.patch("collective.bpmproxy.services.deployments.get_deployments")
    @mock.patch("collective.bpmproxy.services.deployments.camunda_client")
    def test_get_deployments(self, _mock_client, mock_get_deployments):
        mock_get_deployments.return_value = [MockDeployment()]

        result = make_service(DeploymentsGet, "GET").reply()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "dep-123")
        self.assertEqual(result[0]["name"], "Test Deployment")

    @mock.patch(
        "collective.bpmproxy.services.deployments.camunda_client",
        side_effect=Exception("API Error"),
    )
    def test_get_deployments_engine_error(self, _mock_client):
        service = make_service(DeploymentsGet, "GET")

        result = service.reply()

        # The internal exception text must not reach the client.
        self.assertNotIn("API Error", result["error"])
        self.assertIn("see the Plone log", result["error"])
        service.request.response.setStatus.assert_called_with(500)

    @mock.patch("collective.bpmproxy.services.deployments.delete_deployment")
    @mock.patch("collective.bpmproxy.services.deployments.camunda_client")
    def test_delete_deployment(self, _mock_client, mock_delete_deployment):
        result = make_service(DeploymentsDelete, "DELETE", {"id": "dep-123"}).reply()

        self.assertEqual(result["status"], "deleted")
        self.assertEqual(result["id"], "dep-123")
        mock_delete_deployment.assert_called_once()

    @mock.patch("collective.bpmproxy.services.deployments.delete_deployment")
    @mock.patch("collective.bpmproxy.services.deployments.camunda_client")
    def test_delete_deployment_without_id(self, _mock_client, mock_delete_deployment):
        service = make_service(DeploymentsDelete, "DELETE")
        service.request.form = {}

        result = service.reply()

        self.assertIn("error", result)
        service.request.response.setStatus.assert_called_with(400)
        mock_delete_deployment.assert_not_called()

    @mock.patch("collective.bpmproxy.services.deployments.delete_deployment")
    @mock.patch("collective.bpmproxy.services.deployments.camunda_client")
    def test_delete_deployment_id_from_query_string(
        self, _mock_client, mock_delete_deployment
    ):
        service = make_service(DeploymentsDelete, "DELETE")
        service.request.form = {"id": "dep-456"}

        result = service.reply()

        self.assertEqual(result["id"], "dep-456")
        mock_delete_deployment.assert_called_once()

    @mock.patch(
        "collective.bpmproxy.services.deployments.camunda_client",
        side_effect=Exception("API Error"),
    )
    def test_delete_deployment_engine_error(self, _mock_client):
        service = make_service(DeploymentsDelete, "DELETE", {"id": "dep-123"})

        result = service.reply()

        # The internal exception text must not reach the client.
        self.assertNotIn("API Error", result["error"])
        self.assertIn("see the Plone log", result["error"])
        service.request.response.setStatus.assert_called_with(500)
