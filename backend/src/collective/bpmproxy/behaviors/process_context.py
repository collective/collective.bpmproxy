from collective.bpmproxy import _
from plone.autoform import directives as form
from plone.autoform.interfaces import IFormFieldProvider
from plone.schema.jsonfield import JSONField
from plone.supermodel import model
from zope import schema
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from zope.interface import provider


class IProcessContext(Interface):
    """Marker for content configured to start and host BPM processes."""


@provider(IFormFieldProvider)
class IProcessContextBehavior(model.Schema):
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

    interactive_start_enabled = schema.Bool(
        title=_("Allow starting this process interactively"),
        required=False,
        default=True,
    )

    form.widget("process_variables", klass="pat-code-editor")
    process_variables = JSONField(
        title=_("Initial process variables"),
        description=_(
            "Must be valid JSON. Values may contain Plone string substitutions."
        ),
        required=True,
        defaultFactory=lambda: {"portalUrl": "${portal_url}"},
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


_SCHEMA_FIELD_NAMES = frozenset(IProcessContextBehavior.names())


@implementer(IProcessContextBehavior)
@adapter(IProcessContext)
class ProcessContextBehavior:
    def __init__(self, context):
        self.context = context

    def __getattr__(self, name):
        return getattr(self.context, name)

    def __setattr__(self, name, value):
        if name == "context":
            object.__setattr__(self, name, value)
        elif name in _SCHEMA_FIELD_NAMES:
            setattr(self.context, name, value)
        else:
            # Only schema fields belong on the content object. Without this,
            # any attribute set on the adapter silently became content state.
            object.__setattr__(self, name, value)
