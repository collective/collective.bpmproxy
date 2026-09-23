from collective.bpmproxy.behaviors.process_context import IProcessContext
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import get_available_tasks
from collective.bpmproxy.content.bpm_attachments import IBpmAttachments
from collective.bpmproxy.interfaces import PLONE_TASK_VIEW
from collective.bpmproxy.utils import parents
from plone.app.layout.viewlets import ViewletBase
from plone.uuid.interfaces import IUUID


class BpmAttachmentsTasksViewlet(ViewletBase):
    task_view = PLONE_TASK_VIEW

    # The template reads both; keep them defined even when no process
    # context is found, so a partial match cannot raise in TAL.
    tasks = ()
    base_url = ""

    def update(self):
        # parents() walks *outwards* from the context, so take the first
        # match: the nearest process context, not the outermost one. This
        # matters now that the process_context behavior can be enabled on
        # any folderish type, making nested process contexts possible.
        for context in parents(self.context, IProcessContext):
            self.base_url = context.absolute_url()
            break

        for context in parents(self.context, iface=IBpmAttachments):
            for proxy in parents(context, iface=IProcessContext):
                with camunda_client() as client:
                    self.tasks = get_available_tasks(
                        client,
                        context_key=IUUID(proxy),
                        attachments_key=context.id,
                        for_display=True,
                    )
                break
            break
