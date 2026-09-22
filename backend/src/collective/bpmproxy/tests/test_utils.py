from collective.bpmproxy.utils import datetime_to_c7
from collective.bpmproxy.utils import flatten_variables
from collective.bpmproxy.utils import infer_variable
from collective.bpmproxy.utils import infer_variables
from collective.bpmproxy.utils import interpolate
from collective.bpmproxy.utils import is_review_state_allowed
from collective.bpmproxy.utils import is_valid_uuid
from collective.bpmproxy.utils import validate_camunda_form
from dateutil.tz import tzutc
from unittest import mock
import datetime
import json
import pytest


def test_datetime_to_c7():
    # test without timezone (length < 25)
    dt1 = datetime.datetime(2023, 1, 1, 12, 0, 0)
    assert datetime_to_c7(dt1) == "2023-01-01T12:00:00.0+0000"

    # test with timezone (length >= 25)
    dt2 = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=tzutc())
    assert datetime_to_c7(dt2) == "2023-01-01T12:00:00.0+0000"


def test_is_review_state_allowed():
    context = object()

    assert is_review_state_allowed(context, []) is True

    with mock.patch(
        "collective.bpmproxy.utils.plone.api.content.get_state",
        return_value="pending",
    ):
        assert is_review_state_allowed(context, ["pending"]) is True
        assert is_review_state_allowed(context, ["published"]) is False


def test_is_review_state_allowed_without_workflow():
    with mock.patch(
        "collective.bpmproxy.utils.plone.api.content.get_state",
        return_value=None,
    ):
        assert is_review_state_allowed(object(), ["pending"]) is False


def test_infer_variable():
    assert infer_variable(["a", "b"]) == {"value": '["a", "b"]', "type": "Json"}
    assert infer_variable(True) == {"value": True, "type": "Boolean"}
    assert infer_variable(42) == {"value": 42, "type": "Integer"}
    assert infer_variable("hello") == {"value": "hello", "type": "String"}
    # Date inference
    date_var = infer_variable("2023-05-10T12:00:00")
    assert date_var["type"] == "Date"
    assert "2023-05-10T12:00:00" in date_var["value"]


def test_infer_variables():
    assert infer_variables(None) == []
    assert infer_variables({}) == {}
    vars = infer_variables({"a": 1, "b": "hello"})
    assert vars["a"] == {"value": 1, "type": "Integer"}
    assert vars["b"] == {"value": "hello", "type": "String"}


def test_flatten_variables():
    from collections import namedtuple

    Variable = namedtuple("Variable", ["value", "type"])
    variables = {
        "str_var": Variable("hello", "String"),
        "int_var": Variable(42, "Integer"),
        "date_var": Variable("2023-01-01T00:00:00.0+0000", "Date"),
        "null_var": Variable(None, "String"),
    }
    flattened = flatten_variables(variables)
    assert flattened["str_var"] == "hello"
    assert flattened["int_var"] == 42
    assert flattened["date_var"] == "2023-01-01"
    assert "null_var" not in flattened


def test_interpolate():
    def mock_interpolator(val):
        if val == "${test}":
            return "replaced "
        return val

    assert interpolate("${test}", mock_interpolator) == "replaced"
    assert interpolate(["${test}", "other"], mock_interpolator) == ["replaced", "other"]
    assert interpolate({"k": "${test}"}, mock_interpolator) == {"k": "replaced"}
    assert interpolate(None, mock_interpolator) is None
    assert interpolate("text", None) == "text"


def test_is_valid_uuid():
    valid = "550e8400-e29b-41d4-a716-446655440000"
    assert is_valid_uuid(valid) is True
    assert is_valid_uuid("not-a-uuid") is False
    assert is_valid_uuid("550e8400e29b41d4a716446655440000") is True


def test_validate_camunda_form():
    schema = {
        "components": [
            {
                "key": "field1",
                "validate": {"required": True, "minLength": 2, "maxLength": 5},
            },
            {
                "key": "field2",
                "validate": {"pattern": "^[A-Z]+$"},
            },
            {
                "key": "field3",
                "disabled": True,
                "validate": {"required": True},
            },
        ]
    }
    schema_json = json.dumps(schema)

    # Valid data
    valid_data = {"field1": "abc", "field2": "ABC"}
    validate_camunda_form(json.dumps(valid_data), schema_json, None)

    # Missing required field
    invalid_data_1 = {"field2": "ABC"}
    with pytest.raises(AssertionError, match="Field field1 is required."):
        validate_camunda_form(json.dumps(invalid_data_1), schema_json, None)

    # Pattern mismatch
    invalid_data_2 = {"field1": "abc", "field2": "abc"}
    with pytest.raises(AssertionError, match="Field field2 must match pattern"):
        validate_camunda_form(json.dumps(invalid_data_2), schema_json, None)
