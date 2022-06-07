# -*- coding: utf-8 -*-
# from plone.app.textfield import RichText
# from plone.autoform import directives

from collective.bpmproxy import _
# from plone.supermodel.directives import fieldset
# from z3c.form.browser.radio import RadioFieldWidget
from plone.autoform import directives as form
from plone.schema.jsonfield import JSONField
# from plone.namedfile import field as namedfile
from plone.supermodel import model
from zope import schema


class PatternsSettings(object):
    def __init__(self, context, request, field):
        self.request = request
        self.context = context
        self.field = field

    def __call__(self):
        return {
            # 'data-pat-code-editor': 'language: json; theme: tomorrow;',
            "data-pat-code-editor": "language: js; theme: tomorrow;",
        }


class IBpmProxy(model.Schema):
    """Marker interface and Dexterity Python Schema for BpmProxy"""

    process_definition_key = schema.Choice(
        title=_(u"Process Definition"),
        required=True,
        vocabulary="collective.bpmproxy.AvailableProcessDefinitions",
    )

    form.widget("process_variables", klass="pat-code-editor")
    process_variables = JSONField(
        title=_(u"Initial process variables"),
        description=_(
            u"Must be valid JSON. Values may contain Plone string substitutions."
        ),
        required=True,
        defaultFactory=lambda: {
            "portalUrl": "${portal_url}",
        },
    )

    form.widget("default_values", klass="pat-code-editor")
    default_values = JSONField(
        title=_(u"Default form values"),
        description=_(
            u"Must be valid JSON. Values may contain Plone string substitutions."
        ),
        required=True,
        defaultFactory=lambda: {
            "authorEmail": "${user_email}",
            "authorFullName": "${user_fullname}",
        },
    )

    # If you want, you can load a xml model created TTW here
    # and customize it in Python:

    # model.load('bpm_proxy.xml')

    # directives.widget(level=RadioFieldWidget)
    # level = schema.Choice(
    #     title=_(u'Sponsoring Level'),
    #     vocabulary=LevelVocabulary,
    #     required=True
    # )

    # text = RichText(
    #     title=_(u'Text'),
    #     required=False
    # )

    # url = schema.URI(
    #     title=_(u'Link'),
    #     required=False
    # )

    # fieldset('Images', fields=['logo', 'advertisement'])
    # logo = namedfile.NamedBlobImage(
    #     title=_(u'Logo'),
    #     required=False,
    # )

    # advertisement = namedfile.NamedBlobImage(
    #     title=_(u'Advertisement (Gold-sponsors and above)'),
    #     required=False,
    # )

    # directives.read_permission(notes='cmf.ManagePortal')
    # directives.write_permission(notes='cmf.ManagePortal')
    # notes = RichText(
    #     title=_(u'Secret Notes (only for site-admins)'),
    #     required=False
    # )
