# -*- coding: utf-8 -*-
from __future__ import absolute_import

from Acquisition import aq_inner
from collective.bpmproxy import _
from collective.bpmproxy.client import (
    camunda_client,
    get_available_tasks,
    get_task_variables,
)
from collective.bpmproxy.interfaces import PLONE_TASK_VIEW
from collective.bpmproxy.utils import is_valid_uuid
from plone.app.portlets.portlets import base
from plone.memoize.instance import memoize
from plone.portlets.interfaces import IPortletDataProvider
from plone.uuid.interfaces import IUUID
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from z3c.form import field
from zope import schema
from zope.component import getMultiAdapter
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse, NotFound

import plone.api


class ITasksPortlet(IPortletDataProvider):

    use_context = schema.Bool(
        title=_("Show only tasks for the current context"),
        required=False,
        default=False,
    )


@implementer(ITasksPortlet)
class Assignment(base.Assignment):
    schema = ITasksPortlet
    use_context = False

    def __init__(self, use_context=False):
        self.use_context = use_context

    @property
    def title(self):
        return _("Task list")


class AddForm(base.AddForm):
    schema = ITasksPortlet
    form_fields = field.Fields(ITasksPortlet)
    label = _("Add Task list")
    description = _("This portlet displays available pending BPM tasks.")

    def create(self, data):
        return Assignment(use_context=data["use_context"])


class EditForm(base.EditForm):
    schema = ITasksPortlet
    form_fields = field.Fields(ITasksPortlet)
    label = _("Edit Task list")
    description = _("This portlet displays available pending BPM tasks.")


class Renderer(base.Renderer):
    schema = ITasksPortlet
    _template = ViewPageTemplateFile("tasks.pt")

    def __init__(self, *args):
        base.Renderer.__init__(self, *args)
        context = aq_inner(self.context)
        portal_state = getMultiAdapter(
            (context, self.request), name="plone_portal_state"
        )
        self.anonymous = portal_state.anonymous()
        self.base_url = (
            plone.api.portal.get().absolute_url() + "/@@redirect-to-bpm-task"
        )

    def render(self):
        return self._template()

    @property
    def available(self):
        """Show the portlet only if there are one or more elements."""
        return not self.anonymous and bool(self._data())

    def tasks(self):
        return self._data()

    @memoize
    def _data(self):
        with camunda_client() as client:
            context_key = IUUID(self.context) if self.data.use_context else None
            return get_available_tasks(
                client, context_key=context_key, for_display=True
            )


@implementer(IPublishTraverse)
class RedirectView(BrowserView):
    task_view = PLONE_TASK_VIEW

    def __init__(self, context, request):
        super(RedirectView, self).__init__(context, request)
        self.task_id = None

    def publishTraverse(self, request, name):
        if self.task_id is None:  # ../task_id
            self.task_id = name
        else:
            raise NotFound(self, name, request)
        return self

    def __call__(self):
        with camunda_client() as client:
            variables = get_task_variables(client, self.task_id)
        if not variables or "businessKey" not in variables:
            raise NotFound(self, self.task_id, self.request)
        uuid = variables["businessKey"].split(":", 1)[0]
        if not is_valid_uuid(uuid):
            raise NotFound(self, self.task_id, self.request)
        url = (
            plone.api.portal.get().absolute_url()
            + "/resolveuid/"
            + uuid
            + "/"
            + PLONE_TASK_VIEW
            + "/"
            + self.task_id
        )
        self.request.response.redirect(url)
        return ""
