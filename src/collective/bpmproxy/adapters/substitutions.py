# -*- coding: utf-8 -*-
from collective.bpmproxy import _
from plone.stringinterp.adapters import BaseSubstitution
from plone.uuid.interfaces import IUUID, IUUIDAware
from zope.component import adapter
from zope.interface import Interface

import plone.api

from collective.bpmproxy.utils import parents


@adapter(IUUIDAware)
class UUIDSubstitution(BaseSubstitution):

    category = _("All Content")
    description = _("Unique identifier (UUID) of the content")

    def safe_call(self):
        return IUUID(self.context)


@adapter(IUUIDAware)
class ParentUUIDSubstitution(BaseSubstitution):

    category = _("All Content")
    description = _("Unique identifier (UUID) of the parent")

    def safe_call(self):
        for parent in parents(self.context, iface=IUUIDAware):
            return IUUID(parent)


@adapter(Interface)
class CameFromSubstitution(BaseSubstitution):

    category = _("Request")
    description = _("URL in portal from came_from-parameter")

    def safe_call(self):
        request = plone.api.portal.getRequest()
        portal_url = plone.api.portal.get().absolute_url()
        came_from = request.form.get("came_from")
        return came_from if came_from and came_from.startswith(portal_url) else ""
