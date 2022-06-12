# -*- coding: utf-8 -*-
from __future__ import print_function
from collective.bpmproxy import _
from collective.bpmproxy.utils import get_api_url, get_authorization
from generic_camunda_client.rest import ApiException
from plone.protect.authenticator import check
from plone.stringinterp.interfaces import IStringInterpolator
from plone.uuid.interfaces import IUUID
from Products.Five.browser import BrowserView
from uuid import uuid4
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse, NotFound

import generic_camunda_client
import json
import logging
import plone.api
import re
import six


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
    return dict(
        [
            (name, variable.value)
            for name, variable in variables.items()
            if variable.value is not None
        ]
    )


def interpolate(value, interpolator):
    if isinstance(value, six.text_type):
        return interpolator(value).strip()
    elif isinstance(value, list) or isinstance(value, tuple):
        return [interpolate(v) for v in value]
    elif isinstance(value, dict):
        return dict([(k, interpolate(v)) for k, v in value.items()])
    return value


def prepare_form(schema_json, default_data, default_values, interpolator):
    schema = json.loads(schema_json)
    data = {}
    for component in schema.get("components") or []:
        key = component.get("key")
        if default_data.get(key) is not None:
            value = default_data[key]
            if isinstance(value, six.text_type):
                data[key] = value.strip()
            else:
                data[key] = value
        elif key in default_values:
            data[key] = interpolate(default_values[key], interpolator)
    return json.dumps(schema), json.dumps(data)


def validate(data, schema_json):
    schema = json.loads(schema_json)

    for component in schema.get("components") or []:
        if component.get("disabled"):
            # Skip validation of disabled fields
            continue

        key = component.get("key")
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
            interpolator = IStringInterpolator(self.context)
            with open(api.get_deployed_start_form_by_key(self.key)) as fp:
                self.schema, self.data = prepare_form(
                    fp.read(), {}, self.context.default_values, interpolator
                )
            tasks_api = generic_camunda_client.TaskApi(client)
            needle = IUUID(self.context) + ":%"
            self.tasks = tasks_api.query_tasks(
                task_query_dto=dict(processInstanceBusinessKeyLike=needle),
            )
        return self.index()

    def _submit(self):
        with generic_camunda_client.ApiClient(
            self.api,
            header_name=self.authorization and "Authorization" or None,
            header_value=self.authorization,
        ) as client:
            api = generic_camunda_client.ProcessDefinitionApi(client)
            interpolator = IStringInterpolator(self.context)
            data = json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            with open(api.get_deployed_start_form_by_key(self.key)) as fp:
                self.schema, self.data = prepare_form(
                    fp.read(), data, self.context.default_values, interpolator
                )
            try:
                data = json.loads(self.data)
                validate(data, self.schema)
                data.update(
                    dict(
                        [
                            (k, interpolator(v))
                            for k, v in self.context.process_variables.items()
                        ]
                    )
                )
                payload = {
                    "variables": infer_variables(data),
                    "businessKey": ":".join([
                        IUUID(self.context),
                        str(uuid4()),
                    ]),
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
                needle = IUUID(self.context) + ":%"
                self.tasks = tasks_api.query_tasks(
                    task_query_dto=dict(processInstanceBusinessKeyLike=needle),
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


class BpmProxyTaskAttachmentsView(BrowserView):
    def __init__(self, context, request):
        self.context = context.context
        self.request = request
        self.task_id = context.task_id

    def update(self):
        self.key = self.context.process_definition_key
        self.api = generic_camunda_client.Configuration(host=get_api_url())
        self.authorization = get_authorization()

    def __call__(self):
        self.update()
        with generic_camunda_client.ApiClient(
            self.api,
            header_name=self.authorization and "Authorization" or None,
            header_value=self.authorization,
        ) as client:
            api = generic_camunda_client.TaskApi(client)
            try:
                # Sanity check. Task belongs to this context.
                needle = IUUID(self.context) + ":%"
                tasks = dict([(task.id, task) for task in api.query_tasks(
                    task_query_dto=dict(processInstanceBusinessKeyLike=needle),
                )])
                task = tasks.get(self.task_id)
                if task is None:
                    raise NotFound(self, self.task_id, self.request)
                return str(task)
            # {'assignee': None,
            #  'camunda_form_ref': {'binding': {'binding': None,
            #                                   'key': None,
            #                                   'version': None},
            #                       'key': {'binding': None, 'key': None,
            #                               'version': None},
            #                       'version': None},
            #  'case_definition_id': None,
            #  'case_execution_id': None,
            #  'case_instance_id': None,
            #  'created': datetime.datetime(2022, 6, 11, 20, 29, 11, 712000,
            #                               tzinfo=tzoffset(None, 10800)),
            #  'delegation_state': None,
            #  'description': None,
            #  'due': None,
            #  'execution_id': '16531',
            #  'follow_up': None,
            #  'form_key': None,
            #  'id': '16563',
            #  'name': 'Enter reviewer manually',
            #  'owner': None,
            #  'parent_task_id': None,
            #  'priority': 50,
            #  'process_definition_id': 'example-approval-process:12:16418',
            #  'process_instance_id': '16531',
            #  'suspended': False,
            #  'task_definition_key': 'Activity_00e5qi0',
            #  'tenant_id': None}
            finally:
                pass


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
                needle = IUUID(self.context) + ":%"
                tasks = api.query_tasks(
                    task_query_dto=dict(processInstanceBusinessKeyLike=needle),
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
                interpolator = IStringInterpolator(self.context)
                with open(api.get_deployed_form(self.task_id)) as fp:
                    self.schema, self.data = prepare_form(
                        fp.read(), data, self.context.default_values, interpolator
                    )
            except ApiException as e:
                logger.error("Exception when fetching task for rendering: %s\n", e)
                logger.warning(e)
                raise NotFound(self, self.task_id, self.request)
        return self.index()

    def _submit(self):
        with generic_camunda_client.ApiClient(
            self.api,
            header_name=self.authorization and "Authorization" or None,
            header_value=self.authorization,
        ) as client:
            api = generic_camunda_client.TaskApi(client)
            # Get from schema and existing data.
            variables = generic_camunda_client.TaskVariableApi(
                client
            ).get_task_variables(self.task_id)
            local_variables = generic_camunda_client.TaskLocalVariableApi(
                client
            ).get_task_local_variables(self.task_id)
            data = flatten_variables(variables)
            data.update(flatten_variables(local_variables))
            data.update(json.loads(self.request.form.get(FORM_DATA_KEY) or "{}"))
            interpolator = IStringInterpolator(self.context)
            with open(api.get_deployed_form(self.task_id)) as fp:
                self.schema, self.data = prepare_form(
                    fp.read(), data, self.context.default_values, interpolator
                )
            try:
                data = json.loads(self.data)
                validate(data, self.schema)
                payload = {
                    "variables": infer_variables(data),
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
