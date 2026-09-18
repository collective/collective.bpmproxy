from Acquisition import aq_inner
from collective.bpmproxy import _
from collective.bpmproxy.actions.message import _throwMessage
from collective.bpmproxy.actions.message import interpolate
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import get_available_tasks
from collective.bpmproxy.interfaces import ANONYMOUS_USER_ANNOTATION_KEY
from collective.bpmproxy.interfaces import PLONE_TASK_VIEW
from collective.bpmproxy.utils import get_tenant_ids
from generic_camunda_client import ApiException
from plone.app.portlets.portlets import base
from plone.autoform import directives as form
from plone.portlets.interfaces import IPortletDataProvider
from plone.schema import JSONField
from plone.stringinterp.interfaces import IStringInterpolator
from plone.uuid.interfaces import IUUID
from plone.z3cform.interfaces import IWrappedForm
from z3c.form import button
from z3c.form import field
from z3c.form.form import Form
from zope import schema
from zope.annotation import IAnnotations
from zope.component import getMultiAdapter
from zope.interface import implementer
import hashlib
import plone.api


@implementer(IWrappedForm)
class MessageForm(Form):
    ignoreContext = True

    def __init__(
        self,
        context,
        request,
        prefix,
        label,
        message,
        businessKey,
        correlationKeys,
        payload,
    ):
        self.prefix = prefix
        self.label = label
        self.message = message
        self.businessKey = businessKey
        self.correlationKeys = correlationKeys
        self.payload = payload
        super().__init__(context, request)

        # button with dynamic label
        self.handlers = button.Handlers()
        new_button = button.Button(name=message, title=label)
        self.buttons += button.Buttons(new_button)
        self.handlers.addHandler(new_button, self.dispatch)

    def dispatch(self, form, action):
        assert form and action
        interpolator = IStringInterpolator(self.context)
        name = interpolate(self.message, interpolator)
        business_key = interpolate(self.businessKey, interpolator)
        correlation_keys = interpolate(self.correlationKeys, interpolator)
        payload = interpolate(self.payload, interpolator)
        if not plone.api.user.is_anonymous():
            username = plone.api.user.get_current().getUserName()
        else:
            username = None
        _throwMessage(
            name,
            business_key,
            correlation_keys,
            payload,
            username,
            get_tenant_ids(),
        )
        with camunda_client() as client:
            try:
                next_tasks = get_available_tasks(
                    client, context_key=IUUID(self.context)
                )
                for task in next_tasks:
                    url = "/".join(
                        [self.context.absolute_url(), PLONE_TASK_VIEW, task.id]
                    )
                    token = IAnnotations(self.request).get(
                        ANONYMOUS_USER_ANNOTATION_KEY
                    )
                    if token:
                        url += "?token=" + token
                    self.request.response.redirect(url)
                    break
            except ApiException:
                pass  # process may have already ended


class IMessagePortlet(IPortletDataProvider):
    header = schema.TextLine(
        title=_("Button label"),
        description=_("Label for the rendered button"),
        required=False,
    )

    name = schema.TextLine(
        title=_("BPM Message name"), required=True, default="${uuid}"
    )

    businessKey = schema.TextLine(
        title=_("Business key"),
        description=_(
            "Correlate only to the process instance with this exact business key."
        ),
        required=False,
    )

    form.widget("correlationKeys", klass="pat-code-editor")
    correlationKeys = JSONField(
        title=_("Correlation keys"),
        description=_(
            "JSON object of process-variable name/value pairs the waiting "
            "process instance must match to receive this message."
        ),
        required=False,
        defaultFactory=lambda: {},
    )

    form.widget("payload", klass="pat-code-editor")
    payload = JSONField(
        title=_("JSON Payload"),
        description=_("The process variables you want to dispatch in JSON"),
        required=False,
        defaultFactory=lambda: {
            "uuid": "${uuid}",
        },
    )


@implementer(IMessagePortlet)
class Assignment(base.Assignment):
    schema = IMessagePortlet
    header = None
    name = False
    businessKey = None
    correlationKeys = None
    payload = None

    def __init__(
        self,
        header=None,
        name=False,
        businessKey=None,
        correlationKeys=None,
        payload=None,
    ):
        self.header = header
        self.name = name
        self.businessKey = businessKey
        self.correlationKeys = correlationKeys
        self.payload = payload

    @property
    def title(self):
        return _("Message dispatch")


class AddForm(base.AddForm):
    schema = IMessagePortlet
    form_fields = field.Fields(IMessagePortlet)
    label = _("Add Message dispatch")
    description = _("This portlet displays button for dispatching a BPM Message.")

    def create(self, data):
        return Assignment(
            header=data["header"],
            name=data["name"],
            businessKey=data["businessKey"],
            correlationKeys=data["correlationKeys"],
            payload=data["payload"],
        )


class EditForm(base.EditForm):
    schema = IMessagePortlet
    form_fields = field.Fields(IMessagePortlet)
    label = _("Edit Message dispatch")
    description = _("This portlet displays button for dispatching a BPM Message.")


class Renderer(base.Renderer):
    schema = IMessagePortlet

    def __init__(self, *args):
        base.Renderer.__init__(self, *args)
        context = aq_inner(self.context)
        portal_state = getMultiAdapter(
            (context, self.request), name="plone_portal_state"
        )
        self.anonymous = portal_state.anonymous()

    @property
    def available(self):
        """Show the portlet only if there are one or more elements."""
        return not self.anonymous

    def render(self):
        prefix = f"{hashlib.md5(self.data.name.encode('utf-8')).hexdigest()}."
        self.form = MessageForm(
            self.context,
            self.request,
            prefix,
            self.data.header,
            self.data.name,
            self.data.businessKey,
            self.data.correlationKeys,
            self.data.payload,
        )
        self.form.update()
        return self.form.render()
