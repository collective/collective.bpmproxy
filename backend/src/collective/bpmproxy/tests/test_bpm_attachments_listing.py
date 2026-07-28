from collective.bpmproxy.views.bpm_attachments_listing import AttachmentsListing
from unittest.mock import MagicMock
from unittest.mock import patch
import unittest


class TestAttachmentsListing(unittest.TestCase):
    @patch("collective.bpmproxy.views.bpm_attachments_listing.IContentListing")
    @patch("collective.bpmproxy.views.bpm_attachments_listing.getToolByName")
    def test_call_no_batching(self, mock_getToolByName, mock_IContentListing):
        context = MagicMock()
        context.getPhysicalPath.return_value = ["", "plone", "folder"]

        request = MagicMock()
        view = AttachmentsListing(context, request)

        mock_catalog = MagicMock()
        mock_getToolByName.return_value = mock_catalog
        mock_catalog.unrestrictedSearchResults.return_value = ["result1", "result2"]

        mock_IContentListing.return_value = "content_listing_result"

        result = view()

        self.assertEqual(result, "content_listing_result")

        mock_catalog.unrestrictedSearchResults.assert_called_once_with(
            {
                "path": {"query": "/plone/folder", "depth": 1},
                "sort_on": "getObjPositionInParent",
            }
        )
        mock_IContentListing.assert_called_once_with(["result1", "result2"])

    @patch("collective.bpmproxy.views.bpm_attachments_listing.IContentListing")
    @patch("collective.bpmproxy.views.bpm_attachments_listing.getToolByName")
    def test_call_with_batching_and_kwargs(
        self, mock_getToolByName, mock_IContentListing
    ):
        context = MagicMock()
        context.getPhysicalPath.return_value = ["", "plone", "folder"]

        request = MagicMock()
        view = AttachmentsListing(context, request)

        mock_catalog = MagicMock()
        mock_getToolByName.return_value = mock_catalog

        view(
            batch=True,
            b_size=10,
            b_start=5,
            orphan=2,
            custom_query="foo",
            sort_on="customSort",
        )

        mock_catalog.unrestrictedSearchResults.assert_called_once_with(
            {
                "custom_query": "foo",
                "path": {"query": "/plone/folder", "depth": 1},
                "sort_on": "customSort",
                "b_start": 5,
                "b_size": 12,
            }
        )
