from collective.bpmproxy.actions.signal import _throwSignal
from collective.bpmproxy.actions.signal import BpmSignalAction
from collective.bpmproxy.actions.signal import BpmSignalActionExecutor
from collective.bpmproxy.actions.signal import BpmSignalAddForm
from collective.bpmproxy.actions.signal import BpmSignalAddFormView
from collective.bpmproxy.actions.signal import BpmSignalEditForm
from collective.bpmproxy.actions.signal import BpmSignalEditFormView
from collective.bpmproxy.actions.signal import interpolate
from unittest.mock import MagicMock
from unittest.mock import patch


def test_bpmsignalaction():
    action = BpmSignalAction()
    action.name = "test_signal"
    assert action.summary == "test_signal"


def test_interpolate():
    interpolator = MagicMock(side_effect=lambda x: f"interpolated_{x}")
    assert interpolate("foo", interpolator) == "interpolated_foo"
    assert interpolate(["foo", "bar"], interpolator) == [
        "interpolated_foo",
        "interpolated_bar",
    ]
    assert interpolate({"key": "foo"}, interpolator) == {"key": "interpolated_foo"}
    assert interpolate(123, interpolator) == 123


@patch("collective.bpmproxy.actions.signal.camunda_admin_client")
@patch("collective.bpmproxy.actions.signal.generic_camunda_client.SignalApi")
@patch("collective.bpmproxy.actions.signal.infer_variables")
def test_throw_signal_with_tenants(
    mock_infer_vars, mock_signal_api_cls, mock_admin_client
):
    mock_client = MagicMock()
    mock_admin_client.return_value.__enter__.return_value = mock_client
    mock_api = MagicMock()
    mock_signal_api_cls.return_value = mock_api
    mock_infer_vars.return_value = {"inferred": "vars"}

    _throwSignal("my_signal", {"payload": "data"}, "user1", ["tenant1", "tenant2"])

    mock_admin_client.assert_called_with("user1", ["tenant1", "tenant2"])
    assert mock_api.throw_signal.call_count == 3


@patch("collective.bpmproxy.actions.signal.camunda_admin_client")
@patch("collective.bpmproxy.actions.signal.generic_camunda_client.SignalApi")
@patch("collective.bpmproxy.actions.signal.infer_variables")
@patch("collective.bpmproxy.actions.signal.logger")
def test_throw_signal_exception(
    mock_logger, mock_infer_vars, mock_signal_api_cls, mock_admin_client
):
    mock_client = MagicMock()
    mock_admin_client.return_value.__enter__.return_value = mock_client
    mock_api = MagicMock()
    mock_signal_api_cls.return_value = mock_api
    mock_api.throw_signal.side_effect = Exception("test error")

    _throwSignal("my_signal", {}, "user1", ["tenant1"])

    assert mock_logger.warning.call_count == 2


@patch("collective.bpmproxy.actions.signal.plone.api.user")
@patch("collective.bpmproxy.actions.signal.IStringInterpolator")
@patch("collective.bpmproxy.actions.signal.get_tenant_ids")
@patch("collective.bpmproxy.actions.signal.join_side_effect")
def test_executor_authenticated(
    mock_join_side_effect, mock_get_tenant_ids, mock_interpolator, mock_user
):
    context = MagicMock()
    element = MagicMock()
    element.name = "my_signal"
    element.payload = {"k": "v"}
    event = MagicMock()

    mock_interpolator.return_value.side_effect = lambda x: x
    mock_user.is_anonymous.return_value = False
    mock_user.get_current().getUserName.return_value = "user1"
    mock_get_tenant_ids.return_value = ["t1"]

    executor = BpmSignalActionExecutor(context, element, event)
    res = executor()

    assert res is True
    mock_join_side_effect.assert_called_once_with(
        _throwSignal, args=("my_signal", {"k": "v"}, "user1", ["t1"])
    )


@patch("collective.bpmproxy.actions.signal.plone.api.user")
@patch("collective.bpmproxy.actions.signal.IStringInterpolator")
@patch("collective.bpmproxy.actions.signal.get_tenant_ids")
@patch("collective.bpmproxy.actions.signal.join_side_effect")
def test_executor_anonymous(
    mock_join_side_effect, mock_get_tenant_ids, mock_interpolator, mock_user
):
    context = MagicMock()
    element = MagicMock()
    element.name = "my_signal"
    element.payload = {"k": "v"}
    event = MagicMock()

    mock_interpolator.return_value.side_effect = lambda x: x
    mock_user.is_anonymous.return_value = True
    mock_get_tenant_ids.return_value = ["t1"]

    executor = BpmSignalActionExecutor(context, element, event)
    res = executor()

    assert res is True
    mock_join_side_effect.assert_called_once_with(
        _throwSignal, args=("my_signal", {"k": "v"}, None, ["t1"])
    )


def test_forms():
    assert BpmSignalAddForm.__name__ == "BpmSignalAddForm"
    assert BpmSignalAddFormView.__name__ == "BpmSignalAddFormView"
    assert BpmSignalEditForm.__name__ == "BpmSignalEditForm"
    assert BpmSignalEditFormView.__name__ == "BpmSignalEditFormView"
