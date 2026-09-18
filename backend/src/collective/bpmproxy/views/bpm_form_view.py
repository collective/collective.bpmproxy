from Acquisition import aq_inner
from collective.bpmproxy import _
from collective.bpmproxy.behaviors.process_context import IProcessContext
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import get_available_tasks
from collective.bpmproxy.client import get_diagram_xml
from collective.bpmproxy.client import get_next_tasks
from collective.bpmproxy.client import get_start_form
from collective.bpmproxy.client import get_task_form
from collective.bpmproxy.client import get_task_variables
from collective.bpmproxy.client import submit_start_form
from collective.bpmproxy.client import submit_task_form
from collective.bpmproxy.content.bpm_proxy import get_process_context
from collective.bpmproxy.content.bpm_proxy import IBpmProxy
from collective.bpmproxy.interfaces import ANONYMOUS_USER_ANNOTATION_KEY
from collective.bpmproxy.interfaces import BUSINESS_KEY_VARIABLE_NAME
from collective.bpmproxy.interfaces import FORM_DATA_KEY
from collective.bpmproxy.interfaces import HTTPMethod
from collective.bpmproxy.interfaces import PLONE_TASK_VIEW
from collective.bpmproxy.interfaces import PloneNotificationLevel
from collective.bpmproxy.utils import prepare_camunda_form
from collective.bpmproxy.utils import validate_camunda_form
from generic_camunda_client.rest import ApiException
from plone.app.caching.operations.utils import doNotCache
from plone.base.interfaces import INavigationRoot
from plone.protect.authenticator import check
from plone.uuid.interfaces import IUUID
from Products.CMFPlone.browser.interfaces import INavigationBreadcrumbs
from Products.CMFPlone.browser.navigation import PhysicalNavigationBreadcrumbs
from Products.Five.browser import BrowserView
from uuid import UUID
from uuid import uuid4
from zope.annotation import IAnnotations
from zope.interface import implementer
from zope.proxy import ProxyBase
from zope.publisher.interfaces import IPublishTraverse
from zope.publisher.interfaces import NotFound
import json
import logging
import plone.api


logger = logging.getLogger(__name__)


@implementer(INavigationBreadcrumbs)
class BpmProxyNavigationBreadcrumbs(PhysicalNavigationBreadcrumbs):
    def breadcrumbs(self):
        # This view is registered for IUUIDAware to allow task breadcrumbs on
        # any content. In Plone 6 the site root is IUUIDAware as well, so this
        # would also override Plone's RootPhysicalNavigationBreadcrumbs and
        # recurse past the portal into the request container. Stop at the
        # navigation root the same way Plone does.
        if INavigationRoot.providedBy(aq_inner(self.context)):
            return ()

        base = super().breadcrumbs()

        task_view = getattr(self.request, "PUBLISHED", None)
        task_id = getattr(task_view, "task_id", None)
        task_title = getattr(task_view, "task_title", None)

        if task_id and task_title:
            return base + (
                {
                    "absolute_url": "/".join(
                        [self.context.absolute_url(), PLONE_TASK_VIEW, task_id]
                    ),
                    "Title": task_title,
                },
            )
        else:
            return base

    def customize_entry(self, entry, context=None):
        """a little helper to enlarge customizability."""
        pass


class BpmProxyStartFormView(BrowserView):
    task_view = PLONE_TASK_VIEW

    def __init__(self, context, request):
        super().__init__(context, request)
        self.process_context = get_process_context(context)

        self.data = "{}"
        self.schema = "{}"
        self.tasks = []
        self.diagram_xml = ""

        self.tabs = False

    def _view(self):
        if not self.process_context.process_definition_key:
            # A process context can exist (and be viewable) before anyone
            # has picked a process definition for it -- e.g. right after
            # creation, or when the field pointed at a definition that
            # hasn't been deployed yet. Every engine call below requires a
            # definition key, so there is nothing more to render.
            plone.api.portal.show_message(
                message=_("This process is not configured yet."),
                request=self.request,
                type=PloneNotificationLevel.ERROR,
            )
            return self.index()

        with camunda_client() as client:
            try:
                # Get diagram
                if self.process_context.diagram_enabled:
                    self.diagram_xml = get_diagram_xml(
                        client,
                        definition_key=self.process_context.process_definition_key,
                    )
                # Get form and data
                if self.process_context.interactive_start_enabled:
                    __, self.data, self.schema = get_start_form(
                        client,
                        self.process_context.process_definition_key,
                        current_values={},
                        default_values=self.process_context.default_values,
                        context=self.context,
                    )
                self.tasks = get_available_tasks(
                    client, context_key=IUUID(self.context), for_display=True
                )
            except ApiException as e:
                # The engine no longer has this process definition or its
                # start form. Deleting a deployment cascades into its
                # instances, so this is what every page configured with that
                # process looks like afterwards -- an ordinary operational
                # state, not a server error.
                logger.warning(
                    "No start form for %s: %s",
                    self.process_context.process_definition_key,
                    e,
                )
                plone.api.portal.show_message(
                    message=_("This process is not available."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                self.data = self.schema = "{}"

        if self.process_context.diagram_enabled or self.tasks:
            self.tabs = True
        return self.index()

    def _submit(self):
        with camunda_client() as client:
            current_values = json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            self.data, __, self.schema = get_start_form(
                client,
                self.process_context.process_definition_key,
                current_values=current_values,
                default_values=self.process_context.default_values,
                context=self.context,
            )
            try:
                # Validate
                validate_camunda_form(self.data, self.schema, self.context)
                # Submit
                business_key = IUUID(self.context) + ":" + uuid4().hex
                process_variables = self.process_context.process_variables.copy()
                process = submit_start_form(
                    client,
                    self.process_context.process_definition_key,
                    business_key=business_key,
                    form_variables=json.loads(self.data),
                    process_variables=process_variables,
                    context=self.context,
                )
                plone.api.portal.show_message(
                    message=_("Submit successful."),
                    request=self.request,
                    type=PloneNotificationLevel.INFO,
                )
                self.tasks = get_available_tasks(
                    client, context_key=IUUID(self.context), for_display=True
                )
                __, self.data, ___ = prepare_camunda_form(
                    self.schema,
                    default_data={},
                    default_values=self.process_context.default_values,
                    context=self.context,
                )

            except ApiException:
                process = None
                plone.api.portal.show_message(
                    message=_("Unexpected error on submit."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                self.data = __
            except AssertionError as e:
                process = None
                plone.api.portal.show_message(
                    message=_("Invalid or missing data."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                logger.error(e)
                self.data = __
            try:
                next_tasks = get_next_tasks(client, process.id) if process else []
                for task in next_tasks:
                    url = "/".join(
                        [self.context.absolute_url(), PLONE_TASK_VIEW, task.id]
                    )
                    token = IAnnotations(self.request).get(
                        ANONYMOUS_USER_ANNOTATION_KEY
                    )
                    if token:
                        url += "?token=" + token
                    if self.process_context.diagram_enabled:
                        url += "#autotoc-item-autotoc-0"
                    self.request.response.redirect(url)
                    break
            except ApiException:
                pass  # process may have already ended

        if self.process_context.diagram_enabled or self.tasks:
            self.tabs = True
        return self.index()

    def __call__(self):
        self.request.set("bpmproxy_form_required", True)
        if self.process_context.diagram_enabled:
            self.request.set("bpmproxy_diagram_required", True)

        doNotCache(self, self.request, self.request.response)
        # A POST to this page is not necessarily this view's own start-form
        # submission -- e.g. a portlet rendered in the same page (the Signal
        # portlet's SignalForm) posts back to this same URL when its own
        # button is clicked. Only FORM_DATA_KEY's presence means this form's
        # own hidden `<form id="collective-bpmproxy-form-submit">` (see
        # bpm_form_view.pt) actually submitted; any other POST falls through
        # to _view(), whose template rendering is what gives portlets their
        # chance to process their own submission via z3c.form's normal
        # button-dispatch in Renderer.render()/form.update().
        if (
            self.request.method == HTTPMethod.POST
            and FORM_DATA_KEY in self.request.form
        ):
            check(self.request)
            return self._submit()
        else:
            return self._view()


class BpmProxy(ProxyBase):
    diagram_enabled = False
    attachments_enabled = False
    default_values = {}
    default_data = {}


@implementer(IPublishTraverse)
class BpmProxyTaskFormView(BrowserView):
    task_view = PLONE_TASK_VIEW

    def __init__(self, context, request):
        super().__init__(context, request)

        if not IBpmProxy.providedBy(self.context) and not IProcessContext.providedBy(
            self.context
        ):
            self.context = BpmProxy(self.context)
        self.process_context = get_process_context(self.context)

        self.attachments_enabled = False
        self.attachments_key = None

        self.data = "{}"
        self.schema = "{}"
        self.tabs = False
        self.task_id = None
        self.task_title = None
        self.task_description = None

    def publishTraverse(self, request, name):
        if self.task_id is None:  # ../task_id
            self.task_id = name
        else:
            raise NotFound(self, name, request)
        return self

    def _view(self, task):
        with camunda_client() as client:
            try:
                # Get data.
                self.task_title = task.name
                self.task_description = task.description
                self.task_definition_key = task.task_definition_key
                current_values = get_task_variables(client, self.task_id)

                # Get diagram
                if self.process_context.diagram_enabled:
                    self.diagram_xml = get_diagram_xml(
                        client, task.process_definition_id, task.tenant_id
                    )

                # Enable attachments when possible.
                try:
                    business_key = current_values[BUSINESS_KEY_VARIABLE_NAME]
                    if ":" in business_key and self.process_context.attachments_enabled:
                        self.attachments_key = str(UUID(business_key.split(":")[-1]))
                        self.attachments_enabled = bool(self.attachments_key)
                except (KeyError, TypeError, ValueError):
                    pass

                __, self.data, self.schema = get_task_form(
                    client,
                    self.task_id,
                    current_values=current_values,
                    default_values=self.process_context.default_values,
                    context=self.context,
                )
            except ApiException as e:
                logger.error("Exception when fetching task for rendering: %s\n", e)
                logger.warning(e)
                raise NotFound(self, self.task_id, self.request) from e

        if self.process_context.diagram_enabled:
            self.tabs = True
        return self.index()

    def _submit(self, task):
        with camunda_client() as client:
            current_values = get_task_variables(client, self.task_id)
            current_values.update(
                json.loads(self.request.form.get(FORM_DATA_KEY) or "{}")
            )

            # Enable attachments when possible.
            try:
                business_key = current_values[BUSINESS_KEY_VARIABLE_NAME]
                if ":" in business_key and self.process_context.attachments_enabled:
                    self.attachments_key = str(UUID(business_key.split(":")[-1]))
                    self.attachments_enabled = bool(self.attachments_key)
            except (KeyError, TypeError, ValueError):
                pass

            self.data, __, self.schema = get_task_form(
                client,
                self.task_id,
                current_values=current_values,
                default_values=self.process_context.default_values,
                context=self.context,
            )
            try:
                validate_camunda_form(self.data, self.schema, self.context)
                submit_task_form(client, self.task_id, json.loads(self.data))
                plone.api.portal.show_message(
                    message=_("Submit successful."),
                    request=self.request,
                    type=PloneNotificationLevel.INFO,
                )
                self.request.response.redirect(self.context.absolute_url())
            except ApiException:
                plone.api.portal.show_message(
                    message=_("Unexpected error on submit."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                self.data = __
            except AssertionError as e:
                plone.api.portal.show_message(
                    message=_("Invalid or missing data."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                logger.error(e)
                self.data = __
            try:
                next_tasks = get_next_tasks(client, task.process_instance_id)
                for task in next_tasks:
                    url = "/".join(
                        [self.context.absolute_url(), PLONE_TASK_VIEW, task.id]
                    )
                    token = IAnnotations(self.request).get(
                        ANONYMOUS_USER_ANNOTATION_KEY
                    )
                    if token:
                        url += "?token=" + token
                    if self.process_context.diagram_enabled:
                        url += "#autotoc-item-autotoc-0"
                    self.request.response.redirect(url)
                    break
            except ApiException:
                pass  # process may have already ended

        if self.process_context.diagram_enabled:
            self.tabs = True
        return self.index()

    def __call__(self):
        self.request.set("bpmproxy_form_required", True)
        if self.process_context.diagram_enabled:
            self.request.set("bpmproxy_diagram_required", True)

        doNotCache(self, self.request, self.request.response)
        with camunda_client() as client:
            try:
                # Sanity check. Task belongs to this context.
                tasks = {
                    task.id: task
                    for task in get_available_tasks(
                        client, context_key=IUUID(self.context)
                    )
                }
                if self.task_id not in tasks:
                    plone.api.portal.show_message(
                        message=_("Task not found or no longer available."),
                        request=self.request,
                        type=PloneNotificationLevel.ERROR,
                    )
                    self.request.response.redirect(self.context.absolute_url())
                    return ""
            except ApiException:
                plone.api.portal.show_message(
                    message=_("Unexpected error."),
                    request=self.request,
                    type=PloneNotificationLevel.ERROR,
                )
                self.request.response.redirect(self.context.absolute_url())
                return ""
        if (
            self.request.method == HTTPMethod.POST
            and FORM_DATA_KEY in self.request.form
        ):
            check(self.request)
            return self._submit(tasks[self.task_id])
        elif tasks[self.task_id].form_key and (
            tasks[self.task_id].form_key.startswith("@@")
            or tasks[self.task_id].form_key.startswith("++")
        ):
            self.request.response.redirect(
                self.context.absolute_url() + "/" + tasks[self.task_id].form_key
            )
            return ""
        else:
            return self._view(tasks[self.task_id])
