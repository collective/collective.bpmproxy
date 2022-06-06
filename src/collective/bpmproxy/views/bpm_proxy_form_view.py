# -*- coding: utf-8 -*-
from __future__ import print_function

from collective.bpmproxy import _
from generic_camunda_client.rest import ApiException
from plone.protect.authenticator import check
from plone.uuid.interfaces import IUUID
from Products.Five.browser import BrowserView
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse, NotFound

import datetime
import generic_camunda_client
import json
import jwt
import logging
import os
import plone.api
import re
import six


CAMUNDA_API_URL_ENV = "CAMUNDA_API_URL"
CAMUNDA_API_URL_DEFAULT = "http://localhost:8081/engine-rest"
CAMUNDA_API_PRIVATE_KEY_ENV = "CAMUNDA_API_PRIVATE_KEY"
FORM_DATA_KEY = "collective-bpmproxy-form-data"

# openssl ecparam -name prime256v1 -genkey -noout -out ec-prime256v1-priv-key.pem
# openssl ec -in ec-prime256v1-priv-key.pem -pubout > ec-prime256v1-pub-key.pem

logger = logging.getLogger(__name__)


class State:
    NEW = "NEW"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class HTTP:
    GET = "GET"
    POST = "POST"


class Type:
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


def get_api_url():
    return os.environ.get(CAMUNDA_API_URL_ENV) or CAMUNDA_API_URL_DEFAULT


def get_token(username, groups):
    private_key = os.environ.get(CAMUNDA_API_PRIVATE_KEY_ENV)
    if private_key and os.path.exists(private_key):
        with open(private_key, "r", encoding="utf-8") as fp:
            private_key = fp.read()
    if not private_key:
        return None
    return jwt.encode(
        {
            "sub": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=3600),
            "groups": groups,
        },
        private_key,
        algorithm="ES256",
    ).decode("utf-8")


def get_authorization():
    user = plone.api.user.get_current()
    token = get_token(
        username=user and user.getUserName() or None,
        groups=user
        and [g.getId() for g in plone.api.group.get_groups(user=user) or []],
    )
    return token and "Bearer " + token or None


def infer_value(value):
    if isinstance(value, bool):
        return {"value": value, "type": "Boolean"}
    elif isinstance(value, int):
        return {"value": value, "type": "Integer"}
    else:
        return {"value": str(value), "type": "String"}


def infer_variables(data):
    if not isinstance(data, dict):
        return []

    variables = {}
    for key, value in data.items():
        variables[key] = infer_value(value)
    return variables


def flatten_variables(variables):
    return dict([(name, variable.value) for name, variable in variables.items()
                if variable.value is not None])


def convert_tales_expressions(schema_json):
    user = plone.api.user.get_current()
    if '"defaultValue": "here/memberId"' in schema_json:
        schema_json = schema_json.replace(
            '"defaultValue": "here/memberId"',
            '"defaultValue": ' + json.dumps(user.getUserName() or ""),
        )
    if '"defaultValue": "here/memberFullName"' in schema_json:
        schema_json = schema_json.replace(
            '"defaultValue": "here/memberFullName"',
            '"defaultValue": ' + json.dumps(user.getProperty("fullname") or ""),
        )
    if '"defaultValue": "here/memberEmail"' in schema_json:
        schema_json = schema_json.replace(
            '"defaultValue": "here/memberEmail"',
            '"defaultValue": ' + json.dumps(user.getProperty("email") or ""),
        )
    return schema_json


def enforce_schema(data, schema_json):
    schema = json.loads(schema_json)
    for component in schema.get("components") or []:
        key = component.get("key")
        if not key:
            continue

        # Trim strings
        if isinstance(data.get(key), six.text_type):
            data[key] = data[key].strip()

        # Apply default value
        default = component.get("defaultValue")
        if default is not None and data.get(key) is None:
            data[key] = default

        # Skip validation of disabled fields
        if component.get("disabled"):
            continue

        # Backend validation
        validation = component.get("validate") or {}

        pattern = validation.get("pattern")
        assert not pattern or re.match(pattern, data.get(key) or ""), (
            "Field " + key + " must match pattern /" + pattern + "/."
        )

        required = validation.get("required")
        assert not required or data.get(key) not in [None, ""], (
            "Field " + key + " is required."
        )

        min_value = validation.get("min")
        assert min_value is None or data.get(key) or 0 >= min_value, (
            "Field " + key + " must have minimum value of " + min_value + "."
        )

        max_value = validation.get("max")
        assert max_value is None or data.get(key) or 0 <= max_value, (
            "Field " + key + " must have maximum value of " + max_value + "."
        )

        min_length = validation.get("minLength")
        assert min_length is None or len(data.get(key) or "") >= min_length, (
            "Field " + key + " must have minimum length of " + min_length + "."
        )

        max_length = validation.get("maxLength")
        assert max_length is None or len(data.get(key) or "") <= max_length, (
            "Field " + key + " must have maximum length of " + max_length + "."
        )

    return data


class BpmProxyStartFormView(BrowserView):
    def __init__(self, context, request):
        super(BpmProxyStartFormView, self).__init__(context, request)

        self.state = State.NEW
        self.data = "{}"
        self.schema = "{}"
        self.tasks = []

    def update(self):
        self.key = self.context.process_definition_key
        self.api = generic_camunda_client.Configuration(host=get_api_url())
        self.authorization = get_authorization()

    def _view(self):
        with generic_camunda_client.ApiClient(
            self.api,
            header_name=self.authorization and "Authorization" or None,
            header_value=self.authorization,
        ) as client:
            api = generic_camunda_client.ProcessDefinitionApi(client)
            with open(api.get_deployed_start_form_by_key(self.key)) as fp:
                self.schema = convert_tales_expressions(fp.read())
            tasks_api = generic_camunda_client.TaskApi(client)
            self.tasks = tasks_api.query_tasks(
                task_query_dto=dict(processInstanceBusinessKey=IUUID(self.context))
            )
        return self.index()

    def _submit(self):
        with generic_camunda_client.ApiClient(
            self.api,
            header_name=self.authorization and "Authorization" or None,
            header_value=self.authorization,
        ) as client:
            api = generic_camunda_client.ProcessDefinitionApi(client)
            with open(api.get_deployed_start_form_by_key(self.key)) as fp:
                schema = convert_tales_expressions(fp.read())
            data = json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            try:
                data.update({"portalUrl": plone.api.portal.get().absolute_url()})
                payload = {
                    "variables": infer_variables(enforce_schema(data, schema)),
                    "businessKey": IUUID(self.context),
                }
                api.start_process_instance_by_key(
                    self.key, start_process_instance_dto=payload
                )
                self.state = State.SUCCESS
                plone.api.portal.show_message(
                    message=_("Submit successful."),
                    request=self.request,
                    type=Type.INFO,
                )
                tasks_api = generic_camunda_client.TaskApi(client)
                self.tasks = tasks_api.query_tasks(
                    task_query_dto=dict(processInstanceBusinessKey=IUUID(self.context))
                )
            except ApiException as e:
                self.state = State.ERROR
                plone.api.portal.show_message(
                    message=_("Unexpected error on submit."),
                    request=self.request,
                    type=Type.ERROR,
                )
                logger.error(
                    "Exception when calling ProcessDefinitionApi->start_process_instance_by_key: %s %s\n",
                    e,
                    payload,
                )
            except AssertionError as e:
                self.state = State.ERROR
                self.data = json.dumps(data)
                self.schema = schema
                plone.api.portal.show_message(
                    message=_("Invalid or missing data."),
                    request=self.request,
                    type=Type.ERROR,
                )
                logger.error(e)
        return self.index()

    def __call__(self):
        self.update()
        if self.request.method == HTTP.POST:
            check(self.request)
            return self._submit()
        else:
            return self._view()


@implementer(IPublishTraverse)
class BpmProxyTaskFormView(BrowserView):
    def __init__(self, context, request):
        super(BpmProxyTaskFormView, self).__init__(context, request)

        self.state = State.NEW
        self.data = "{}"
        self.schema = "{}"
        self.task_id = None
        self.tasks = []

    def publishTraverse(self, request, name):
        if self.task_id is None:  # ../task_id
            self.task_id = name
        else:
            raise NotFound(self, name, request)
        return self

    def update(self):
        self.key = self.context.process_definition_key
        self.api = generic_camunda_client.Configuration(host=get_api_url())
        self.authorization = get_authorization()

    def _view(self):
        with generic_camunda_client.ApiClient(
            self.api,
            header_name=self.authorization and "Authorization" or None,
            header_value=self.authorization,
        ) as client:
            api = generic_camunda_client.TaskApi(client)
            try:
                # Sanity check. Task belongs to this context.
                tasks = api.query_tasks(
                    task_query_dto=dict(processInstanceBusinessKey=IUUID(self.context))
                )
                if self.task_id not in [t.id for t in tasks]:
                    raise NotFound(self, self.task_id, self.request)
                # Get from schema and existing data.
                variables = generic_camunda_client.TaskVariableApi(
                    client
                ).get_task_variables(self.task_id)
                local_variables = generic_camunda_client.TaskLocalVariableApi(
                    client
                ).get_task_local_variables(self.task_id)
                data = flatten_variables(variables)
                data.update(flatten_variables(local_variables))
                self.data = json.dumps(data)
                with open(api.get_deployed_form(self.task_id)) as fp:
                    self.schema = convert_tales_expressions(fp.read())
                return self.index()
            except ApiException as e:
                raise NotFound(self, self.task_id, self.request)

    def _submit(self):
        with generic_camunda_client.ApiClient(
            self.api,
            header_name=self.authorization and "Authorization" or None,
            header_value=self.authorization,
        ) as client:
            api = generic_camunda_client.TaskApi(client)
            data = json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            with open(api.get_deployed_form(self.task_id)) as fp:
                schema = convert_tales_expressions(fp.read())
            try:
                payload = {
                    "variables": infer_variables(enforce_schema(data, schema)),
                    "withVariablesInReturn": True,
                }
                api.complete(self.task_id, complete_task_dto=payload)
                self.state = State.SUCCESS
                plone.api.portal.show_message(
                    message=_("Submit successful."),
                    request=self.request,
                    type=Type.INFO,
                )
                self.request.response.redirect(self.context.absolute_url())
            except ApiException as e:
                self.state = State.ERROR
                plone.api.portal.show_message(
                    message=_("Unexpected error on submit."),
                    request=self.request,
                    type=Type.ERROR,
                )
                logger.error(
                    "Exception when calling TaskApi->complete: %s %s\n", e, payload
                )
            except AssertionError as e:
                self.state = State.ERROR
                self.data = json.dumps(data)
                self.schema = schema
                plone.api.portal.show_message(
                    message=_("Invalid or missing data."),
                    request=self.request,
                    type=Type.ERROR,
                )
                logger.error(e)
        return self.index()

    def __call__(self):
        self.update()
        if self.request.method == HTTP.POST:
            check(self.request)
            return self._submit()
        else:
            return self._view()
