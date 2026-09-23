from collective.bpmproxy.interfaces import FORM_DATA_KEY
from collective.bpmproxy.views.bpm_form_view import BpmProxy
from collective.bpmproxy.views.bpm_form_view import BpmProxyNavigationBreadcrumbs
from collective.bpmproxy.views.bpm_form_view import BpmProxyStartFormView
from collective.bpmproxy.views.bpm_form_view import BpmProxyTaskFormView
from generic_camunda_client.rest import ApiException
from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import patch
from zope.publisher.interfaces import NotFound
import unittest


class TestBpmProxyNavigationBreadcrumbs(unittest.TestCase):
    def test_breadcrumbs_no_task(self):
        context = MagicMock()
        request = MagicMock()
        breadcrumbs = BpmProxyNavigationBreadcrumbs(context, request)
        breadcrumbs.context = context
        breadcrumbs.request = request
        request.PUBLISHED = None

        with patch(
            "Products.CMFPlone.browser.navigation.PhysicalNavigationBreadcrumbs.breadcrumbs",
            return_value=({"Title": "base"},),
        ):
            result = breadcrumbs.breadcrumbs()
            self.assertEqual(result, ({"Title": "base"},))

    def test_breadcrumbs_with_task(self):
        context = MagicMock()
        context.absolute_url.return_value = "http://site"
        request = MagicMock()
        task_view = MagicMock()
        task_view.task_id = "123"
        task_view.task_title = "Task 1"
        request.PUBLISHED = task_view

        breadcrumbs = BpmProxyNavigationBreadcrumbs(context, request)
        breadcrumbs.context = context
        breadcrumbs.request = request

        with patch(
            "Products.CMFPlone.browser.navigation.PhysicalNavigationBreadcrumbs.breadcrumbs",
            return_value=({"Title": "base"},),
        ):
            result = breadcrumbs.breadcrumbs()
            self.assertEqual(
                result,
                (
                    {"Title": "base"},
                    {"absolute_url": "http://site/@@bpm-task/123", "Title": "Task 1"},
                ),
            )

    def test_customize_entry(self):
        breadcrumbs = BpmProxyNavigationBreadcrumbs(MagicMock(), MagicMock())
        breadcrumbs.customize_entry({})


class TestBpmProxyStartFormView(unittest.TestCase):
    def setUp(self):
        anonymous = patch(
            "collective.bpmproxy.views.bpm_form_view.plone.api.user.is_anonymous",
            return_value=False,
        )
        anonymous.start()
        self.addCleanup(anonymous.stop)

        self.context = MagicMock()
        self.context.process_definition_key = "test_process"
        self.context.default_values = {}
        self.context.diagram_enabled = False
        self.context.absolute_url.return_value = "http://site"

        self.request = MagicMock()
        self.request.form = {}
        self.request.method = "GET"

        self.view = BpmProxyStartFormView(self.context, self.request)
        self.view.index = MagicMock(return_value="rendered_html")

        patcher = patch(
            "collective.bpmproxy.views.bpm_form_view.IUUID",
            return_value="12345678-1234-5678-1234-567812345678",
        )
        self.mock_iuuid = patcher.start()
        self.addCleanup(patcher.stop)

        context_filter = patch(
            "collective.bpmproxy.views.bpm_form_view.get_task_context_filter",
            return_value=("12345678-1234-5678-1234-567812345678", False, None),
        )
        context_filter.start()
        self.addCleanup(context_filter.stop)
        context_filter = patch(
            "collective.bpmproxy.views.bpm_form_view.get_task_context_filter",
            return_value=("12345678-1234-5678-1234-567812345678", False, None),
        )
        context_filter.start()
        self.addCleanup(context_filter.stop)

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_diagram_xml")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    def test_view_get_no_diagram(
        self,
        mock_doNotCache,
        mock_get_diagram,
        mock_get_tasks,
        mock_get_form,
        mock_client,
    ):
        mock_get_form.return_value = ('{"foo": "bar"}', "raw_data", "schema")
        mock_get_tasks.return_value = []

        result = self.view()
        self.assertEqual(result, "rendered_html")
        self.assertEqual(self.view.data, "raw_data")
        self.assertEqual(self.view.schema, "schema")
        self.assertEqual(self.view.tasks, [])
        self.assertFalse(self.view.tabs)
        mock_get_diagram.assert_not_called()

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_diagram_xml")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    def test_view_get_with_diagram_and_tasks(
        self,
        mock_doNotCache,
        mock_get_diagram,
        mock_get_tasks,
        mock_get_form,
        mock_client,
    ):
        self.context.diagram_enabled = True
        mock_get_form.return_value = ('{"foo": "bar"}', "raw_data", "schema")
        mock_get_tasks.return_value = ["task1"]
        mock_get_diagram.return_value = "<xml>"

        result = self.view()
        self.assertEqual(result, "rendered_html")
        self.assertEqual(self.view.diagram_xml, "<xml>")
        self.assertTrue(self.view.tabs)

    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.user.is_anonymous")
    @patch("collective.bpmproxy.views.bpm_form_view.get_diagram_xml")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    def test_view_get_hides_diagram_for_anonymous_user(
        self,
        mock_doNotCache,
        mock_client,
        mock_get_form,
        mock_get_tasks,
        mock_get_diagram,
        mock_is_anonymous,
    ):
        self.context.diagram_enabled = True
        mock_is_anonymous.return_value = True
        mock_get_form.return_value = ("{}", "{}", "{}")
        mock_get_tasks.return_value = []

        self.view()

        mock_get_diagram.assert_not_called()
        self.assertFalse(
            any(
                call.args[0] == "bpmproxy_diagram_required"
                for call in self.request.set.call_args_list
            )
        )

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.validate_camunda_form")
    @patch("collective.bpmproxy.views.bpm_form_view.submit_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_next_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.IAnnotations")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    @patch("collective.bpmproxy.views.bpm_form_view.check")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.uuid4")
    @patch("collective.bpmproxy.views.bpm_form_view.prepare_camunda_form")
    def test_view_post_success(
        self,
        mock_prepare,
        mock_uuid4,
        mock_doNotCache,
        mock_check,
        mock_show_message,
        mock_ianno,
        mock_get_next_tasks,
        mock_submit,
        mock_validate,
        mock_get_tasks,
        mock_get_form,
        mock_client,
    ):
        self.request.method = "POST"
        self.request.form = {FORM_DATA_KEY: '{"foo": "bar"}'}
        self.context.process_variables = {"var1": "val1"}
        self.context.diagram_enabled = True

        mock_get_form.return_value = ('{"foo": "bar"}', "raw_data", "schema")
        self.mock_iuuid.return_value = "12345678-1234-5678-1234-567812345678"
        mock_uuid4.return_value.hex = "12345678123456781234567812345678"
        mock_process = MagicMock()
        mock_process.id = "process-1"
        mock_submit.return_value = mock_process
        mock_get_tasks.return_value = []
        mock_prepare.return_value = (None, "{}", None)

        mock_next_task = MagicMock()
        mock_next_task.id = "task-2"
        mock_get_next_tasks.return_value = [mock_next_task]

        mock_ianno.return_value.get.return_value = "some-token"

        self.view()

        mock_submit.assert_called_once_with(
            ANY,
            "test_process",
            business_key="12345678-1234-5678-1234-567812345678:12345678123456781234567812345678",
            form_variables={"foo": "bar"},
            process_variables={"var1": "val1"},
            context=self.context,
        )
        self.request.response.redirect.assert_called_once_with(
            "http://site/@@bpm-task/task-2?token=some-token#autotoc-item-autotoc-0"
        )
        mock_show_message.assert_called_once()
        self.assertTrue(self.view.tabs)

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.validate_camunda_form")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    @patch("collective.bpmproxy.views.bpm_form_view.check")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    def test_view_post_validation_error(
        self,
        mock_doNotCache,
        mock_check,
        mock_show_message,
        mock_validate,
        mock_get_form,
        mock_client,
    ):
        self.request.method = "POST"
        self.request.form = {FORM_DATA_KEY: '{"foo": "bar"}'}
        mock_get_form.return_value = ('{"foo": "bar"}', "raw_data", "schema")
        mock_validate.side_effect = AssertionError("Invalid data")

        result = self.view()
        self.assertEqual(result, "rendered_html")
        mock_show_message.assert_called_once()
        self.assertEqual(self.view.data, "raw_data")

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.validate_camunda_form")
    @patch("collective.bpmproxy.views.bpm_form_view.submit_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    @patch("collective.bpmproxy.views.bpm_form_view.check")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.uuid4")
    def test_view_post_api_error(
        self,
        mock_uuid4,
        mock_doNotCache,
        mock_check,
        mock_show_message,
        mock_submit,
        mock_validate,
        mock_get_form,
        mock_client,
    ):
        self.request.method = "POST"
        self.request.form = {FORM_DATA_KEY: '{"foo": "bar"}'}
        self.context.process_variables = {}
        self.mock_iuuid.return_value = "12345678-1234-5678-1234-567812345678"
        mock_uuid4.return_value.hex = "12345678123456781234567812345678"
        mock_get_form.return_value = ('{"foo": "bar"}', "raw_data", "schema")
        mock_submit.side_effect = ApiException()

        result = self.view()
        self.assertEqual(result, "rendered_html")
        mock_show_message.assert_called_once()
        self.assertEqual(self.view.data, "raw_data")

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.validate_camunda_form")
    @patch("collective.bpmproxy.views.bpm_form_view.submit_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_next_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.IAnnotations")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    @patch("collective.bpmproxy.views.bpm_form_view.check")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.uuid4")
    @patch("collective.bpmproxy.views.bpm_form_view.prepare_camunda_form")
    def test_view_post_api_error_on_next_tasks(
        self,
        mock_prepare,
        mock_uuid4,
        mock_doNotCache,
        mock_check,
        mock_show_message,
        mock_ianno,
        mock_get_next_tasks,
        mock_submit,
        mock_validate,
        mock_get_tasks,
        mock_get_form,
        mock_client,
    ):
        self.request.method = "POST"
        self.context.process_variables = {}
        self.mock_iuuid.return_value = "12345678-1234-5678-1234-567812345678"
        mock_uuid4.return_value.hex = "12345678123456781234567812345678"
        mock_get_form.return_value = ('{"foo": "bar"}', "raw_data", "schema")
        mock_process = MagicMock()
        mock_submit.return_value = mock_process
        mock_get_next_tasks.side_effect = ApiException()
        mock_prepare.return_value = (None, "{}", None)

        result = self.view()
        self.assertEqual(result, "rendered_html")


class TestBpmProxyTaskFormView(unittest.TestCase):
    def setUp(self):
        anonymous = patch(
            "collective.bpmproxy.views.bpm_form_view.plone.api.user.is_anonymous",
            return_value=False,
        )
        anonymous.start()
        self.addCleanup(anonymous.stop)

        self.context = MagicMock()
        self.context.default_values = {}
        self.context.diagram_enabled = False
        self.context.absolute_url.return_value = "http://site"
        self.context.attachments_enabled = True

        self.request = MagicMock()
        self.request.form = {}
        self.request.method = "GET"

        with patch(
            "collective.bpmproxy.views.bpm_form_view.IBpmProxy.providedBy",
            return_value=True,
        ):
            self.view = BpmProxyTaskFormView(self.context, self.request)
        self.view.index = MagicMock(return_value="rendered_html")
        self.view.task_id = "task-1"

        patcher = patch(
            "collective.bpmproxy.views.bpm_form_view.IUUID",
            return_value="12345678-1234-5678-1234-567812345678",
        )
        self.mock_iuuid = patcher.start()
        self.addCleanup(patcher.stop)

        context_filter = patch(
            "collective.bpmproxy.views.bpm_form_view.get_task_context_filter",
            return_value=("12345678-1234-5678-1234-567812345678", False, None),
        )
        context_filter.start()
        self.addCleanup(context_filter.stop)

    def test_init_without_ibpmproxy(self):
        with patch(
            "collective.bpmproxy.views.bpm_form_view.IBpmProxy.providedBy",
            return_value=False,
        ):
            view = BpmProxyTaskFormView(self.context, self.request)
            self.assertTrue(isinstance(view.context, BpmProxy))

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_variables")
    @patch("collective.bpmproxy.views.bpm_form_view.get_diagram_xml")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    def test_view_get_invalid_business_key(
        self,
        mock_doNotCache,
        mock_get_form,
        mock_diagram,
        mock_get_vars,
        mock_get_tasks,
        mock_client,
    ):
        task = MagicMock()
        task.id = "task-1"
        task.form_key = None
        mock_get_tasks.return_value = [task]
        mock_get_vars.return_value = {}
        mock_get_form.return_value = (None, "data", "schema")
        self.context.diagram_enabled = False
        self.view()

    def test_publishTraverse(self):
        self.view.task_id = None
        result = self.view.publishTraverse(self.request, "task-2")
        self.assertEqual(result, self.view)
        self.assertEqual(self.view.task_id, "task-2")

        with self.assertRaises(NotFound):
            self.view.publishTraverse(self.request, "extra-segment")

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    def test_call_task_not_found(
        self, mock_msg, mock_doNotCache, mock_get_tasks, mock_client
    ):
        mock_get_tasks.return_value = []
        result = self.view()
        self.assertEqual(result, "")
        self.request.response.redirect.assert_called_once_with("http://site")

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    def test_call_api_error_on_sanity_check(
        self, mock_msg, mock_doNotCache, mock_get_tasks, mock_client
    ):
        mock_get_tasks.side_effect = ApiException()
        result = self.view()
        self.assertEqual(result, "")
        self.request.response.redirect.assert_called_once_with("http://site")

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    def test_call_redirect_form_key(self, mock_doNotCache, mock_get_tasks, mock_client):
        task = MagicMock()
        task.id = "task-1"
        task.form_key = "@@custom-form"
        mock_get_tasks.return_value = [task]

        result = self.view()
        self.assertEqual(result, "")
        self.request.response.redirect.assert_called_once_with(
            "http://site/@@custom-form"
        )

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_variables")
    @patch("collective.bpmproxy.views.bpm_form_view.get_diagram_xml")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    def test_view_get_success(
        self,
        mock_doNotCache,
        mock_get_form,
        mock_diagram,
        mock_get_vars,
        mock_get_tasks,
        mock_client,
    ):
        task = MagicMock()
        task.id = "task-1"
        task.form_key = None
        task.name = "Task Name"
        task.description = "Desc"
        task.process_definition_id = "proc-def-1"
        task.tenant_id = "tenant-1"
        mock_get_tasks.return_value = [task]

        mock_get_vars.return_value = {
            "businessKey": "uuid:12345678-1234-5678-1234-567812345678",
            "childUrl": "http://site/case/page",
        }
        mock_get_form.return_value = (None, "data", "schema")

        self.context.diagram_enabled = True

        result = self.view()
        self.assertEqual(result, "rendered_html")
        self.assertEqual(self.view.task_title, "Task Name")
        self.assertTrue(self.view.attachments_enabled)
        self.assertEqual(
            self.view.attachments_key, "12345678-1234-5678-1234-567812345678"
        )
        self.assertEqual(self.view.review_content_url, "http://site/case/page")
        self.assertTrue(self.view.tabs)
        mock_diagram.assert_called_once_with(ANY, "proc-def-1", "tenant-1")

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_variables")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    def test_view_get_api_error_on_vars(
        self, mock_doNotCache, mock_get_vars, mock_get_tasks, mock_client
    ):
        task = MagicMock()
        task.id = "task-1"
        task.form_key = None
        mock_get_tasks.return_value = [task]
        mock_get_vars.side_effect = ApiException()

        with self.assertRaises(NotFound):
            self.view()

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_variables")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.validate_camunda_form")
    @patch("collective.bpmproxy.views.bpm_form_view.submit_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_next_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.check")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    @patch("collective.bpmproxy.views.bpm_form_view.IAnnotations")
    def test_view_post_success(
        self,
        mock_ianno,
        mock_msg,
        mock_doNotCache,
        mock_check,
        mock_next,
        mock_submit,
        mock_validate,
        mock_get_form,
        mock_get_vars,
        mock_get_tasks,
        mock_client,
    ):
        self.request.method = "POST"
        self.request.form = {FORM_DATA_KEY: '{"foo": "bar"}'}
        self.context.diagram_enabled = True

        task = MagicMock()
        task.id = "task-1"
        task.form_key = None
        mock_get_tasks.return_value = [task]

        mock_get_vars.return_value = {
            "businessKey": "uuid:12345678-1234-5678-1234-567812345678"
        }
        mock_get_form.return_value = ('{"foo": "bar"}', "raw", "schema")

        mock_next_task = MagicMock()
        mock_next_task.id = "task-2"
        mock_next.return_value = [mock_next_task]
        mock_ianno.return_value.get.return_value = "some-token"

        self.view()

        mock_submit.assert_called_once_with(ANY, "task-1", {"foo": "bar"})
        self.request.response.redirect.assert_called_with(
            "http://site/@@bpm-task/task-2?token=some-token#autotoc-item-autotoc-0"
        )

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_variables")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.validate_camunda_form")
    @patch("collective.bpmproxy.views.bpm_form_view.check")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    def test_view_post_validation_error(
        self,
        mock_msg,
        mock_doNotCache,
        mock_check,
        mock_validate,
        mock_get_form,
        mock_get_vars,
        mock_get_tasks,
        mock_client,
    ):
        self.request.method = "POST"
        self.request.form = {FORM_DATA_KEY: '{"foo": "bar"}'}

        task = MagicMock()
        task.id = "task-1"
        task.form_key = None
        mock_get_tasks.return_value = [task]

        mock_get_vars.return_value = {}
        mock_get_form.return_value = ('{"foo": "bar"}', "raw", "schema")
        mock_validate.side_effect = AssertionError("Invalid")

        result = self.view()
        self.assertEqual(result, "rendered_html")
        mock_msg.assert_called_once()
        self.assertEqual(self.view.data, "raw")

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_variables")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.validate_camunda_form")
    @patch("collective.bpmproxy.views.bpm_form_view.submit_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.check")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    def test_view_post_api_error(
        self,
        mock_msg,
        mock_doNotCache,
        mock_check,
        mock_submit,
        mock_validate,
        mock_get_form,
        mock_get_vars,
        mock_get_tasks,
        mock_client,
    ):
        self.request.method = "POST"
        self.request.form = {FORM_DATA_KEY: '{"foo": "bar"}'}

        task = MagicMock()
        task.id = "task-1"
        task.form_key = None
        mock_get_tasks.return_value = [task]

        mock_get_vars.return_value = {}
        mock_get_form.return_value = ('{"foo": "bar"}', "raw", "schema")
        mock_submit.side_effect = ApiException()

        result = self.view()
        self.assertEqual(result, "rendered_html")
        mock_msg.assert_called_once()
        self.assertEqual(self.view.data, "raw")

    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_variables")
    @patch("collective.bpmproxy.views.bpm_form_view.get_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.validate_camunda_form")
    @patch("collective.bpmproxy.views.bpm_form_view.submit_task_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_next_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.check")
    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    @patch("collective.bpmproxy.views.bpm_form_view.IAnnotations")
    def test_view_post_api_error_on_next_tasks(
        self,
        mock_ianno,
        mock_msg,
        mock_doNotCache,
        mock_check,
        mock_next,
        mock_submit,
        mock_validate,
        mock_get_form,
        mock_get_vars,
        mock_get_tasks,
        mock_client,
    ):
        self.request.method = "POST"
        self.request.form = {FORM_DATA_KEY: '{"foo": "bar"}'}
        self.context.diagram_enabled = True

        task = MagicMock()
        task.id = "task-1"
        task.form_key = None
        mock_get_tasks.return_value = [task]

        mock_get_vars.return_value = {
            "businessKey": "uuid:12345678-1234-5678-1234-567812345678"
        }
        mock_get_form.return_value = ('{"foo": "bar"}', "raw", "schema")

        mock_next.side_effect = ApiException()

        result = self.view()
        self.assertEqual(result, "rendered_html")


class TestBpmProxyAdapter(unittest.TestCase):
    def test_bpm_proxy_adapter(self):
        context = MagicMock()
        proxy = BpmProxy(context)
        self.assertFalse(proxy.diagram_enabled)
        self.assertFalse(proxy.attachments_enabled)
        self.assertEqual(proxy.default_values, {})
        self.assertEqual(proxy.default_data, {})


class BpmProxyStartFormViewMissingProcessTest(unittest.TestCase):
    """The start form view when the engine no longer has the process.

    Deleting a deployment from the control panel cascades into its instances,
    so every page configured with that process definition ends up here. It has
    to render a message, not a traceback.
    """

    def setUp(self):
        anonymous = patch(
            "collective.bpmproxy.views.bpm_form_view.plone.api.user.is_anonymous",
            return_value=False,
        )
        anonymous.start()
        self.addCleanup(anonymous.stop)

        self.context = MagicMock()
        self.context.process_definition_key = "gone-from-the-engine"
        self.context.default_values = {}
        self.context.diagram_enabled = True
        self.context.absolute_url.return_value = "http://site"

        self.request = MagicMock()
        self.request.form = {}
        self.request.method = "GET"

        self.view = BpmProxyStartFormView(self.context, self.request)
        self.view.index = MagicMock(return_value="rendered_html")

        patcher = patch(
            "collective.bpmproxy.views.bpm_form_view.IUUID",
            return_value="12345678-1234-5678-1234-567812345678",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_diagram_xml")
    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    def test_missing_definition_renders_a_message(
        self,
        mock_client,
        mock_diagram,
        mock_start_form,
        mock_show_message,
        mock_do_not_cache,
    ):
        mock_diagram.side_effect = ApiException(status=404)

        # Must not raise: before this was handled, the 404 propagated and the
        # page answered with a Zope traceback.
        self.assertEqual(self.view(), "rendered_html")

        self.assertEqual(self.view.data, "{}")
        self.assertEqual(self.view.schema, "{}")
        # The template reads diagram_xml whenever diagrams are enabled, so it
        # must survive a failed fetch.
        self.assertEqual(self.view.diagram_xml, "")
        mock_start_form.assert_not_called()
        mock_show_message.assert_called_once()


class BpmProxyStartFormViewNoInteractiveStartTest(unittest.TestCase):
    """The start form view for a process opted out of interactive start.

    A signal-started process has no deployed start form -- get_start_form
    would always 404 for it. Setting
    interactive_start_enabled = False must skip that call entirely, so the
    page renders normally with no error banner (the diagram and task list
    still come from their own, independent calls).
    """

    def setUp(self):
        anonymous = patch(
            "collective.bpmproxy.views.bpm_form_view.plone.api.user.is_anonymous",
            return_value=False,
        )
        anonymous.start()
        self.addCleanup(anonymous.stop)

        self.context = MagicMock()
        self.context.process_definition_key = "signal-started-process"
        self.context.default_values = {}
        self.context.diagram_enabled = True
        self.context.interactive_start_enabled = False
        self.context.absolute_url.return_value = "http://site"

        self.request = MagicMock()
        self.request.form = {}
        self.request.method = "GET"

        self.view = BpmProxyStartFormView(self.context, self.request)
        self.view.index = MagicMock(return_value="rendered_html")

        patcher = patch(
            "collective.bpmproxy.views.bpm_form_view.IUUID",
            return_value="12345678-1234-5678-1234-567812345678",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch("collective.bpmproxy.views.bpm_form_view.doNotCache")
    @patch("collective.bpmproxy.views.bpm_form_view.plone.api.portal.show_message")
    @patch("collective.bpmproxy.views.bpm_form_view.get_start_form")
    @patch("collective.bpmproxy.views.bpm_form_view.get_available_tasks")
    @patch("collective.bpmproxy.views.bpm_form_view.get_diagram_xml")
    @patch("collective.bpmproxy.views.bpm_form_view.camunda_client")
    def test_start_form_is_never_fetched_and_no_error_shown(
        self,
        mock_client,
        mock_diagram,
        mock_get_tasks,
        mock_start_form,
        mock_show_message,
        mock_do_not_cache,
    ):
        mock_diagram.return_value = "<xml>"
        mock_get_tasks.return_value = ["task1"]

        self.assertEqual(self.view(), "rendered_html")

        mock_start_form.assert_not_called()
        mock_show_message.assert_not_called()
        self.assertEqual(self.view.data, "{}")
        self.assertEqual(self.view.schema, "{}")
        self.assertEqual(self.view.diagram_xml, "<xml>")
        self.assertEqual(self.view.tasks, ["task1"])
        self.assertTrue(self.view.tabs)
