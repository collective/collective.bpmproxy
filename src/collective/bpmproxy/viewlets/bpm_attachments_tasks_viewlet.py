# -*- coding: utf-8 -*-
from Acquisition import aq_parent
from collective.bpmproxy.client import camunda_client, get_available_tasks
from collective.bpmproxy.content.bpm_attachments import IBpmAttachments
from collective.bpmproxy.content.bpm_proxy import IBpmProxy
from collective.bpmproxy.utils import parents
from plone.app.layout.viewlets import ViewletBase
from plone.uuid.interfaces import IUUID


class BpmAttachmentsTasksViewlet(ViewletBase):
    def update(self):
        for context in parents(self.context, IBpmProxy):
            self.base_url = context.absolute_url()

        for context in parents(self.context, iface=IBpmAttachments):
            for proxy in parents(context, iface=IBpmProxy):
                with camunda_client() as client:
                    self.tasks = get_available_tasks(
                        client, context_key=IUUID(proxy), attachments_key=context.id
                    )
                    break
