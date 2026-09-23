from collective.bpmproxy.client import camunda_admin_client
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import deploy_process
from collective.bpmproxy.client import get_api_url
from collective.bpmproxy.client import get_authorization
from collective.bpmproxy.client import get_token
from collective.bpmproxy.interfaces import ANONYMOUS_USER_ANNOTATION_KEY
from collective.bpmproxy.interfaces import ANONYMOUS_USER_PREFIX
from collective.bpmproxy.interfaces import CAMUNDA_API_PRIVATE_KEY_ENV
from collective.bpmproxy.interfaces import CAMUNDA_API_URL_ENV
from unittest import mock


def test_get_api_url(monkeypatch):
    monkeypatch.setenv(CAMUNDA_API_URL_ENV, "http://test.url")
    assert get_api_url() == "http://test.url"

    monkeypatch.delenv(CAMUNDA_API_URL_ENV, raising=False)
    assert get_api_url() == "http://localhost:8081/engine-rest"


@mock.patch("collective.bpmproxy.client.get_tenant_ids", return_value=["tenant1"])
@mock.patch("collective.bpmproxy.client.jwt.encode", return_value="fake_jwt")
def test_get_token(mock_jwt, mock_tenants, monkeypatch):
    monkeypatch.setenv(CAMUNDA_API_PRIVATE_KEY_ENV, "/fake/path.pem")

    with mock.patch("builtins.open", mock.mock_open(read_data="fake_key")):
        token = get_token("user1", ["group1"])
        assert token == "fake_jwt"
        mock_jwt.assert_called_once()
        args = mock_jwt.call_args[0]
        assert args[0]["sub"] == "user1"
        assert args[0]["groups"] == ["group1"]
        assert args[0]["tenant_ids"] == ["tenant1"]

    # no private key
    monkeypatch.delenv(CAMUNDA_API_PRIVATE_KEY_ENV, raising=False)
    assert get_token("user", []) is None


@mock.patch("collective.bpmproxy.client.plone.api.user.is_anonymous", return_value=True)
@mock.patch("collective.bpmproxy.client.plone.api.portal.getRequest")
@mock.patch("collective.bpmproxy.client.IAnnotations")
@mock.patch("collective.bpmproxy.client.sign_anonymous_token", return_value="new.sig")
@mock.patch("collective.bpmproxy.client.verify_anonymous_token", return_value=None)
@mock.patch("collective.bpmproxy.client.get_token", return_value="anon_token")
def test_get_authorization_anonymous_mints_a_token(
    mock_get_token,
    mock_verify,
    mock_sign,
    mock_annotations,
    mock_get_request,
    mock_is_anon,
):
    # No token in the annotation or request.form, so a fresh one is minted
    # and signed rather than trusting a bare client-supplied value.
    mock_request = mock.MagicMock()
    mock_request.form = {}
    mock_get_request.return_value = mock_request

    mock_dict = {}
    mock_annotations.return_value = mock_dict

    auth = get_authorization()
    assert auth == "Bearer anon_token"
    mock_sign.assert_called_once()
    assert mock_dict[ANONYMOUS_USER_ANNOTATION_KEY] == "new.sig"
    username = mock_get_token.call_args.kwargs["username"]
    assert username.startswith(ANONYMOUS_USER_PREFIX)


@mock.patch("collective.bpmproxy.client.plone.api.user.is_anonymous", return_value=True)
@mock.patch("collective.bpmproxy.client.plone.api.portal.getRequest")
@mock.patch("collective.bpmproxy.client.IAnnotations")
@mock.patch("collective.bpmproxy.client.sign_anonymous_token")
@mock.patch(
    "collective.bpmproxy.client.verify_anonymous_token", return_value="known-uuid"
)
@mock.patch("collective.bpmproxy.client.get_token", return_value="anon_token")
def test_get_authorization_anonymous_reuses_a_verified_token(
    mock_get_token,
    mock_verify,
    mock_sign,
    mock_annotations,
    mock_get_request,
    mock_is_anon,
):
    # A token that verifies is reused as-is; nothing new is signed.
    mock_request = mock.MagicMock()
    mock_request.form = {"token": "known-uuid.some-sig"}
    mock_get_request.return_value = mock_request

    mock_dict = {}
    mock_annotations.return_value = mock_dict

    auth = get_authorization()
    assert auth == "Bearer anon_token"
    mock_verify.assert_called_once_with("known-uuid.some-sig")
    mock_sign.assert_not_called()
    assert mock_dict[ANONYMOUS_USER_ANNOTATION_KEY] == "known-uuid.some-sig"
    mock_get_token.assert_called_once_with(
        username=ANONYMOUS_USER_PREFIX + "known-uuid", groups=[]
    )


@mock.patch("collective.bpmproxy.client.plone.api.user.is_anonymous", return_value=True)
@mock.patch("collective.bpmproxy.client.plone.api.portal.getRequest")
@mock.patch("collective.bpmproxy.client.IAnnotations")
@mock.patch("collective.bpmproxy.client.sign_anonymous_token", return_value="new.sig")
@mock.patch("collective.bpmproxy.client.verify_anonymous_token", return_value=None)
@mock.patch("collective.bpmproxy.client.get_token", return_value="anon_token")
def test_get_authorization_anonymous_rejects_an_unsigned_token(
    mock_get_token,
    mock_verify,
    mock_sign,
    mock_annotations,
    mock_get_request,
    mock_is_anon,
):
    # A client-supplied value that does not verify (e.g. a bare made-up
    # UUID, or an old client still sending the pre-signing format) is
    # rejected exactly like no token at all: a fresh one is minted.
    mock_request = mock.MagicMock()
    mock_request.form = {"token": "550e8400-e29b-41d4-a716-446655440000"}
    mock_get_request.return_value = mock_request

    mock_dict = {}
    mock_annotations.return_value = mock_dict

    auth = get_authorization()
    assert auth == "Bearer anon_token"
    mock_verify.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")
    mock_sign.assert_called_once()
    assert mock_dict[ANONYMOUS_USER_ANNOTATION_KEY] == "new.sig"


@mock.patch(
    "collective.bpmproxy.client.plone.api.user.is_anonymous", return_value=False
)
@mock.patch("collective.bpmproxy.client.plone.api.user.get_current")
@mock.patch("collective.bpmproxy.client.plone.api.group.get_groups", return_value=[])
@mock.patch("collective.bpmproxy.client.get_token", return_value="user_token")
def test_get_authorization_user(
    mock_get_token, mock_get_groups, mock_get_current, mock_is_anon
):
    mock_user = mock.MagicMock()
    mock_user.getUserName.return_value = "testuser"
    mock_get_current.return_value = mock_user

    auth = get_authorization()
    assert auth == "Bearer user_token"
    mock_get_token.assert_called_once_with(username="testuser", groups=[])


@mock.patch("collective.bpmproxy.client.get_authorization", return_value="Bearer fake")
def test_camunda_client(mock_auth):
    with camunda_client() as client:
        assert client is not None
        assert client.configuration.host == "http://localhost:8081/engine-rest"
        assert client.default_headers["Authorization"] == "Bearer fake"


@mock.patch("collective.bpmproxy.client.get_token", return_value="fake_admin")
def test_camunda_admin_client(mock_token):
    with camunda_admin_client() as client:
        assert client is not None
        assert client.default_headers["Authorization"] == "Bearer fake_admin"


@mock.patch("collective.bpmproxy.client.requests.post")
@mock.patch("collective.bpmproxy.client.get_api_url", return_value="http://fake")
def test_deploy_process(mock_get_api_url, mock_post):
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {"id": "123"}
    mock_post.return_value = mock_response

    mock_client = mock.MagicMock()
    mock_client.default_headers = {"Authorization": "Bearer fake"}

    result = deploy_process(
        mock_client, "test-model", "<bpmn></bpmn>", tenant_id="tenant1"
    )

    assert result == {"id": "123"}
    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == "http://fake/deployment/create"
    assert mock_post.call_args[1]["headers"] == {"Authorization": "Bearer fake"}
    assert "tenant-id" in mock_post.call_args[1]["files"]

    # Test without tenant_id and without auth header
    mock_post.reset_mock()
    mock_client.default_headers = {}
    result = deploy_process(mock_client, "test2", "<bpmn></bpmn>")
    assert "tenant-id" not in mock_post.call_args[1]["files"]
    assert mock_post.call_args[1]["headers"] == {}
