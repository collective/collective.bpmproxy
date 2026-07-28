from collective.bpmproxy.services.deploy import DeployProcess
from unittest import mock
import json


def test_deploy_process_service():
    service = DeployProcess()
    service.context = mock.MagicMock()
    service.request = mock.MagicMock()

    # Missing XML
    service.request = mock.MagicMock()
    service.request.get.return_value = json.dumps({})
    service.request.response = mock.MagicMock()
    result = service.reply()
    assert "error" in result
    service.request.response.setStatus.assert_called_with(400)

    # Success
    service.request.get.return_value = json.dumps({"xml": "<bpmn>", "name": "test"})
    with mock.patch("collective.bpmproxy.services.deploy.camunda_client"):
        with mock.patch(
            "collective.bpmproxy.services.deploy.deploy_process"
        ) as mock_deploy:
            mock_deploy.return_value = {"id": "123"}
            result = service.reply()
            assert result["status"] == "deployed"
            assert result["result"] == {"id": "123"}

    # Exception
    with mock.patch(
        "collective.bpmproxy.services.deploy.camunda_client",
        side_effect=Exception("API Error"),
    ):
        result = service.reply()
        assert "error" in result
        assert result["error"] == "API Error"
        service.request.response.setStatus.assert_called_with(500)


def make_service(body):
    service = DeployProcess()
    service.context = mock.MagicMock()
    service.request = mock.MagicMock()
    service.request.get.return_value = body
    service.request.response = mock.MagicMock()
    return service


def test_deploy_process_invalid_json():
    service = make_service("{not json")

    result = service.reply()

    assert "Invalid JSON" in result["error"]
    service.request.response.setStatus.assert_called_with(400)


def test_deploy_process_empty_body():
    service = make_service("")

    result = service.reply()

    assert result["error"] == "Missing 'xml' payload"
    service.request.response.setStatus.assert_called_with(400)


def test_deploy_process_defaults_extension_to_bpmn():
    service = make_service(json.dumps({"xml": "<bpmn/>", "name": "my-process"}))

    with mock.patch("collective.bpmproxy.services.deploy.camunda_client"):
        with mock.patch(
            "collective.bpmproxy.services.deploy.deploy_process"
        ) as mock_deploy:
            service.reply()

    assert mock_deploy.call_args[0][1] == "my-process.bpmn"


def test_deploy_process_keeps_known_extensions():
    for name in ("decision.dmn", "contact.form", "process.bpmn"):
        service = make_service(json.dumps({"xml": "<xml/>", "name": name}))
        with mock.patch("collective.bpmproxy.services.deploy.camunda_client"):
            with mock.patch(
                "collective.bpmproxy.services.deploy.deploy_process"
            ) as mock_deploy:
                service.reply()
        assert mock_deploy.call_args[0][1] == name
