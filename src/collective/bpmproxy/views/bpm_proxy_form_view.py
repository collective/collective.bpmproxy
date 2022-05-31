# -*- coding: utf-8 -*-
from __future__ import print_function
import generic_camunda_client
from generic_camunda_client.rest import ApiException
from pprint import pprint
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse
from collective.bpmproxy import _
from Products.Five.browser import BrowserView
from zope.publisher.interfaces import NotFound
from plone.protect.authenticator import check
from plone.uuid.interfaces import IUUID
from enum import Enum

import json
import plone.api
import logging

FORM_DATA_KEY = "collective-bpmproxy-form-data"

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


class BpmProxyStartFormView(BrowserView):

    def __init__(self, context, request):
        super(BpmProxyStartFormView, self).__init__(context, request)

        self.state = State.NEW
        self.schema = "{}"
    
    def update(self):
        self.key = self.context.process_definition_key

        # TODO: Read dynamically either form plone registry or from addon config
        self.api = generic_camunda_client.Configuration(
            host = "http://localhost:8081/engine-rest"
        )

    def _view(self):
        with generic_camunda_client.ApiClient(self.api) as client:
            api = generic_camunda_client.ProcessDefinitionApi(client)
            schema = api.get_deployed_start_form_by_key(self.key)
            with open(schema) as fp:
                self.schema = fp.read()
        return self.index()

    def _submit(self):
        with generic_camunda_client.ApiClient(self.api) as client:
            api = generic_camunda_client.ProcessDefinitionApi(client)
            data = json.loads(self.request.form.get(FORM_DATA_KEY) or '{}')
            payload = {
                "variables": infer_variables(data),
                "businessKey": IUUID(self.context)
            }
            try:
                api.start_process_instance_by_key(
                    self.key,
                    start_process_instance_dto=payload
                )
                self.state = State.SUCCESS
                plone.api.portal.show_message(
                    message=_('Submit successful.'),
                    request=self.request,
                    type=Type.INFO,
                )
            except ApiException as e:
                self.state = State.ERROR
                plone.api.portal.show_message(
                    message=_('Unexpected error on submit.'),
                    request=self.request,
                    type=Type.ERROR,
                )
                logger.error("Exception when calling ProcessDefinitionApi->start_process_instance_by_key: %s %s\n", e, payload)
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

        # TODO: Read dynamically either form plone registry or from addon config
        self.api = generic_camunda_client.Configuration(
            host = "http://localhost:8081/engine-rest"
        )

    def _view(self):
        with generic_camunda_client.ApiClient(self.api) as client:
            api = generic_camunda_client.TaskApi(client)
            try:
                schema = api.get_deployed_form(self.task_id)
                with open(schema) as fp:
                    self.schema = fp.read()
                return self.index()
            except ApiException as e:
                raise NotFound(self, self.task_id, self.request)

    def _submit(self):
        with generic_camunda_client.ApiClient(self.api) as client:
            api = generic_camunda_client.TaskApi(client)
            data = json.loads(self.request.form.get(FORM_DATA_KEY) or '{}')
            payload = {
                "variables": infer_variables(data),
                "withVariablesInReturn": True,
            }
            try:
                api.complete(self.task_id, complete_task_dto=payload)
                self.state = State.SUCCESS
                plone.api.portal.show_message(
                    message=_('Submit successful.'),
                    request=self.request,
                    type=Type.INFO,
                )
            except ApiException as e:
                self.state = State.ERROR
                plone.api.portal.show_message(
                    message=_('Unexpected error on submit.'),
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