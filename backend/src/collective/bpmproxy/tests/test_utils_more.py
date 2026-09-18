from collective.bpmproxy.utils import datetime_to_c7
from collective.bpmproxy.utils import flatten_variables
from collective.bpmproxy.utils import get_tenant_ids
from collective.bpmproxy.utils import infer_variable
from collective.bpmproxy.utils import infer_variables
from collective.bpmproxy.utils import interpolate
from collective.bpmproxy.utils import is_valid_uuid
from collective.bpmproxy.utils import parents
from collective.bpmproxy.utils import prepare_camunda_form
from collective.bpmproxy.utils import SideEffectDataManager
from collective.bpmproxy.utils import sign_anonymous_token
from collective.bpmproxy.utils import validate_camunda_form
from collective.bpmproxy.utils import verify_anonymous_token
from unittest import mock
from zope.interface import implementer
from zope.interface import Interface
from zope.interface.interfaces import ComponentLookupError
import datetime
import json
import pytest


def test_get_tenant_ids():
    with mock.patch("plone.api.portal.get_registry_record") as get_registry_record:
        get_registry_record.return_value = ["tenant1", "", "tenant2"]
        assert get_tenant_ids() == ["tenant1", "tenant2"]
        get_registry_record.return_value = None
        assert get_tenant_ids() == []


def test_datetime_to_c7():
    dt1 = datetime.datetime(2023, 1, 1, 11, 30, 0)
    assert datetime_to_c7(dt1) == "2023-01-01T11:30:00.0+0000"

    dt2 = datetime.datetime(2023, 1, 1, 11, 30, 0, tzinfo=datetime.timezone.utc)
    assert datetime_to_c7(dt2) == "2023-01-01T11:30:00.0+0000"


def test_infer_variable():
    assert infer_variable(["a"]) == {"value": '["a"]', "type": "Json"}
    assert infer_variable(True) == {"value": True, "type": "Boolean"}
    assert infer_variable(123) == {"value": 123, "type": "Integer"}
    assert infer_variable("2023-01-01") == {
        "value": "2023-01-01T00:00:00.0+0000",
        "type": "Date",
    }
    # time only, combined with today's date
    assert infer_variable("11:30:00")["type"] == "Date"
    assert infer_variable("not-a-date") == {"value": "not-a-date", "type": "String"}
    assert infer_variable("T") == {"value": "T", "type": "String"}


def test_infer_variables():
    assert infer_variables("not-a-dict") == []
    data = {"a": 1, "b": "test"}
    assert infer_variables(data) == {
        "a": {"value": 1, "type": "Integer"},
        "b": {"value": "test", "type": "String"},
    }


def test_flatten_variables():
    from collections import namedtuple

    Variable = namedtuple("Variable", ["value", "type"])

    variables = {
        "v1": Variable(value="2023-01-01T00:00:00Z", type="Date"),
        "v2": Variable(value="0001-01-01T11:30:00Z", type="Date"),
        "v3": Variable(value="2023-01-01T11:30:00Z", type="Date"),
        "v4": Variable(value="invalid-date", type="Date"),
        "v5": Variable(value="string-val", type="String"),
        "v6": Variable(value=None, type="String"),
    }

    flat = flatten_variables(variables)
    assert flat["v1"] == "2023-01-01"
    assert flat["v2"] == "11:30:00+00:00"
    assert flat["v3"] == "2023-01-01T11:30:00Z"
    assert flat["v4"] is None
    assert flat["v5"] == "string-val"
    assert "v6" not in flat


def test_interpolate():
    def interpolator(val):
        return val.replace("x", "y")

    assert interpolate("x ", interpolator) == "y"
    assert interpolate(["x ", "a "], interpolator) == ["y", "a"]
    assert interpolate({"k": "x "}, interpolator) == {"k": "y"}
    assert interpolate(123, interpolator) == 123
    assert interpolate("x", None) == "x"


def test_prepare_camunda_form():
    schema = {
        "components": [
            {"key": "f1", "defaultValue": "x", "disabled": True},
            {"key": "f2", "defaultValue": "y"},
            {"key": "f3", "valuesKey": "opts"},
            {"key": "f4", "properties": {"vocabulary": "my.vocab"}, "type": "select"},
            {"key": "f5", "type": "text", "text": "Hello $name"},
            {"key": "f6"},
        ]
    }
    default_data = {
        "f2": "val2",
        "opts": ["opt1"],
        "name": "World",
        "f6": ["non-string"],
    }
    default_values = {"f3": "val3"}
    context = mock.Mock()

    with (
        mock.patch("collective.bpmproxy.utils.IStringInterpolator") as InterpolatorMock,
        mock.patch("collective.bpmproxy.utils.getUtility") as getUtilityMock,
    ):
        InterpolatorMock.return_value = lambda val: val.replace("x", "x_interpolated")

        vocab_mock = mock.Mock()
        term_mock = mock.Mock()
        term_mock.title = "Title"
        term_mock.token = "token"
        vocab_mock.return_value = [term_mock]

        getUtilityMock.return_value = vocab_mock

        d_json, o_json, s_json = prepare_camunda_form(
            json.dumps(schema), default_data, default_values, context
        )
        d = json.loads(d_json)
        o = json.loads(o_json)
        s = json.loads(s_json)

        assert d["f1"] == "x_interpolated"
        assert d["f2"] == "val2"
        assert d["f3"] == "val3"
        assert d["f6"] == ["non-string"]

        assert o["opts"] == ["opt1"]
        assert o["my.vocab.values"] == [{"label": "Title", "value": "token"}]

        assert s["components"][4]["text"] == "Hello World"

    # test component lookup error
    with (
        mock.patch("collective.bpmproxy.utils.IStringInterpolator") as InterpolatorMock,
        mock.patch(
            "collective.bpmproxy.utils.getUtility", side_effect=ComponentLookupError
        ),
    ):
        InterpolatorMock.return_value = lambda val: val
        d_json, o_json, s_json = prepare_camunda_form(
            json.dumps(schema), default_data, default_values, context
        )
        o = json.loads(o_json)
        assert "my.vocab.values" not in o


def test_validate_camunda_form():
    schema = {
        "components": [
            {"key": "disabled_f", "disabled": True, "validate": {"required": True}},
            {"key": "f_pattern", "validate": {"pattern": "^[a-z]+$"}},
            {"key": "f_required", "validate": {"required": True}},
            {"key": "f_min", "validate": {"min": 5}},
            {"key": "f_max", "validate": {"max": -1}},
            {"key": "f_min_len", "validate": {"minLength": 3}},
            {"key": "f_max_len", "validate": {"maxLength": 5}},
        ]
    }

    data = {
        "disabled_f": "",
        "f_pattern": "abc",
        "f_required": "yes",
        "f_min": 6,
        "f_max": -2,
        "f_min_len": "abcd",
        "f_max_len": "abcd",
    }

    validate_camunda_form(json.dumps(data), json.dumps(schema), None)

    with pytest.raises(AssertionError, match="must match pattern"):
        bad_data = data.copy()
        bad_data["f_pattern"] = "123"
        validate_camunda_form(json.dumps(bad_data), json.dumps(schema), None)

    with pytest.raises(AssertionError, match="is required"):
        bad_data = data.copy()
        bad_data["f_required"] = ""
        validate_camunda_form(json.dumps(bad_data), json.dumps(schema), None)

    with pytest.raises(AssertionError, match="must have minimum value of 5"):
        bad_data = data.copy()
        bad_data["f_min"] = 0
        validate_camunda_form(json.dumps(bad_data), json.dumps(schema), None)

    # A truthy value below the minimum used to pass: the old condition parsed
    # as ``data.get(key) or (0 >= min_value)``, so any non-falsy value
    # short-circuited the check entirely.
    with pytest.raises(AssertionError, match="must have minimum value of 5"):
        bad_data = data.copy()
        bad_data["f_min"] = 1
        validate_camunda_form(json.dumps(bad_data), json.dumps(schema), None)

    with pytest.raises(AssertionError, match="must have maximum value of -1"):
        bad_data = data.copy()
        bad_data["f_max"] = 0
        validate_camunda_form(json.dumps(bad_data), json.dumps(schema), None)

    with pytest.raises(AssertionError, match="must have minimum length of 3"):
        bad_data = data.copy()
        bad_data["f_min_len"] = "ab"
        validate_camunda_form(json.dumps(bad_data), json.dumps(schema), None)

    with pytest.raises(AssertionError, match="must have maximum length of 5"):
        bad_data = data.copy()
        bad_data["f_max_len"] = "abcdef"
        validate_camunda_form(json.dumps(bad_data), json.dumps(schema), None)

    # Bounds must not fire on an empty optional value -- that is the
    # "required" check's job.
    ok_data = data.copy()
    ok_data["f_min"] = ""
    ok_data["f_max"] = ""
    validate_camunda_form(json.dumps(ok_data), json.dumps(schema), None)


def test_validate_camunda_form_vocabulary():
    schema = {
        "components": [{"key": "f_vocab", "properties": {"vocabulary": "my.vocab"}}]
    }

    data = {"f_vocab": "token"}

    # Success
    with mock.patch("collective.bpmproxy.utils.getUtility") as getUtilityMock:
        vocab_mock = mock.Mock()
        vocab_mock().getTermByToken.return_value = True
        getUtilityMock.return_value = vocab_mock
        validate_camunda_form(json.dumps(data), json.dumps(schema), None)

    # ComponentLookupError
    with mock.patch(
        "collective.bpmproxy.utils.getUtility", side_effect=ComponentLookupError
    ):
        with pytest.raises(AssertionError, match="must define vocabulary"):
            validate_camunda_form(json.dumps(data), json.dumps(schema), None)

    # LookupError
    with mock.patch("collective.bpmproxy.utils.getUtility") as getUtilityMock:
        vocab_mock = mock.Mock()
        vocab_mock().getTermByToken.side_effect = LookupError
        getUtilityMock.return_value = vocab_mock
        with pytest.raises(AssertionError, match="must be selected from given options"):
            validate_camunda_form(json.dumps(data), json.dumps(schema), None)


class DummyIface(Interface):
    pass


@implementer(DummyIface)
class DummyParent:
    pass


class DummyChild:
    pass


def test_parents():
    p = DummyParent()
    c = DummyChild()
    c.__parent__ = p  # typical plone acquisition mock if we don't have extension class

    # Just mock aq_inner and aq_parent
    with (
        mock.patch("collective.bpmproxy.utils.aq_inner") as inner_mock,
        mock.patch("collective.bpmproxy.utils.aq_parent") as parent_mock,
    ):
        inner_mock.side_effect = lambda x: x

        def parent_side_effect(x):
            if x == c:
                return p
            if x == p:
                return None

        parent_mock.side_effect = parent_side_effect

        # Test basic parents
        res = list(parents(c))
        assert res == [c, p]

        # Test with interface
        res_iface = list(parents(c, DummyIface))
        assert res_iface == [p]

        # Test with im_self
        class MethodWrapper:
            def __init__(self, obj):
                self.im_self = obj

        m = MethodWrapper(c)
        res_method = list(parents(m))
        assert res_method == [m, c, p]


def test_side_effect_data_manager():
    called = []

    def my_callable(arg1, arg2):
        called.append((arg1, arg2))

    vote_called = []

    def my_vote(arg1, arg2):
        vote_called.append((arg1, arg2))
        return "vote-result"

    abort_called = []

    def my_abort():
        abort_called.append(True)

    dm = SideEffectDataManager(my_callable, args=(1, 2), vote=my_vote, onAbort=my_abort)

    dm.commit(None)
    dm.abort(None)
    assert abort_called == [True]

    assert dm.sortKey() == str(id(dm))
    dm.abort_sub(None)
    dm.commit_sub(None)
    dm.beforeCompletion(None)
    dm.afterCompletion(None)
    dm.tpc_begin(None)

    assert dm.tpc_vote(None) == "vote-result"
    assert vote_called == [(1, 2)]

    with mock.patch(
        "collective.bpmproxy.utils.SIDE_EFFECT_WORKER.submit"
    ) as submit_mock:
        dm.tpc_finish(None)
        submit_mock.assert_called_once_with(my_callable, 1, 2)

        submit_mock.side_effect = Exception("test")
        dm.tpc_finish(None)  # should swallow exception and log

    dm.tpc_abort(None)

    savepoint = dm.savepoint()
    assert savepoint is not None


def test_is_valid_uuid():
    import uuid

    valid_uuid = str(uuid.uuid4())
    assert is_valid_uuid(valid_uuid)
    assert not is_valid_uuid("invalid-uuid")


class FakeKeyring(list):
    """A stand-in for plone.keyring's Keyring: a list with a .current."""

    @property
    def current(self):
        return self[0]


class FakeKeyManager(dict):
    """A stand-in for plone.keyring's IKeyManager utility."""

    def secret(self, ring="_system"):
        return self[ring].current


@pytest.fixture
def fake_key_manager():
    return FakeKeyManager(_anon=FakeKeyring(["current-secret", "previous-secret"]))


def test_sign_and_verify_anonymous_token(fake_key_manager):
    import uuid

    token = str(uuid.uuid4())
    with mock.patch(
        "collective.bpmproxy.utils.getUtility", return_value=fake_key_manager
    ):
        signed = sign_anonymous_token(token)
        assert signed.startswith(token + ".")
        assert verify_anonymous_token(signed) == token


def test_verify_anonymous_token_accepts_a_previous_keyring_secret(fake_key_manager):
    import uuid

    token = str(uuid.uuid4())
    with mock.patch(
        "collective.bpmproxy.utils.getUtility", return_value=fake_key_manager
    ):
        # Sign with what was, until just now, the current secret.
        old_secret = fake_key_manager["_anon"].current
        signed = sign_anonymous_token(token)
        # Rotate: the secret used to sign is no longer current, but it is
        # still in the ring.
        fake_key_manager["_anon"].insert(0, "rotated-in-secret")
        assert old_secret in fake_key_manager["_anon"]
        assert verify_anonymous_token(signed) == token


def test_verify_anonymous_token_rejects_forgeries():
    import uuid

    unsigned_uuid = str(uuid.uuid4())
    fake_key_manager = FakeKeyManager(_anon=FakeKeyring(["real-secret"]))
    with mock.patch(
        "collective.bpmproxy.utils.getUtility", return_value=fake_key_manager
    ):
        # Not signed at all -- the pre-hardening format, or a bare made-up
        # UUID a client supplied.
        assert verify_anonymous_token(unsigned_uuid) is None
        # Well-formed but signed with a secret that was never in the ring.
        forged = f"{unsigned_uuid}.deadbeef"
        assert verify_anonymous_token(forged) is None
        # Not even a valid UUID as the payload.
        assert verify_anonymous_token("not-a-uuid.deadbeef") is None
        # Empty / None input.
        assert verify_anonymous_token("") is None
        assert verify_anonymous_token(None) is None
