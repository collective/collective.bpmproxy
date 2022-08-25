# -*- coding: utf-8 -*-
from __future__ import print_function

from collective.bpmproxy import _
from collective.bpmproxy.client import (
    camunda_client,
    get_available_tasks,
    get_diagram_xml,
    get_next_tasks,
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
from Products.CMFPlone.browser.interfaces import INavigationBreadcrumbs
from Products.CMFPlone.browser.navigation import PhysicalNavigationBreadcrumbs
from Products.Five.browser import BrowserView
from uuid import UUID, uuid4
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse, NotFound

import json
import logging
import plone.api


logger = logging.getLogger(__name__)


@implementer(INavigationBreadcrumbs)
class BpmProxyNavigationBreadcrumbs(PhysicalNavigationBreadcrumbs):
    def breadcrumbs(self):
        base = super(BpmProxyNavigationBreadcrumbs, self).breadcrumbs()

        task_view = getattr(self.request, "PUBLISHED", None)
        task_id = getattr(task_view, "task_id", None)
        task_title = getattr(task_view, "task_title", None)

        if task_id and task_title:
            return base + (
                {
                    "absolute_url": "/".join(
                        [self.context.absolute_url(), "@@task", task_id]
                    ),
                    "Title": task_title,
                },
            )
        else:
            return base

    def customize_entry(self, entry, context=None):
        """a little helper to enlarge customizability."""
        pass


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
                process = submit_start_form(
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
                process = None
                plone.api.portal.show_message(
                    message=_("Unexpected error on submit."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
            except AssertionError as e:
                process = None
                plone.api.portal.show_message(
                    message=_("Invalid or missing data."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                logger.error(e)
            try:
                next_tasks = get_next_tasks(client, process.id) if process else []
                for task in next_tasks:
                    url = "/".join([
                        self.context.absolute_url(),
                        "@@task",
                        task.id
                    ])
                    if self.context.diagram_enabled:
                        url += "#autotoc-item-autotoc-0"
                    self.request.response.redirect(url)
                    break
            except ApiException:
                pass  # process may have already ended
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
        self.attachments_key = None

        self.data = "{}"
        self.schema = "{}"
        self.task_id = None
        self.task_title = None
        self.task_description = None

    def publishTraverse(self, request, name):
        if self.task_id is None:  # ../task_id
            self.task_id = name
        else:
            raise NotFound(self, name, request)
        return self

    def _view(self, task):
        with camunda_client() as client:
            try:
                # Get data.
                self.task_title = task.name
                self.task_description = task.description
                self.task_definition_key = task.task_definition_key
                current_values = get_task_variables(client, self.task_id)

                # Get diagram
                if self.context.diagram_enabled:
                    self.diagram_xml = get_diagram_xml(
                        client, task.process_definition_id
                    )

                # Enable attachments when possible.
                try:
                    self.attachments_key = str(
                        UUID(current_values.get(ATTACHMENTS_KEY_KEY))
                    )
                    self.attachments_enabled = bool(self.attachments_key)
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

    def _submit(self, task):
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
            try:
                next_tasks = get_next_tasks(client, task.process_instance_id)
                for task in next_tasks:
                    url = "/".join([
                        self.context.absolute_url(),
                        "@@task",
                        task.id
                    ])
                    if self.context.diagram_enabled:
                        url += "#autotoc-item-autotoc-0"
                    self.request.response.redirect(url)
                    break
            except ApiException:
                pass  # process may have already ended
        return self.index()

    def __call__(self):
        with camunda_client() as client:
            try:
                # Sanity check. Task belongs to this context.
                tasks = dict(
                    (task.id, task)
                    for task in get_available_tasks(
                        client, context_key=IUUID(self.context)
                    )
                )
                if self.task_id not in tasks:
                    plone.api.portal.show_message(
                        message=_("Task not found or no longer available."),
                        request=self.request,
                        type=PloneNotificationLevel.ERROR,
                    )
                    self.request.response.redirect(self.context.absolute_url())
                    return ""
            except ApiException as e:
                plone.api.portal.show_message(
                    message=_("Unexpected error."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                self.request.response.redirect(self.context.absolute_url())
                return u""
        if self.request.method == HTTPMethod.POST:
            check(self.request)
            return self._submit(tasks[self.task_id])
        else:
            return self._view(tasks[self.task_id])
