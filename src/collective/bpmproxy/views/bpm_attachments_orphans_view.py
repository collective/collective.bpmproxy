# -*- coding: utf-8 -*-
from __future__ import print_function
from collective.bpmproxy.client import camunda_client, get_available_tasks
from collective.bpmproxy.content.bpm_attachments import IBpmAttachments
from collective.bpmproxy.content.bpm_proxy import IBpmProxy
from collective.bpmproxy.interfaces import CAMUNDA_ADMIN_GROUP
from collective.bpmproxy.utils import parents
from plone.uuid.interfaces import IUUID
from Products.Five.browser import BrowserView

import json
import logging
import plone.api


logger = logging.getLogger(__name__)


class BpmAttachmentsOrphansView(BrowserView):
    def __call__(self):
        self.request.response.setHeader("Content-Type", "application/json")

        # Require user with camunda admin group
        group_ids = [
            group.getId()
            for group in plone.api.group.get_groups(user=plone.api.user.get_current())
        ]
        if CAMUNDA_ADMIN_GROUP not in group_ids:
            return json.dumps(list())

        # Filter all attachments without tasks
        pc = plone.api.portal.get_tool("portal_catalog")
        urls = []
        with camunda_client() as client:
            for brain in pc(object_provides=IBpmAttachments.__identifier__):
                ob = brain.getObject()
                for context in parents(ob, iface=IBpmProxy):
                    if not get_available_tasks(
                        client, context_key=IUUID(context), attachments_key=ob.id
                    ):
                        urls.append(ob.absolute_url())
        return json.dumps(urls)
