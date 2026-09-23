from collective.bpmproxy.adapters.substitutions import CameFromSubstitution
from collective.bpmproxy.adapters.substitutions import ParentUUIDSubstitution
from collective.bpmproxy.adapters.substitutions import UUIDSubstitution
from unittest.mock import MagicMock
from unittest.mock import patch
import unittest


class TestSubstitutions(unittest.TestCase):
    def test_uuid_substitution(self):
        context = MagicMock()
        with patch(
            "collective.bpmproxy.adapters.substitutions.IUUID", return_value="my-uuid"
        ):
            sub = UUIDSubstitution(context)
            self.assertEqual(sub.safe_call(), "my-uuid")

    def test_parent_uuid_substitution_with_parent(self):
        context = MagicMock()
        parent = MagicMock()
        with (
            patch(
                "collective.bpmproxy.adapters.substitutions.parents",
                return_value=[parent],
            ),
            patch(
                "collective.bpmproxy.adapters.substitutions.IUUID",
                return_value="parent-uuid",
            ),
        ):
            sub = ParentUUIDSubstitution(context)
            self.assertEqual(sub.safe_call(), "parent-uuid")

    def test_parent_uuid_substitution_no_parent(self):
        context = MagicMock()
        with patch(
            "collective.bpmproxy.adapters.substitutions.parents", return_value=[]
        ):
            sub = ParentUUIDSubstitution(context)
            self.assertIsNone(sub.safe_call())

    def test_came_from_substitution_valid(self):
        context = MagicMock()
        request = MagicMock()
        request.form = {"came_from": "http://portal/path"}

        portal = MagicMock()
        portal.absolute_url.return_value = "http://portal"

        with (
            patch("plone.api.portal.getRequest", return_value=request),
            patch("plone.api.portal.get", return_value=portal),
        ):
            sub = CameFromSubstitution(context)
            self.assertEqual(sub.safe_call(), "http://portal/path")

    def test_came_from_substitution_invalid(self):
        context = MagicMock()
        request = MagicMock()
        request.form = {"came_from": "http://other/path"}

        portal = MagicMock()
        portal.absolute_url.return_value = "http://portal"

        with (
            patch("plone.api.portal.getRequest", return_value=request),
            patch("plone.api.portal.get", return_value=portal),
        ):
            sub = CameFromSubstitution(context)
            self.assertEqual(sub.safe_call(), "")

    def test_came_from_substitution_none(self):
        context = MagicMock()
        request = MagicMock()
        request.form = {}

        portal = MagicMock()
        portal.absolute_url.return_value = "http://portal"

        with (
            patch("plone.api.portal.getRequest", return_value=request),
            patch("plone.api.portal.get", return_value=portal),
        ):
            sub = CameFromSubstitution(context)
            self.assertEqual(sub.safe_call(), "")
