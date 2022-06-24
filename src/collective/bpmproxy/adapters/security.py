from borg.localrole.interfaces import ILocalRoleProvider
from collective.bpmproxy.client import camunda_client, get_available_tasks
from collective.bpmproxy.content.bpm_attachments import IBpmAttachments
from collective.bpmproxy.content.bpm_proxy import IBpmProxy
from collective.bpmproxy.utils import parents
from plone.memoize.request import cache
from plone.uuid.interfaces import IUUID
from zope.component import adapter
from zope.interface import implementer

import plone.api


@implementer(ILocalRoleProvider)
@adapter(IBpmAttachments)
class AttachmentsLocalRoleProvider(object):
    def __init__(self, context):
        self.context = context
        self.request = plone.api.portal.getRequest()
        for proxy in parents(self.context, iface=IBpmProxy):
            self.proxy = proxy
            break

    @cache(
        get_key=lambda fun, self, principal_id: IUUID(self.context)
        + ":"
        + principal_id,
        get_request="self.request",
    )
    def getRoles(self, principal_id):
        if not self.proxy or not plone.api.user.get(userid=principal_id):
            return ()  # not a known user
        with camunda_client() as client:
            if get_available_tasks(
                client, context_key=IUUID(self.proxy), attachments_key=self.context.id
            ):
                return "Contributor", "Editor"
        return ()

    def getAllRoles(self):
        # We could check assignees and candidates, but do not want to index them.
        return []
