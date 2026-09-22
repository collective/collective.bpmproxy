from Acquisition import aq_inner
from collective.bpmproxy import _
from collective.bpmproxy.actions.signal import _throwSignal
from collective.bpmproxy.actions.signal import interpolate
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import get_available_tasks
from collective.bpmproxy.interfaces import ANONYMOUS_USER_ANNOTATION_KEY
from collective.bpmproxy.interfaces import PLONE_TASK_VIEW
from collective.bpmproxy.utils import get_tenant_ids
from collective.bpmproxy.utils import is_review_state_allowed
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
class SignalForm(Form):
    ignoreContext = True

    def __init__(self, context, request, prefix, label, signal, payload):
        self.prefix = prefix
        self.label = label
        self.signal = signal
        self.payload = payload
        super().__init__(context, request)

        # button with dynamic label
        self.handlers = button.Handlers()
        new_button = button.Button(name=signal, title=label)
        self.buttons += button.Buttons(new_button)
        self.handlers.addHandler(new_button, self.dispatch)

    def dispatch(self, form, action):
        assert form and action
        interpolator = IStringInterpolator(self.context)
        name = interpolate(self.signal, interpolator)
        payload = interpolate(self.payload, interpolator)
        if not plone.api.user.is_anonymous():
            username = plone.api.user.get_current().getUserName()
        else:
            username = None
        _throwSignal(name, payload, username, get_tenant_ids())
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


class ISignalPortlet(IPortletDataProvider):
    header = schema.TextLine(
        title=_("Button label"),
        description=_("Label for the rendered button"),
        required=False,
    )

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

    review_states = schema.List(
        title=_("Display for review states"),
        description=_("Leave empty to display for all review states."),
        value_type=schema.Choice(vocabulary="plone.app.vocabularies.WorkflowStates"),
        required=False,
        missing_value=[],
        defaultFactory=list,
    )


@implementer(ISignalPortlet)
class Assignment(base.Assignment):
    schema = ISignalPortlet
    header = None
    name = False
    payload = None
    review_states = []

    def __init__(self, header=None, name=False, payload=None, review_states=None):
        self.header = header
        self.name = name
        self.payload = payload
        self.review_states = review_states or []

    @property
    def title(self):
        return _("Signal dispatch")


class AddForm(base.AddForm):
    schema = ISignalPortlet
    form_fields = field.Fields(ISignalPortlet)
    label = _("Add Signal dispatch")
    description = _("This portlet displays button for dispatching BPM Signal.")

    def create(self, data):
        return Assignment(
            header=data["header"],
            name=data["name"],
            payload=data["payload"],
            review_states=data.get("review_states", []),
        )


class EditForm(base.EditForm):
    schema = ISignalPortlet
    form_fields = field.Fields(ISignalPortlet)
    label = _("Edit Signal dispatch")
    description = _("This portlet displays button for dispatching BPM Signal.")


class Renderer(base.Renderer):
    schema = ISignalPortlet

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
        return not self.anonymous and is_review_state_allowed(
            self.context, self.data.review_states
        )

    def render(self):
        prefix = f"{hashlib.md5(self.data.name.encode('utf-8')).hexdigest()}."
        self.form = SignalForm(
            self.context,
            self.request,
            prefix,
            self.data.header,
            self.data.name,
            self.data.payload,
        )
        self.form.update()
        return self.form.render()
