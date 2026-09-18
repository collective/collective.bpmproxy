from collective.bpmproxy.actions.message import _throwMessage
from collective.bpmproxy.actions.message import BpmMessageAction
from collective.bpmproxy.actions.message import BpmMessageActionExecutor
from collective.bpmproxy.actions.message import BpmMessageAddForm
from collective.bpmproxy.actions.message import BpmMessageAddFormView
from collective.bpmproxy.actions.message import BpmMessageEditForm
from collective.bpmproxy.actions.message import BpmMessageEditFormView
from unittest.mock import MagicMock
from unittest.mock import patch


def test_bpmmessageaction():
    action = BpmMessageAction()
    action.name = "test_message"
    assert action.summary == "test_message"


@patch("collective.bpmproxy.actions.message.camunda_admin_client")
@patch("collective.bpmproxy.actions.message.generic_camunda_client.MessageApi")
@patch("collective.bpmproxy.actions.message.infer_variables")
def test_throw_message_with_tenants(
    mock_infer_vars, mock_message_api_cls, mock_admin_client
):
    mock_client = MagicMock()
    mock_admin_client.return_value.__enter__.return_value = mock_client
    mock_api = MagicMock()
    mock_message_api_cls.return_value = mock_api
    mock_infer_vars.return_value = {"inferred": "vars"}

    _throwMessage(
        "my_message",
        "bk-1",
        {"uuid": "abc"},
        {"payload": "data"},
        "user1",
        ["tenant1", "tenant2"],
    )

    mock_admin_client.assert_called_with("user1", ["tenant1", "tenant2"])
    assert mock_api.deliver_message.call_count == 3


@patch("collective.bpmproxy.actions.message.camunda_admin_client")
@patch("collective.bpmproxy.actions.message.generic_camunda_client.MessageApi")
@patch("collective.bpmproxy.actions.message.infer_variables")
@patch("collective.bpmproxy.actions.message.logger")
def test_throw_message_exception(
    mock_logger, mock_infer_vars, mock_message_api_cls, mock_admin_client
):
    mock_client = MagicMock()
    mock_admin_client.return_value.__enter__.return_value = mock_client
    mock_api = MagicMock()
    mock_message_api_cls.return_value = mock_api
    mock_api.deliver_message.side_effect = Exception("test error")

    _throwMessage("my_message", None, None, None, "user1", ["tenant1"])

    assert mock_logger.warning.call_count == 2


@patch("collective.bpmproxy.actions.message.camunda_admin_client")
@patch("collective.bpmproxy.actions.message.generic_camunda_client.MessageApi")
@patch("collective.bpmproxy.actions.message.CorrelationMessageDto")
@patch("collective.bpmproxy.actions.message.infer_variables")
def test_throw_message_omits_empty_correlation_fields(
    mock_infer_vars, mock_dto_cls, mock_message_api_cls, mock_admin_client
):
    mock_client = MagicMock()
    mock_admin_client.return_value.__enter__.return_value = mock_client
    mock_message_api_cls.return_value = MagicMock()

    _throwMessage("my_message", "", {}, None, None, [])

    # No tenants: only the without-tenant-id call happens.
    mock_dto_cls.assert_called_once_with(
        message_name="my_message", without_tenant_id="true"
    )


@patch("collective.bpmproxy.actions.message.transaction")
@patch("collective.bpmproxy.actions.message.plone.api.user")
@patch("collective.bpmproxy.actions.message.IStringInterpolator")
@patch("collective.bpmproxy.actions.message.get_tenant_ids")
@patch("collective.bpmproxy.actions.message.SideEffectDataManager")
def test_executor_authenticated(
    mock_data_mgr, mock_get_tenant_ids, mock_interpolator, mock_user, mock_transaction
):
    context = MagicMock()
    element = MagicMock()
    element.name = "my_message"
    element.businessKey = "bk"
    element.correlationKeys = {"uuid": "abc"}
    element.payload = {"k": "v"}
    event = MagicMock()

    mock_interpolator.return_value.side_effect = lambda x: x
    mock_user.is_anonymous.return_value = False
    mock_user.get_current().getUserName.return_value = "user1"
    mock_get_tenant_ids.return_value = ["t1"]

    mock_txn = MagicMock()
    mock_transaction.get.return_value = mock_txn

    executor = BpmMessageActionExecutor(context, element, event)
    res = executor()

    assert res is True
    mock_txn.join.assert_called_once()
    mock_data_mgr.assert_called_once()
    func = mock_data_mgr.call_args[0][0]
    assert func.func.__name__ == "_throwMessage"
    assert func.args == (
        "my_message",
        "bk",
        {"uuid": "abc"},
        {"k": "v"},
        "user1",
        ["t1"],
    )


@patch("collective.bpmproxy.actions.message.transaction")
@patch("collective.bpmproxy.actions.message.plone.api.user")
@patch("collective.bpmproxy.actions.message.IStringInterpolator")
@patch("collective.bpmproxy.actions.message.get_tenant_ids")
@patch("collective.bpmproxy.actions.message.SideEffectDataManager")
def test_executor_anonymous(
    mock_data_mgr, mock_get_tenant_ids, mock_interpolator, mock_user, mock_transaction
):
    context = MagicMock()
    element = MagicMock()
    element.name = "my_message"
    element.businessKey = ""
    element.correlationKeys = {}
    element.payload = {"k": "v"}
    event = MagicMock()

    mock_interpolator.return_value.side_effect = lambda x: x
    mock_user.is_anonymous.return_value = True
    mock_get_tenant_ids.return_value = ["t1"]

    mock_txn = MagicMock()
    mock_transaction.get.return_value = mock_txn

    executor = BpmMessageActionExecutor(context, element, event)
    res = executor()

    assert res is True
    mock_txn.join.assert_called_once()
    mock_data_mgr.assert_called_once()
    func = mock_data_mgr.call_args[0][0]
    assert func.args == ("my_message", "", {}, {"k": "v"}, None, ["t1"])


def test_forms():
    assert BpmMessageAddForm.__name__ == "BpmMessageAddForm"
    assert BpmMessageAddFormView.__name__ == "BpmMessageAddFormView"
    assert BpmMessageEditForm.__name__ == "BpmMessageEditForm"
    assert BpmMessageEditFormView.__name__ == "BpmMessageEditFormView"
