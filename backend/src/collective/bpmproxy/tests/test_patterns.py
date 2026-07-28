from collective.bpmproxy.adapters.patterns import PatternsSettings
import unittest


class TestPatternsSettings(unittest.TestCase):
    def test_patterns_settings(self):
        adapter = PatternsSettings("context", "request", "field")
        self.assertEqual(adapter.context, "context")
        self.assertEqual(adapter.request, "request")
        self.assertEqual(adapter.field, "field")

        result = adapter()
        self.assertEqual(
            result, {"data-pat-code-editor": "language: js; theme: tomorrow;"}
        )
