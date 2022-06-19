# -*- coding: utf-8 -*-
from __future__ import print_function

from collective.bpmproxy import _
from collective.bpmproxy.client import (
    camunda_client,
    get_available_tasks,
    get_start_form,
    get_task_form,
    get_task_variables,
    submit_start_form,
    submit_task_form,
)
from collective.bpmproxy.interfaces import (
    ATTACHMENTS_KEY_KEY,
    FORM_DATA_KEY,
    HTTPMethod,
    PloneNotificationLevel,
)
from collective.bpmproxy.utils import validate_camunda_form
from generic_camunda_client.rest import ApiException
from plone.protect.authenticator import check
from plone.stringinterp.interfaces import IStringInterpolator
from plone.uuid.interfaces import IUUID
from Products.Five.browser import BrowserView
from uuid import UUID, uuid4
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse, NotFound

import json
import logging
import plone.api


logger = logging.getLogger(__name__)


class BpmProxyStartFormView(BrowserView):
    def __init__(self, context, request):
        super(BpmProxyStartFormView, self).__init__(context, request)

        self.data = "{}"
        self.schema = "{}"
        self.tasks = []

    def _view(self):
        with camunda_client() as client:
            self.data, self.schema = get_start_form(
                client,
                self.context.process_definition_key,
                default_values=self.context.default_values,
                interpolator=IStringInterpolator(self.context),
            )
            self.tasks = get_available_tasks(client, context_key=IUUID(self.context))
        return self.index()

    def _submit(self):
        with camunda_client() as client:
            current_values = json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            interpolator = IStringInterpolator(self.context)
            self.data, self.schema = get_start_form(
                client,
                self.context.process_definition_key,
                current_values=current_values,
                default_values=self.context.default_values,
                interpolator=interpolator,
            )
            try:
                # Validate
                validate_camunda_form(self.data, self.schema)
                # Submit
                business_key = IUUID(self.context) + ":" + str(uuid4())
                process_variables = self.context.process_variables.copy()
                if self.context.attachments_enabled:
                    process_variables[ATTACHMENTS_KEY_KEY] = business_key.split(":")[-1]
                submit_start_form(
                    client,
                    self.context.process_definition_key,
                    business_key=business_key,
                    form_variables=json.loads(self.data),
                    process_variables=process_variables,
                    interpolator=interpolator,
                )
                plone.api.portal.show_message(
                    message=_("Submit successful."),
                    request=self.request,
                    type=PloneNotificationLevel.INFO,
                )
                self.tasks = get_available_tasks(
                    client, context_key=IUUID(self.context)
                )
            except ApiException:
                plone.api.portal.show_message(
                    message=_("Unexpected error on submit."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
            except AssertionError as e:
                plone.api.portal.show_message(
                    message=_("Invalid or missing data."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                logger.error(e)
        return self.index()

    def __call__(self):
        if self.request.method == HTTPMethod.POST:
            check(self.request)
            return self._submit()
        else:
            return self._view()


@implementer(IPublishTraverse)
class BpmProxyTaskFormView(BrowserView):
    def __init__(self, context, request):
        super(BpmProxyTaskFormView, self).__init__(context, request)

        self.attachments_enabled = False

        self.data = "{}"
        self.schema = "{}"
        self.task_id = None

    def publishTraverse(self, request, name):
        if self.task_id is None:  # ../task_id
            self.task_id = name
        else:
            raise NotFound(self, name, request)
        return self

    def _view(self):
        with camunda_client() as client:
            try:
                # Sanity check. Task belongs to this context.
                tasks = get_available_tasks(client, context_key=IUUID(self.context))
                if self.task_id not in [t.id for t in tasks]:
                    raise NotFound(self, self.task_id, self.request)

                # Get data.
                current_values = get_task_variables(client, self.task_id)

                # Enable attachments when possible.
                try:
                    self.attachments_enabled = bool(
                        UUID(current_values.get(ATTACHMENTS_KEY_KEY))
                    )
                except (TypeError, ValueError):
                    pass

                self.data, self.schema = get_task_form(
                    client,
                    self.task_id,
                    current_values=current_values,
                    default_values=self.context.default_values,
                    interpolator=IStringInterpolator(self.context),
                )
            except ApiException as e:
                logger.error("Exception when fetching task for rendering: %s\n", e)
                logger.warning(e)
                raise NotFound(self, self.task_id, self.request)
        return self.index()

    def _submit(self):
        with camunda_client() as client:
            current_values = get_task_variables(client, self.task_id)
            current_values.update(
                json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            )
            self.data, self.schema = get_task_form(
                client,
                self.task_id,
                current_values=current_values,
                default_values=self.context.default_values,
                interpolator=IStringInterpolator(self.context),
            )
            try:
                validate_camunda_form(self.data, self.schema)
                submit_task_form(client, self.task_id, json.loads(self.data))
                plone.api.portal.show_message(
                    message=_("Submit successful."),
                    request=self.request,
                    type=PloneNotificationLevel.INFO,
                )
                self.request.response.redirect(self.context.absolute_url())
            except ApiException as e:
                plone.api.portal.show_message(
                    message=_("Unexpected error on submit."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
            except AssertionError as e:
                plone.api.portal.show_message(
                    message=_("Invalid or missing data."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                logger.error(e)
        return self.index()

    def __call__(self):
        if self.request.method == HTTPMethod.POST:
            check(self.request)
            return self._submit()
        else:
            return self._view()
