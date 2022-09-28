# -*- coding: utf-8 -*-
from collective.bpmproxy import _
from plone.stringinterp.adapters import BaseSubstitution
from plone.uuid.interfaces import IUUID, IUUIDAware
from zope.component import adapter
from zope.interface import Interface

import plone.api


@adapter(IUUIDAware)
class UUIDSubstitution(BaseSubstitution):

    category = _("All Content")
    description = _("Unique identifier (UUID) of the content")

    def safe_call(self):
        return IUUID(self.context)


@adapter(Interface)
class HTTPRefererSubstitution(BaseSubstitution):

    category = _("Request")
    description = _("HTTP referer (or came_from-parameter)")

    def safe_call(self):
        request = plone.api.portal.getRequest()
        portal_url = plone.api.portal.get().absolute_url()
        came_from = request.form.get("came_from")
        referer = request.get_header("referer")
        return (
            came_from
            if came_from and came_from.startswith(portal_url)
            else referer
            if referer
            else self.context.absolute_url()
        )
