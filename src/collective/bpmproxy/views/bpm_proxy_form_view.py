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
    return dict((name, variable.value) for name, variable in variables.items())


class BpmProxyStartFormView(BrowserView):
    def __init__(self, context, request):
        super(BpmProxyStartFormView, self).__init__(context, request)

        self.state = State.NEW
        self.schema = "{}"

    def update(self):
        self.key = self.context.process_definition_key
        self.api = generic_camunda_client.Configuration(host=get_api_url())
        self.authorization = get_authorization()

    def _view(self):
        with generic_camunda_client.ApiClient(
            self.api, header_name="Authorization", header_value=self.authorization
        ) as client:
            api = generic_camunda_client.ProcessDefinitionApi(client)
            schema = api.get_deployed_start_form_by_key(self.key)
            with open(schema) as fp:
                self.schema = fp.read()
        return self.index()

    def _submit(self):
        with generic_camunda_client.ApiClient(
            self.api, header_name="Authorization", header_value=self.authorization
        ) as client:
            api = generic_camunda_client.ProcessDefinitionApi(client)
            data = json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            payload = {
                "variables": infer_variables(data),
                "businessKey": IUUID(self.context),
            }
            try:
                api.start_process_instance_by_key(
                    self.key, start_process_instance_dto=payload
                )
                self.state = State.SUCCESS
                plone.api.portal.show_message(
                    message=_("Submit successful."),
                    request=self.request,
                    type=Type.INFO,
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
            self.api, header_name="Authorization", header_value=self.authorization
        ) as client:
            api = generic_camunda_client.TaskApi(client)
            try:
                schema = api.get_deployed_form(self.task_id)
                variables = generic_camunda_client.TaskVariableApi(
                    client
                ).get_task_variables(self.task_id)
                local_variables = generic_camunda_client.TaskLocalVariableApi(
                    client
                ).get_task_local_variables(self.task_id)
                data = flatten_variables(variables)
                data.update(flatten_variables(local_variables))
                self.data = json.dumps(data)
                with open(schema) as fp:
                    self.schema = fp.read()
                return self.index()
            except ApiException as e:
                raise NotFound(self, self.task_id, self.request)

    def _submit(self):
        with generic_camunda_client.ApiClient(
            self.api, header_name="Authorization", header_value=self.authorization
        ) as client:
            api = generic_camunda_client.TaskApi(client)
            data = json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            payload = {
                "variables": infer_variables(data),
                "withVariablesInReturn": True,
            }
            try:
                api.complete(self.task_id, complete_task_dto=payload)
                self.state = State.SUCCESS
                plone.api.portal.show_message(
                    message=_("Submit successful."),
                    request=self.request,
                    type=Type.INFO,
                )
            except ApiException as e:
                self.state = State.ERROR
                plone.api.portal.show_message(
                    message=_("Unexpected error on submit."),
                    request=self.request,
                    type=Type.ERROR,
                )
                logger.error("Exception when calling TaskApi->complete: %s\n", e)
        return self.index()

    def __call__(self):
        self.update()
        if self.request.method == HTTP.POST:
            check(self.request)
            return self._submit()
        else:
            return self._view()
