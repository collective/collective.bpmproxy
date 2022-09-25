# -*- coding: utf-8 -*-
from collective.bpmproxy import _
from plone.stringinterp.adapters import BaseSubstitution
from plone.uuid.interfaces import IUUID, IUUIDAware
from zope.component import adapter


@adapter(IUUIDAware)
class UUIDSubstitution(BaseSubstitution):

    category = _("All Content")
    description = _("Unique identifier (UUID) of the content")

    def safe_call(self):
        return IUUID(self.context)
