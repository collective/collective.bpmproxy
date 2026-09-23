from Acquisition import aq_inner
from collective.bpmproxy import _
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import get_available_tasks
from collective.bpmproxy.client import get_task_variables
from collective.bpmproxy.interfaces import PLONE_TASK_VIEW
from collective.bpmproxy.utils import get_task_context_filter
from collective.bpmproxy.utils import is_review_state_allowed
from collective.bpmproxy.utils import is_valid_uuid
from generic_camunda_client.rest import ApiException
from plone.app.portlets.portlets import base
from plone.memoize.instance import memoize
from plone.portlets.interfaces import IPortletDataProvider
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from z3c.form import field
from zope import schema
from zope.component import getMultiAdapter
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse
from zope.publisher.interfaces import NotFound
import plone.api


class ITasksPortlet(IPortletDataProvider):
    header = schema.TextLine(
        title=_("Portlet header"),
        description=_("Title of the rendered portlet"),
        required=False,
    )

    use_context = schema.Bool(
        title=_("Show only tasks for the current context"),
        required=False,
        default=True,
    )

    process_definition_key = schema.Choice(
        title=_("Show only tasks for a single process type"),
        required=False,
        vocabulary="collective.bpmproxy.AvailableProcessDefinitions",
    )

    review_states = schema.List(
        title=_("Display for review states"),
        description=_("Leave empty to display for all review states."),
        value_type=schema.Choice(vocabulary="plone.app.vocabularies.WorkflowStates"),
        required=False,
        missing_value=[],
        defaultFactory=list,
    )


@implementer(ITasksPortlet)
class Assignment(base.Assignment):
    schema = ITasksPortlet
    header = None
    use_context = False
    process_definition_key = None
    review_states = []

    def __init__(
        self,
        header=None,
        use_context=False,
        process_definition_key=None,
        review_states=None,
    ):
        self.header = header
        self.use_context = use_context
        self.process_definition_key = process_definition_key
        self.review_states = review_states or []

    @property
    def title(self):
        return _("Task list")


class AddForm(base.AddForm):
    schema = ITasksPortlet
    form_fields = field.Fields(ITasksPortlet)
    label = _("Add Task list")
    description = _("This portlet displays available pending BPM tasks.")

    def create(self, data):
        return Assignment(
            header=data["header"],
            use_context=data["use_context"],
            process_definition_key=data["process_definition_key"],
            review_states=data.get("review_states", []),
        )


class EditForm(base.EditForm):
    schema = ITasksPortlet
    form_fields = field.Fields(ITasksPortlet)
    label = _("Edit Task list")
    description = _("This portlet displays available pending BPM tasks.")


class Renderer(base.Renderer):
    schema = ITasksPortlet
    _template = ViewPageTemplateFile("tasks.pt")

    def __init__(self, *args):
        base.Renderer.__init__(self, *args)
        context = aq_inner(self.context)
        portal_state = getMultiAdapter(
            (context, self.request), name="plone_portal_state"
        )
        self.anonymous = portal_state.anonymous()
        self.base_url = (
            plone.api.portal.get().absolute_url() + "/@@redirect-to-bpm-task"
        )

    def render(self):
        return self._template()

    @property
    def available(self):
        """Show the portlet only if there are one or more elements."""
        return (
            not self.anonymous
            and is_review_state_allowed(self.context, self.data.review_states)
            and bool(self._data())
        )

    def tasks(self):
        return self._data()

    @memoize
    def _data(self):
        with camunda_client() as client:
            if not self.data.use_context:
                return get_available_tasks(
                    client,
                    for_display=True,
                    process_definition_key=self.data.process_definition_key,
                )

            context_key, nested_context, parent_context_key = get_task_context_filter(
                self.context
            )

            return get_available_tasks(
                client,
                context_key=context_key,
                nested_context=nested_context,
                parent_context_key=parent_context_key,
                for_display=True,
                process_definition_key=self.data.process_definition_key,
            )


@implementer(IPublishTraverse)
class RedirectView(BrowserView):
    task_view = PLONE_TASK_VIEW

    def __init__(self, context, request):
        super().__init__(context, request)
        self.task_id = None

    def publishTraverse(self, request, name):
        if self.task_id is None:  # ../task_id
            self.task_id = name
        else:
            raise NotFound(self, name, request)
        return self

    def __call__(self):
        with camunda_client() as client:
            try:
                variables = get_task_variables(client, self.task_id)
            except ApiException:
                # The engine has no such task. Portlet links go stale as soon
                # as somebody else completes the task, so this is an ordinary
                # 404, not a server error.
                raise NotFound(self, self.task_id, self.request) from None
        if not variables or "businessKey" not in variables:
            raise NotFound(self, self.task_id, self.request)
        business_key_parts = variables["businessKey"].split(":")
        uuid = (
            business_key_parts[1]
            if len(business_key_parts) >= 3
            else business_key_parts[0]
        )
        if not is_valid_uuid(uuid):
            raise NotFound(self, self.task_id, self.request)
        url = (
            plone.api.portal.get().absolute_url()
            + "/resolveuid/"
            + uuid
            + "/"
            + PLONE_TASK_VIEW
            + "/"
            + self.task_id
        )
        self.request.response.redirect(url)
        return ""
