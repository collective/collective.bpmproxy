# -*- coding: utf-8 -*-
from collective.bpmproxy import _
from plone.autoform import directives as form
from plone.schema.jsonfield import JSONField
from plone.supermodel import model
from zope import schema


class IBpmProxy(model.Schema):
    """Marker interface and Dexterity Python Schema for BpmProxy"""

    process_definition_key = schema.Choice(
        title=_("Process Definition"),
        required=True,
        vocabulary="collective.bpmproxy.AvailableProcessDefinitions",
    )

    diagram_enabled = schema.Bool(
        title=_("Show BPMN diagram"),
        required=False,
        default=False,
    )

    attachments_enabled = schema.Bool(
        title=_("Accept attachments"),
        required=False,
        default=False,
    )

    form.widget("process_variables", klass="pat-code-editor")
    process_variables = JSONField(
        title=_("Initial process variables"),
        description=_(
            "Must be valid JSON. Values may contain Plone string substitutions."
        ),
        required=True,
        defaultFactory=lambda: {
            "portalUrl": "${portal_url}",
        },
    )

    form.widget("default_values", klass="pat-code-editor")
    default_values = JSONField(
        title=_("Default form values"),
        description=_(
            "Must be valid JSON. Values may contain Plone string substitutions."
        ),
        required=True,
        defaultFactory=lambda: {
            "authorEmail": "${user_email}",
            "authorFullName": "${user_fullname}",
        },
    )
