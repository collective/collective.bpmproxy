# -*- coding: utf-8 -*-
from collective.bpmproxy.client import camunda_admin_client
from collective.bpmproxy.utils import (
    infer_variables,
    SideEffectDataManager,
    get_tenant_ids,
)
from generic_camunda_client import SignalDto
from OFS.SimpleItem import SimpleItem
from plone.app.contentrules import PloneMessageFactory as _
from plone.app.contentrules.actions import ActionAddForm, ActionEditForm
from plone.app.contentrules.browser.formhelper import ContentRuleFormWrapper
from plone.autoform import directives as form
from plone.contentrules.rule.interfaces import IExecutable, IRuleElementData
from plone.schema import JSONField
from plone.stringinterp.interfaces import IStringInterpolator
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope import schema
from zope.component import adapter
from zope.interface import implementer, Interface

import functools
import generic_camunda_client
import logging
import os
import plone.api.user
import transaction


logger = logging.getLogger(__name__)


class IBpmSignalAction(Interface):
    """Definition of the configuration available for a signal action"""

    name = schema.TextLine(title=_("BPM Signal name"), required=True, default="${uuid}")
    form.widget("payload", klass="pat-code-editor")
    payload = JSONField(
        title=_("JSON Payload"),
        description=_("The process variables you want to dispatch in JSON"),
        required=False,
        defaultFactory=lambda: {
            "uuid": "${uuid}",
        },
    )


@implementer(IBpmSignalAction, IRuleElementData)
class BpmSignalAction(SimpleItem):
    """
    The implementation of the action defined before
    """

    name = ""
    payload = ""

    element = "plone.actions.BpmSignal"

    @property
    def summary(self):
        return self.name


def interpolate(value, interpolator):
    """Recursively interpolate supported values"""
    if isinstance(value, str):
        return interpolator(value).strip()
    elif isinstance(value, list):
        return [interpolate(v, interpolator) for v in value]
    elif isinstance(value, dict):
        return dict([(k, interpolate(v, interpolator)) for k, v in value.items()])
    return value


def _throwSignal(signal, payload, username=None, tenant_ids=None):
    with camunda_admin_client(username, tenant_ids) as client:
        api = generic_camunda_client.SignalApi(client)
        for tenant_id in tenant_ids or []:
            dto = SignalDto(
                name=signal, variables=infer_variables(payload), tenant_id=tenant_id
            )
            api.throw_signal(signal_dto=dto)
        dto = SignalDto(
            name=signal,
            variables=infer_variables(payload),
            without_tenant_id="true",
        )
        api.throw_signal(signal_dto=dto)


@implementer(IExecutable)
@adapter(Interface, IBpmSignalAction, Interface)
class BpmSignalActionExecutor(object):
    """The executor for this action."""

    def __init__(self, context, element, event):
        self.context = context
        self.element = element
        self.event = event

    def __call__(self):
        interpolator = IStringInterpolator(self.event.object)
        name = interpolate(self.element.name, interpolator)
        payload = interpolate(self.element.payload, interpolator)
        if not plone.api.user.is_anonymous():
            username = plone.api.user.get_current().getUserName()
        else:
            username = None
        tenant_ids = get_tenant_ids()
        transaction.get().join(
            SideEffectDataManager(
                functools.partial(_throwSignal, name, payload, username, tenant_ids)
            )
        )
        return True


class BpmSignalAddForm(ActionAddForm):
    """
    An add form for the BPM Signal action
    """

    schema = IBpmSignalAction
    label = _("Add BPM Signal Action")
    description = _(
        "A PBM Signal action can broadcast BPMN signal "
        "with interpolated JSON process variables payload."
    )
    form_name = _("Configure element")
    Type = BpmSignalAction

    # custom template will allow us to add help text
    template = ViewPageTemplateFile(
        os.path.join("templates", "signal.pt"),
    )


class BpmSignalAddFormView(ContentRuleFormWrapper):
    form = BpmSignalAddForm


class BpmSignalEditForm(ActionEditForm):
    """
    An edit form for the BPM Signal action
    """

    schema = IBpmSignalAction
    label = _("Edit BPM Signal Action")
    description = _(
        "A PBM Signal action can broadcast BPMN signal "
        "with interpolated JSON process variables payload."
    )
    form_name = _("Configure element")

    # custom template will allow us to add help text
    template = ViewPageTemplateFile(
        os.path.join("templates", "signal.pt"),
    )


class BpmSignalEditFormView(ContentRuleFormWrapper):
    form = BpmSignalEditForm
