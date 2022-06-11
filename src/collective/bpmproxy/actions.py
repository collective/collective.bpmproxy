# -*- coding: utf-8 -*-

from collective.bpmproxy.content.bpm_proxy import IBpmProxy
from collective.easyform import easyformMessageFactory as _
from collective.easyform.actions import Action, ActionFactory
from collective.easyform.api import get_context
from collective.easyform.interfaces import IAction, IMailer
from plone import api
from plone.supermodel.exportimport import BaseHandler
from zope.interface import implementer


class IStartInstanceAction(IAction, IBpmProxy):
    pass


@implementer(IStartInstanceAction)
class StartInstance(Action):
    def __init__(self, **kw):
        for i, f in IBpmProxy.namesAndDescriptions():
            setattr(self, i, kw.pop(i, f.default))
        super(StartInstance, self).__init__(**kw)

    def onSuccess(self, fields, request):
        """e-mails data."""
        pass


StartInstanceAction = ActionFactory(
    StartInstance,
    _(u"label_start_instance_action", default=u"Start process instance"),
    "cmf.ModifyPortalContent",
)

StartInstanceHandler = BaseHandler(StartInstance)
