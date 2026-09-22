from collective.bpmproxy.client import business_key_needle
from collective.bpmproxy.client import camunda_admin_client
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import check_engine_reachable
from collective.bpmproxy.client import complete_task
from collective.bpmproxy.client import get_api_url
from collective.bpmproxy.client import get_authorization
from collective.bpmproxy.client import get_available_tasks
from collective.bpmproxy.client import get_diagram_xml
from collective.bpmproxy.client import get_next_tasks
from collective.bpmproxy.client import get_start_form
from collective.bpmproxy.client import get_task_form
from collective.bpmproxy.client import get_task_variables
from collective.bpmproxy.client import get_token
from collective.bpmproxy.client import is_optimistic_locking_conflict
from collective.bpmproxy.client import join_side_effect
from collective.bpmproxy.client import submit_start_form
from collective.bpmproxy.client import submit_task_form
from collective.bpmproxy.interfaces import ANONYMOUS_USER_ANNOTATION_KEY
from collective.bpmproxy.interfaces import ANONYMOUS_USER_PREFIX
from collective.bpmproxy.interfaces import CAMUNDA_ADMIN_GROUP
from collective.bpmproxy.interfaces import CAMUNDA_API_PRIVATE_KEY_ENV
from collective.bpmproxy.interfaces import CAMUNDA_API_URL_DEFAULT
from collective.bpmproxy.interfaces import CAMUNDA_API_URL_ENV
from generic_camunda_client import ApiException
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch
import generic_camunda_client
import os
import pytest
import transaction


@patch.dict(os.environ, {}, clear=True)
def test_get_api_url_default():
    assert get_api_url() == CAMUNDA_API_URL_DEFAULT


@patch.dict(os.environ, {CAMUNDA_API_URL_ENV: "http://test-camunda"}, clear=True)
def test_get_api_url_env():
    assert get_api_url() == "http://test-camunda"


@patch("collective.bpmproxy.client.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="fake_key")
@patch("collective.bpmproxy.client.jwt.encode")
@patch.dict(os.environ, {CAMUNDA_API_PRIVATE_KEY_ENV: "/path/to/key"})
def test_get_token_success(mock_jwt_encode, mock_open_file, mock_exists):
    mock_jwt_encode.return_value = "token_string"
    token = get_token("user1", ["group1"], ["t1"])
    assert token == "token_string"
    mock_jwt_encode.assert_called_once()


@patch.dict(os.environ, {}, clear=True)
def test_get_token_no_key():
    token = get_token("user1", ["group1"], ["t1"])
    assert token is None


@patch("collective.bpmproxy.client.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="fake_key")
@patch("collective.bpmproxy.client.jwt.encode")
@patch("collective.bpmproxy.client.get_tenant_ids")
@patch.dict(os.environ, {CAMUNDA_API_PRIVATE_KEY_ENV: "/path/to/key"})
def test_get_token_no_tenant_ids(
    mock_get_tenant_ids, mock_jwt_encode, mock_open_file, mock_exists
):
    mock_get_tenant_ids.return_value = ["t1"]
    mock_jwt_encode.return_value = "token_string"
    token = get_token("user1", ["group1"])
    assert token == "token_string"
    mock_jwt_encode.assert_called_once()
    assert mock_jwt_encode.call_args[0][0]["tenant_ids"] == ["t1"]


@patch("collective.bpmproxy.client.plone.api.user")
@patch("collective.bpmproxy.client.plone.api.portal")
@patch("collective.bpmproxy.client.IAnnotations")
@patch("collective.bpmproxy.client.sign_anonymous_token")
@patch("collective.bpmproxy.client.verify_anonymous_token", return_value=None)
@patch("collective.bpmproxy.client.get_token")
def test_get_authorization_anonymous_new_token(
    mock_get_token,
    mock_verify,
    mock_sign,
    mock_IAnnotations,
    mock_portal,
    mock_user,
):
    mock_user.is_anonymous.return_value = True
    request = MagicMock()
    request.form = {}
    mock_portal.getRequest.return_value = request
    annotations = {}
    mock_IAnnotations.return_value.get.side_effect = annotations.get
    mock_IAnnotations.return_value.__setitem__.side_effect = annotations.__setitem__

    mock_get_token.return_value = "anon_token"
    mock_sign.side_effect = lambda token: token + ".signed"

    auth = get_authorization()

    assert auth == "Bearer anon_token"
    assert ANONYMOUS_USER_ANNOTATION_KEY in annotations
    signed_val = annotations[ANONYMOUS_USER_ANNOTATION_KEY]
    assert signed_val.endswith(".signed")
    token_val = signed_val[: -len(".signed")]
    mock_get_token.assert_called_with(
        username=ANONYMOUS_USER_PREFIX + token_val, groups=[]
    )


@patch("collective.bpmproxy.client.plone.api.user")
@patch("collective.bpmproxy.client.plone.api.portal")
@patch("collective.bpmproxy.client.IAnnotations")
@patch("collective.bpmproxy.client.sign_anonymous_token")
@patch("collective.bpmproxy.client.verify_anonymous_token")
@patch("collective.bpmproxy.client.get_token")
def test_get_authorization_anonymous_existing_token(
    mock_get_token,
    mock_verify,
    mock_sign,
    mock_IAnnotations,
    mock_portal,
    mock_user,
):
    mock_user.is_anonymous.return_value = True
    request = MagicMock()
    request.form = {}
    mock_portal.getRequest.return_value = request
    mock_IAnnotations.return_value.get.return_value = (
        "12345678-1234-5678-1234-567812345678.some-signature"
    )
    mock_verify.return_value = "12345678-1234-5678-1234-567812345678"

    mock_get_token.return_value = "anon_token"

    auth = get_authorization()

    assert auth == "Bearer anon_token"
    mock_sign.assert_not_called()
    mock_get_token.assert_called_with(
        username=ANONYMOUS_USER_PREFIX + "12345678-1234-5678-1234-567812345678",
        groups=[],
    )


@patch("collective.bpmproxy.client.plone.api.user")
@patch("collective.bpmproxy.client.plone.api.group")
@patch("collective.bpmproxy.client.get_token")
def test_get_authorization_authenticated(mock_get_token, mock_group, mock_user):
    mock_user.is_anonymous.return_value = False
    user_obj = MagicMock()
    user_obj.getUserName.return_value = "test_user"
    mock_user.get_current.return_value = user_obj
    group_obj = MagicMock()
    group_obj.getId.return_value = "group1"
    mock_group.get_groups.return_value = [group_obj]

    mock_get_token.return_value = "user_token"

    auth = get_authorization()

    assert auth == "Bearer user_token"
    mock_get_token.assert_called_with(username="test_user", groups=["group1"])


@patch("collective.bpmproxy.client.plone.api.user")
@patch("collective.bpmproxy.client.plone.api.group")
@patch("collective.bpmproxy.client.get_token")
def test_get_authorization_authenticated_no_token(
    mock_get_token, mock_group, mock_user
):
    mock_user.is_anonymous.return_value = False
    mock_user.get_current.return_value = None
    mock_group.get_groups.return_value = []

    mock_get_token.return_value = None

    auth = get_authorization()

    assert auth is None


@patch("collective.bpmproxy.client.get_api_url")
@patch("collective.bpmproxy.client.get_authorization")
def test_camunda_client(mock_get_auth, mock_get_api_url):
    mock_get_api_url.return_value = "http://api"
    mock_get_auth.return_value = "Bearer x"

    with camunda_client() as client:
        assert isinstance(client, generic_camunda_client.ApiClient)
        assert client.configuration.host == "http://api"
        assert client.default_headers["Authorization"] == "Bearer x"


@patch("collective.bpmproxy.client.get_api_url")
@patch("collective.bpmproxy.client.get_token")
def test_camunda_admin_client(mock_get_token, mock_get_api_url):
    mock_get_api_url.return_value = "http://api"
    mock_get_token.return_value = "admin_token"

    with camunda_admin_client(username="my_admin", tenant_ids=["t1"]) as client:
        assert isinstance(client, generic_camunda_client.ApiClient)
        assert client.configuration.host == "http://api"
        assert client.default_headers["Authorization"] == "Bearer admin_token"
        mock_get_token.assert_called_with(
            username="my_admin", groups=[CAMUNDA_ADMIN_GROUP], tenant_ids=["t1"]
        )


@patch("collective.bpmproxy.client.generic_camunda_client.ProcessDefinitionApi")
@patch("collective.bpmproxy.client.prepare_camunda_form")
@patch("builtins.open", new_callable=mock_open, read_data="form_data")
def test_get_start_form(mock_file, mock_prepare, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.get_deployed_start_form_by_key.return_value = "form_path"
    mock_prepare.return_value = "prepared_form"

    res = get_start_form("client", "def_key", {}, {}, "ctx")

    assert res == "prepared_form"
    mock_api.get_deployed_start_form_by_key.assert_called_with("def_key")
    mock_prepare.assert_called_with("form_data", {}, {}, "ctx")


@patch("collective.bpmproxy.client.generic_camunda_client.ProcessDefinitionApi")
@patch("collective.bpmproxy.client.prepare_camunda_form")
@patch("builtins.open", new_callable=mock_open, read_data="form_data")
def test_get_start_form_tenant(mock_file, mock_prepare, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.get_deployed_start_form_by_key_and_tenant_id.return_value = "form_path"
    mock_prepare.return_value = "prepared_form"

    res = get_start_form("client", "def_key:t1", {}, {}, "ctx")

    assert res == "prepared_form"
    mock_api.get_deployed_start_form_by_key_and_tenant_id.assert_called_with(
        "def_key", "t1"
    )


@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
@patch("collective.bpmproxy.client.prepare_camunda_form")
@patch("builtins.open", new_callable=mock_open, read_data="form_data")
def test_get_task_form(mock_file, mock_prepare, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.get_deployed_form.return_value = "form_path"
    mock_prepare.return_value = "prepared_form"

    res = get_task_form("client", "task_1", {}, {}, "ctx")

    assert res == "prepared_form"
    mock_api.get_deployed_form.assert_called_with("task_1")
    mock_prepare.assert_called_with("form_data", {}, {}, "ctx")


@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
def test_get_available_tasks_no_keys(mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.query_tasks.return_value = ["task1"]

    res = get_available_tasks("client")

    assert res == ["task1"]
    mock_api.query_tasks.assert_called_once()
    kwargs = mock_api.query_tasks.call_args[1]
    assert "max_results" in kwargs


@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
def test_get_available_tasks_with_keys(mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.query_tasks.return_value = ["task1"]

    res = get_available_tasks("client", context_key="ctx1", attachments_key="att1")

    assert res == ["task1"]
    mock_api.query_tasks.assert_called_once()
    dto = mock_api.query_tasks.call_args[1]["task_query_dto"]
    # Business keys are "{context}:{attachments}", so the colon belongs in the
    # pattern -- without it this matched the concatenation and never a real
    # key, which made attachments unreachable.
    assert dto.process_instance_business_key_like == "ctx1:att1"


@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
def test_get_available_tasks_filters_by_process_definition_key(mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.query_tasks.return_value = ["task1"]

    get_available_tasks("client", process_definition_key="my-key")

    dto = mock_api.query_tasks.call_args[1]["task_query_dto"]
    assert dto.process_definition_key == "my-key"


@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
def test_get_available_tasks_strips_the_tenant_suffix(mock_api_cls):
    """Vocabulary tokens are "{key}:{tenant}" when a tenant is set -- the
    engine's processDefinitionKey filter takes a bare key; tenant scoping
    already happens through the JWT's tenant_ids claim."""
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.query_tasks.return_value = ["task1"]

    get_available_tasks(
        "client", context_key="ctx1", process_definition_key="my-key:tenant1"
    )

    dto = mock_api.query_tasks.call_args[1]["task_query_dto"]
    assert dto.process_definition_key == "my-key"


def test_business_key_needle_matches_the_stored_format():
    """The needle has to match what the form views actually write."""
    # Both halves known: an exact key, colon included.
    assert business_key_needle("ctx1", "att1") == "ctx1:att1"

    # The attachments half arrives as a container id, which is the dashed
    # str(UUID(...)) form of the hex written into the business key.
    assert (
        business_key_needle(
            "9d2c0f1e4b3a4c5d8e7f6a5b4c3d2e1f",
            "12345678-1234-5678-1234-567812345678",
        )
        == "9d2c0f1e4b3a4c5d8e7f6a5b4c3d2e1f:12345678123456781234567812345678"
    )

    # A missing half still matches anything in that position.
    assert business_key_needle("ctx1", None) == "ctx1:%"
    assert business_key_needle(None, "att1") == "%:att1"


@patch("collective.bpmproxy.client.plone.api.portal")
@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
def test_get_available_tasks_for_display(mock_api_cls, mock_portal):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api

    task1 = MagicMock(assignee=ANONYMOUS_USER_PREFIX + "123")
    task2 = MagicMock(assignee="user2")
    task3 = MagicMock(assignee=None)
    mock_api.query_tasks.return_value = [task1, task2, task3]

    mock_member = MagicMock()
    mock_member.getProperty.return_value = "User Two"
    mock_portal.get_tool().getMemberById.return_value = mock_member

    get_available_tasks("client", for_display=True)

    assert task1.assignee == "Anonymous User"
    assert task2.assignee == "User Two"
    assert task3.assignee is None
    # if get_member returns None
    mock_portal.get_tool().getMemberById.return_value = None
    task4 = MagicMock(assignee="user3")
    mock_api.query_tasks.return_value = [task4]
    get_available_tasks("client", for_display=True)
    assert task4.assignee == "user3"


@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
def test_get_next_tasks(mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.query_tasks.return_value = ["task1"]

    res = get_next_tasks("client", "proc1")

    assert res == ["task1"]
    mock_api.query_tasks.assert_called_once()


@patch("collective.bpmproxy.client.generic_camunda_client.ProcessDefinitionApi")
@patch("collective.bpmproxy.client.infer_variables")
@patch("collective.bpmproxy.client.IStringInterpolator")
def test_submit_start_form(mock_interpolator, mock_infer, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_infer.return_value = "inferred"
    mock_interpolator.return_value.side_effect = lambda x: x + "_interp"
    mock_api.start_process_instance_by_key.return_value = "instance1"

    res = submit_start_form(
        "client", "def_key", "bus_key", {"k": "v"}, {"k2": "v2"}, "ctx"
    )

    assert res == "instance1"
    mock_api.start_process_instance_by_key.assert_called_once()
    mock_infer.assert_called_with({"k": "v", "k2": "v2_interp"})


@patch("collective.bpmproxy.client.generic_camunda_client.ProcessDefinitionApi")
@patch("collective.bpmproxy.client.infer_variables")
def test_submit_start_form_tenant(mock_infer, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_infer.return_value = "inferred"
    mock_api.start_process_instance_by_key_and_tenant_id.return_value = "instance1"

    res = submit_start_form("client", "def_key:t1", "bus_key", {"k": "v"})

    assert res == "instance1"
    mock_api.start_process_instance_by_key_and_tenant_id.assert_called_with(
        "def_key",
        "t1",
        start_process_instance_dto=generic_camunda_client.StartProcessInstanceDto(
            business_key="bus_key", variables="inferred"
        ),
    )


@patch("collective.bpmproxy.client.generic_camunda_client.ProcessDefinitionApi")
@patch("collective.bpmproxy.client.infer_variables")
@patch("collective.bpmproxy.client.logger")
def test_submit_start_form_exception(mock_logger, mock_infer, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.start_process_instance_by_key.side_effect = ApiException("error")

    with pytest.raises(ApiException):
        submit_start_form("client", "def_key", "bus_key", {})

    mock_logger.error.assert_called_once()


@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
@patch("collective.bpmproxy.client.infer_variables")
def test_submit_task_form(mock_infer, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.complete.return_value = "res"
    mock_infer.return_value = "inferred"

    res = submit_task_form("client", "task_1", {"k": "v"})

    assert res == "res"
    mock_api.complete.assert_called_once()


@patch("collective.bpmproxy.client.generic_camunda_client.TaskApi")
@patch("collective.bpmproxy.client.logger")
def test_submit_task_form_exception(mock_logger, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.complete.side_effect = ApiException("error")

    with pytest.raises(ApiException):
        submit_task_form("client", "task_1", {})

    mock_logger.error.assert_called_once()


@patch("collective.bpmproxy.client.generic_camunda_client.TaskVariableApi")
@patch("collective.bpmproxy.client.flatten_variables")
def test_get_task_variables(mock_flatten, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api

    var1 = MagicMock(type="String", value="foo")
    var2 = MagicMock(type="Json", value="null")
    mock_api.get_task_variables.side_effect = [
        {"v1": var1, "v2": var2},
        {"v1": var1, "v2": MagicMock(type="Json", value='{"a": 1}')},
    ]
    mock_flatten.return_value = "flattened"

    res = get_task_variables("client", "task_1")

    assert res == "flattened"
    assert mock_api.get_task_variables.call_count == 2
    mock_flatten.assert_called_once()


@patch("collective.bpmproxy.client.generic_camunda_client.TaskVariableApi")
@patch("collective.bpmproxy.client.flatten_variables")
def test_get_task_variables_no_json(mock_flatten, mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api

    var1 = MagicMock(type="String", value="foo")
    mock_api.get_task_variables.return_value = {"v1": var1}
    mock_flatten.return_value = "flattened"

    res = get_task_variables("client", "task_1")

    assert res == "flattened"
    assert mock_api.get_task_variables.call_count == 1
    mock_flatten.assert_called_once()


@patch("collective.bpmproxy.client.generic_camunda_client.ProcessDefinitionApi")
def test_get_diagram_xml(mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.get_process_definition_bpmn20_xml.return_value = MagicMock(
        bpmn20_xml="<xml/>"
    )

    res = get_diagram_xml("client", definition_id="id1")
    assert res == "<xml/>"
    mock_api.get_process_definition_bpmn20_xml.assert_called_with("id1")


@patch("collective.bpmproxy.client.generic_camunda_client.ProcessDefinitionApi")
def test_get_diagram_xml_by_key(mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.get_process_definition_bpmn20_xml_by_key.return_value = MagicMock(
        bpmn20_xml="<xml/>"
    )

    res = get_diagram_xml("client", definition_key="key1")
    assert res == "<xml/>"
    mock_api.get_process_definition_bpmn20_xml_by_key.assert_called_with("key1")


@patch("collective.bpmproxy.client.generic_camunda_client.ProcessDefinitionApi")
def test_get_diagram_xml_by_key_and_tenant(mock_api_cls):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.get_process_definition_bpmn20_xml_by_key_and_tenant_id.return_value = (
        MagicMock(bpmn20_xml="<xml/>")
    )

    res = get_diagram_xml("client", definition_key="key1:t1")
    assert res == "<xml/>"
    mock_api.get_process_definition_bpmn20_xml_by_key_and_tenant_id.assert_called_with(
        "key1", "t1"
    )

    res2 = get_diagram_xml("client", definition_key="key2", tenant_id="t2")
    assert res2 == "<xml/>"
    mock_api.get_process_definition_bpmn20_xml_by_key_and_tenant_id.assert_called_with(
        "key2", "t2"
    )


@pytest.fixture(autouse=True)
def _isolated_transaction():
    """``check_engine_reachable``'s result is memoized per transaction (see
    client.py), so tests calling it directly -- rather than through a
    ``SideEffectDataManager``'s vote -- each need their own transaction, the
    same way a real request would only ever ask it once."""
    transaction.abort()
    yield
    transaction.abort()


@patch("collective.bpmproxy.client.requests.get")
@patch("collective.bpmproxy.client.get_api_url", return_value="http://fake")
def test_check_engine_reachable_ok(mock_get_api_url, mock_get):
    mock_get.return_value = MagicMock(status_code=200)
    check_engine_reachable()  # does not raise
    mock_get.assert_called_once_with("http://fake/engine", timeout=3)

    # accepts and ignores the same *args a real callable's would carry, and
    # (still within the same transaction) reuses the cached result instead
    # of asking the engine again.
    check_engine_reachable("signal", {"k": "v"}, "user1", ["t1"])
    mock_get.assert_called_once()


@patch("collective.bpmproxy.client.requests.get")
@patch("collective.bpmproxy.client.get_api_url", return_value="http://fake")
def test_check_engine_reachable_memoizes_per_transaction(mock_get_api_url, mock_get):
    mock_get.return_value = MagicMock(status_code=200)

    check_engine_reachable()
    check_engine_reachable()
    mock_get.assert_called_once()

    # A new transaction (a new request/vote cycle) probes again.
    transaction.abort()
    check_engine_reachable()
    assert mock_get.call_count == 2


@patch("collective.bpmproxy.client.requests.get")
@patch("collective.bpmproxy.client.get_api_url", return_value="http://fake")
def test_check_engine_reachable_caches_the_failure_too(mock_get_api_url, mock_get):
    import requests

    mock_get.side_effect = requests.exceptions.ConnectionError("refused")

    with pytest.raises(RuntimeError, match="not reachable"):
        check_engine_reachable()
    # A second vote in the same transaction re-raises the cached failure
    # rather than probing the (still unreachable) engine again.
    with pytest.raises(RuntimeError, match="not reachable"):
        check_engine_reachable()
    mock_get.assert_called_once()


@patch("collective.bpmproxy.client.requests.get")
@patch("collective.bpmproxy.client.get_api_url", return_value="http://fake")
def test_check_engine_reachable_connection_error(mock_get_api_url, mock_get):
    import requests

    mock_get.side_effect = requests.exceptions.ConnectionError("refused")

    with pytest.raises(RuntimeError, match="not reachable"):
        check_engine_reachable()


@patch("collective.bpmproxy.client.requests.get")
@patch("collective.bpmproxy.client.get_api_url", return_value="http://fake")
def test_check_engine_reachable_server_error(mock_get_api_url, mock_get):
    mock_get.return_value = MagicMock(status_code=503)

    with pytest.raises(RuntimeError, match="503"):
        check_engine_reachable()


def test_is_optimistic_locking_conflict():
    conflict = ApiException(
        http_resp=MagicMock(
            status=500,
            data=(
                b'{"type":"RestException","message":"Cannot complete task t1: '
                b"ENGINE-03005 Execution of 'INSERT ...' failed. Entity was "
                b'updated by another transaction concurrently.","code":1}'
            ),
            getheaders=lambda: {},
        )
    )
    assert is_optimistic_locking_conflict(conflict) is True

    not_found = ApiException(status=404, reason="Not Found")
    assert is_optimistic_locking_conflict(not_found) is False

    validation = ApiException(
        http_resp=MagicMock(
            status=400,
            data=b'{"message": "unexpected null value"}',
            getheaders=lambda: {},
        )
    )
    assert is_optimistic_locking_conflict(validation) is False


@patch("collective.bpmproxy.client.time.sleep")
def test_complete_task_retries_optimistic_locking_conflict(mock_sleep):
    conflict_body = (
        b'{"message": "... was updated by another transaction concurrently."}'
    )
    conflict = ApiException(
        http_resp=MagicMock(status=500, data=conflict_body, getheaders=lambda: {})
    )

    api = MagicMock()
    api.complete.side_effect = [conflict, conflict, "ok"]

    result = complete_task(api, "task_1", "dto", retries=3)

    assert result == "ok"
    assert api.complete.call_count == 3
    # A short, randomized backoff separates the retries (see complete_task's
    # docstring) so two colliding callers do not retry in lockstep.
    assert mock_sleep.call_count == 2


@patch("collective.bpmproxy.client.time.sleep")
def test_complete_task_gives_up_after_retries_exhausted(mock_sleep):
    conflict_body = (
        b'{"message": "... was updated by another transaction concurrently."}'
    )
    conflict = ApiException(
        http_resp=MagicMock(status=500, data=conflict_body, getheaders=lambda: {})
    )

    api = MagicMock()
    api.complete.side_effect = [conflict, conflict, conflict]

    with pytest.raises(ApiException):
        complete_task(api, "task_1", "dto", retries=2)

    assert api.complete.call_count == 3


def test_complete_task_does_not_retry_unrelated_errors():
    api = MagicMock()
    api.complete.side_effect = ApiException(status=404, reason="Not Found")

    with pytest.raises(ApiException):
        complete_task(api, "task_1", "dto", retries=3)

    api.complete.assert_called_once()


@patch("collective.bpmproxy.client.transaction")
@patch("collective.bpmproxy.client.SideEffectDataManager")
def test_join_side_effect_defaults_to_check_engine_reachable(
    mock_data_mgr, mock_transaction
):
    mock_txn = MagicMock()
    mock_transaction.get.return_value = mock_txn

    def my_callable(a, b):
        pass

    join_side_effect(my_callable, args=(1, 2))

    mock_data_mgr.assert_called_once_with(
        my_callable, args=(1, 2), vote=check_engine_reachable, onAbort=None
    )
    mock_txn.join.assert_called_once_with(mock_data_mgr.return_value)


@patch("collective.bpmproxy.client.transaction")
@patch("collective.bpmproxy.client.SideEffectDataManager")
def test_join_side_effect_can_override_vote_and_onabort(
    mock_data_mgr, mock_transaction
):
    def my_callable():
        pass

    def my_vote():
        pass

    def my_abort():
        pass

    join_side_effect(my_callable, vote=my_vote, onAbort=my_abort)

    mock_data_mgr.assert_called_once_with(
        my_callable, args=(), vote=my_vote, onAbort=my_abort
    )
