# -*- coding: utf-8 -*-
from plone.app.contenttypes.interfaces import IFile
from plone.namedfile.field import NamedBlobFile
from plone.supermodel import model
from zope import schema
from zope.i18nmessageid import MessageFactory


_ = MessageFactory("plone")


class IBpmAttachment(IFile, model.Schema):
    """Marker interface for BpmAttachment"""

    title = schema.TextLine(
        title=_("Title"),
        required=False,
    )

    description = schema.Text(
        title=_("Description"),
        required=False,
    )

    # noinspection PyUnresolvedReferences
    model.primary("file")
    file = NamedBlobFile(
        title=_("File"),
    )
