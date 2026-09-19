from collective.bpmproxy.portlets.tasks import AddForm
from collective.bpmproxy.portlets.tasks import Assignment
from collective.bpmproxy.portlets.tasks import EditForm
from collective.bpmproxy.portlets.tasks import RedirectView
from collective.bpmproxy.portlets.tasks import Renderer
from unittest import mock
from zope.publisher.browser import TestRequest
from zope.publisher.interfaces import NotFound
import pytest


def test_assignment():
    assignment = Assignment(
        header="Header", use_context=True, process_definition_key="key"
    )
    assert assignment.header == "Header"
    assert assignment.use_context is True
    assert assignment.process_definition_key == "key"
    assert assignment.title == "Task list"


def test_add_form():
    form = AddForm(mock.Mock(), mock.Mock())
    assignment = form.create(
        {"header": "H", "use_context": True, "process_definition_key": "K"}
    )
    assert isinstance(assignment, Assignment)
    assert assignment.header == "H"


def test_edit_form():
    form = EditForm(mock.Mock(), mock.Mock())
    assert form.label == "Edit Task list"


def test_renderer():
    context = mock.Mock()
    request = TestRequest()
    assignment = Assignment(header="H", use_context=True, process_definition_key="key")

    with (
        mock.patch("collective.bpmproxy.portlets.tasks.getMultiAdapter") as gma,
        mock.patch(
            "collective.bpmproxy.portlets.tasks.plone.api.portal.get"
        ) as get_portal_mock,
        mock.patch("collective.bpmproxy.portlets.tasks.camunda_client"),
        mock.patch(
            "collective.bpmproxy.portlets.tasks.get_available_tasks"
        ) as get_tasks_mock,
        mock.patch("collective.bpmproxy.portlets.tasks.IUUID"),
    ):
        portal_state_mock = mock.Mock()
        portal_state_mock.anonymous.return_value = False
        gma.return_value = portal_state_mock
        get_portal_mock().absolute_url.return_value = "http://127.0.0.1"

        task1 = mock.Mock()
        task1.process_definition_id = "key:1:123"

        # Filtering by process_definition_key is now the engine's job (see
        # test_client_more.py for that), not this portlet's -- it just has
        # to pass the value through.
        get_tasks_mock.return_value = [task1]

        renderer = Renderer(context, request, mock.Mock(), mock.Mock(), assignment)

        # memoize wrapper means we call _data directly or access it through tasks()
        tasks = renderer.tasks()
        assert tasks == [task1]
        get_tasks_mock.assert_called_once_with(
            mock.ANY,
            context_key=mock.ANY,
            for_display=True,
            process_definition_key="key",
        )

        assert renderer.available is True

        # render uses a template, mock _template
        renderer._template = mock.Mock(return_value="template-output")
        assert renderer.render() == "template-output"

        # test with no process definition key filter
        assignment2 = Assignment(
            header="H", use_context=False, process_definition_key=None
        )
        renderer2 = Renderer(context, request, mock.Mock(), mock.Mock(), assignment2)
        tasks2 = renderer2.tasks()
        assert tasks2 == [task1]
        get_tasks_mock.assert_called_with(
            mock.ANY,
            context_key=mock.ANY,
            for_display=True,
            process_definition_key=None,
        )


def test_redirect_view():
    context = mock.Mock()
    request = TestRequest()
    view = RedirectView(context, request)

    view.publishTraverse(request, "task-123")
    assert view.task_id == "task-123"

    with pytest.raises(NotFound):
        view.publishTraverse(request, "extra")

    with (
        mock.patch("collective.bpmproxy.portlets.tasks.camunda_client"),
        mock.patch(
            "collective.bpmproxy.portlets.tasks.get_task_variables"
        ) as get_vars_mock,
        mock.patch(
            "collective.bpmproxy.portlets.tasks.plone.api.portal.get"
        ) as get_portal_mock,
    ):
        get_portal_mock().absolute_url.return_value = "http://127.0.0.1"

        # Test 1: no variables
        get_vars_mock.return_value = None
        with pytest.raises(NotFound):
            view()

        # Test 2: no businessKey
        get_vars_mock.return_value = {"other": "val"}
        with pytest.raises(NotFound):
            view()

        # Test 3: invalid uuid
        get_vars_mock.return_value = {"businessKey": "not-a-uuid:123"}
        with pytest.raises(NotFound):
            view()

        # Test 4: valid
        import uuid

        valid_uuid = str(uuid.uuid4())
        get_vars_mock.return_value = {"businessKey": f"{valid_uuid}:123"}

        res = view()
        assert res == ""
        assert request.response.getStatus() in (302, 303)
        assert (
            request.response.getHeader("Location")
            == f"http://127.0.0.1/resolveuid/{valid_uuid}/@@bpm-task/task-123"
        )
