from collective.bpmproxy import _
from collective.bpmproxy.client import camunda_admin_client
from collective.bpmproxy.client import join_side_effect
from collective.bpmproxy.utils import get_tenant_ids
from collective.bpmproxy.utils import infer_variables
from collective.bpmproxy.utils import interpolate
from generic_camunda_client import CorrelationMessageDto
from OFS.SimpleItem import SimpleItem
from plone.app.contentrules.actions import ActionAddForm
from plone.app.contentrules.actions import ActionEditForm
from plone.app.contentrules.browser.formhelper import ContentRuleFormWrapper
from plone.autoform import directives as form
from plone.contentrules.rule.interfaces import IExecutable
from plone.contentrules.rule.interfaces import IRuleElementData
from plone.schema import JSONField
from plone.stringinterp.interfaces import IStringInterpolator
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope import schema
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
import generic_camunda_client
import logging
import os
import plone.api.user


logger = logging.getLogger(__name__)


class IBpmMessageAction(Interface):
    """Definition of the configuration available for a message action"""

    name = schema.TextLine(
        title=_("BPM Message name"), required=True, default="${uuid}"
    )

    businessKey = schema.TextLine(
        title=_("Business key"),
        description=_(
            "Correlate only to the process instance with this exact "
            "business key. Leave blank to correlate by Correlation keys "
            "instead."
        ),
        required=False,
    )

    form.widget("correlationKeys", klass="pat-code-editor")
    correlationKeys = JSONField(
        title=_("Correlation keys"),
        description=_(
            "JSON object of process-variable name/value pairs the waiting "
            "process instance must match to receive this message. Unlike a "
            "signal, a message never broadcasts: leaving this and Business "
            "key both blank correlates engine-wide and raises if more than "
            "one instance matches."
        ),
        required=False,
        defaultFactory=lambda: {},
    )

    form.widget("payload", klass="pat-code-editor")
    payload = JSONField(
        title=_("JSON Payload"),
        description=_(
            "The process variables you want to inject into the triggered "
            "execution after the message is delivered, in JSON."
        ),
        required=False,
        defaultFactory=lambda: {
            "uuid": "${uuid}",
        },
    )


@implementer(IBpmMessageAction, IRuleElementData)
class BpmMessageAction(SimpleItem):
    """
    The implementation of the action defined before
    """

    name = ""
    businessKey = ""
    correlationKeys = ""
    payload = ""

    element = "plone.actions.BpmMessage"

    @property
    def summary(self):
        return self.name


def _throwMessage(
    message, business_key, correlation_keys, payload, username=None, tenant_ids=None
):
    kwargs = {}
    if business_key:
        kwargs["business_key"] = business_key
    if correlation_keys:
        kwargs["correlation_keys"] = infer_variables(correlation_keys)
    if payload:
        kwargs["process_variables"] = infer_variables(payload)

    with camunda_admin_client(username, tenant_ids) as client:
        api = generic_camunda_client.MessageApi(client)
        for tenant_id in tenant_ids or []:
            dto = CorrelationMessageDto(
                message_name=message, tenant_id=tenant_id, **kwargs
            )
            try:
                api.deliver_message(correlation_message_dto=dto)
            except Exception as e:
                logger.warning(e)
        dto = CorrelationMessageDto(
            message_name=message,
            without_tenant_id="true",
            **kwargs,
        )
        try:
            api.deliver_message(correlation_message_dto=dto)
        except Exception as e:
            logger.warning(e)


@implementer(IExecutable)
@adapter(Interface, IBpmMessageAction, Interface)
class BpmMessageActionExecutor:
    """The executor for this action."""

    def __init__(self, context, element, event):
        self.context = context
        self.element = element
        self.event = event

    def __call__(self):
        interpolator = IStringInterpolator(self.event.object)
        name = interpolate(self.element.name, interpolator)
        business_key = interpolate(self.element.businessKey, interpolator)
        correlation_keys = interpolate(self.element.correlationKeys, interpolator)
        payload = interpolate(self.element.payload, interpolator)
        if not plone.api.user.is_anonymous():
            username = plone.api.user.get_current().getUserName()
        else:
            username = None
        tenant_ids = get_tenant_ids()
        join_side_effect(
            _throwMessage,
            args=(name, business_key, correlation_keys, payload, username, tenant_ids),
        )
        return True


class BpmMessageAddForm(ActionAddForm):
    """
    An add form for the BPM Message action
    """

    schema = IBpmMessageAction
    label = _("Add BPM Message Action")
    description = _(
        "A BPM Message action delivers a correlated BPMN message "
        "with interpolated JSON process variables payload, targeting a "
        "single matching process instance rather than broadcasting."
    )
    form_name = _("Configure element")
    Type = BpmMessageAction

    # custom template will allow us to add help text
    template = ViewPageTemplateFile(
        os.path.join("templates", "message.pt"),
    )


class BpmMessageAddFormView(ContentRuleFormWrapper):
    form = BpmMessageAddForm


class BpmMessageEditForm(ActionEditForm):
    """
    An edit form for the BPM Message action
    """

    schema = IBpmMessageAction
    label = _("Edit BPM Message Action")
    description = _(
        "A BPM Message action delivers a correlated BPMN message "
        "with interpolated JSON process variables payload, targeting a "
        "single matching process instance rather than broadcasting."
    )
    form_name = _("Configure element")

    # custom template will allow us to add help text
    template = ViewPageTemplateFile(
        os.path.join("templates", "message.pt"),
    )


class BpmMessageEditFormView(ContentRuleFormWrapper):
    form = BpmMessageEditForm
