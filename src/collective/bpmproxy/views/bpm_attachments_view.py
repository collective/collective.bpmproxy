from AccessControl.interfaces import IOwned, IRoleManager
from collective.bpmproxy import _
from collective.bpmproxy.client import (
    camunda_client,
    get_available_tasks,
    get_task_variables,
)
from collective.bpmproxy.interfaces import (
    ATTACHMENTS_CONTAINER_TYPE,
    ATTACHMENTS_DEFAULT_TYPE,
    BUSINESS_KEY_VARIABLE_NAME,
)
from generic_camunda_client import ApiException
from plone.dexterity.utils import createContentInContainer
from plone.uuid.interfaces import IUUID
from Products.Five import BrowserView
from uuid import UUID
from zope.i18n import translate
from zope.publisher.interfaces import NotFound


class BpmProxyTaskAttachmentsView(BrowserView):
    def __init__(self, context, request):
        super().__init__(context, request)
        self.context = context.context
        self.task_id = context.task_id

    def __call__(self):
        if not self.context.attachments_enabled:
            return ""

        with camunda_client() as client:
            try:
                # Sanity check that the task exists on this context.
                tasks = get_available_tasks(client, context_key=IUUID(self.context))
                if not len([t for t in tasks if t.id == self.task_id]):
                    raise NotFound(self, self.task_id, self.request)

                # Parse attachments container UUID from injected business key variable
                try:
                    key = get_task_variables(client, self.task_id)[
                        BUSINESS_KEY_VARIABLE_NAME
                    ]
                    if ":" in key:
                        key = str(UUID(key.split(":")[-1]))
                except (KeyError, TypeError, ValueError):
                    raise NotFound(self, self.task_id, self.request)

                tasks = get_available_tasks(
                    client, context_key=IUUID(self.context), attachments_key=key
                )
                if not len([t for t in tasks if t.id == self.task_id]):
                    raise NotFound(self, self.task_id, self.request)

                # Ensure folder
                container = self.context.get(str(key))
                if not container:
                    container = createContentInContainer(
                        self.context,
                        ATTACHMENTS_CONTAINER_TYPE,
                        checkConstraints=False,
                        id=str(key),
                        title=translate(_("Attachments")),
                    )
                    # Remove initial roles from the new container
                    IOwned(container)._deleteOwnershipAfterAdd()
                    roles = dict(IRoleManager(container).get_local_roles())
                    # noinspection PyArgumentList
                    IRoleManager(container).manage_delLocalRoles(roles.keys())
                    container.__ac_local_roles_block__ = True
                    container.reindexObject()
                    # Note: We leave the default Creator, because DX enforces creator.

                self.request.response.redirect(
                    container.absolute_url() + "/++add++" + ATTACHMENTS_DEFAULT_TYPE
                )
            except (ApiException, ValueError):
                raise NotFound(self, self.task_id, self.request)
            finally:
                pass
