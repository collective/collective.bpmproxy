# -*- coding: utf-8 -*-
from plone.app.layout.viewlets import ViewletBase


class BpmAttachmentsViewlet(ViewletBase):
    def update(self):
        pass

    def index(self):
        if self.view.attachments_enabled:
            return super(BpmAttachmentsViewlet, self).render()
        else:
            return u""

    @property
    def attachments_context(self):
        context = self.context.get(self.view.attachments_key)
        return (context and len(context)) and context or None
