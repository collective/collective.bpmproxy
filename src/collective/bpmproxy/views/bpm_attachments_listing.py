from plone.app.contentlisting.browser import FolderListing
from plone.app.contentlisting.interfaces import IContentListing
from Products.CMFCore.utils import getToolByName


class AttachmentsListing(FolderListing):
    def __call__(self, batch=False, b_size=20, b_start=0, orphan=0, **kw):
        query = {}
        query.update(kw)

        query["path"] = {
            "query": "/".join(self.context.getPhysicalPath()),
            "depth": 1,
        }

        # if we don't have asked explicitly for other sorting, we'll want
        # it by position in parent
        if "sort_on" not in query:
            query["sort_on"] = "getObjPositionInParent"

        # Provide batching hints to the catalog
        if batch:
            query["b_start"] = b_start
            query["b_size"] = b_size + orphan

        catalog = getToolByName(self.context, "portal_catalog")
        # Unrestricted search, because allowed users and roles depends on process state
        results = catalog.unrestrictedSearchResults(query)

        return IContentListing(results)
