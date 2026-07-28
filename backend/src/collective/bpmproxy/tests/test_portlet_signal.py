from collective.bpmproxy.portlets.signal import AddForm
from collective.bpmproxy.portlets.signal import Assignment
from collective.bpmproxy.portlets.signal import EditForm
from collective.bpmproxy.portlets.signal import Renderer
from collective.bpmproxy.portlets.signal import SignalForm
from unittest import mock
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.interface import directlyProvides
from zope.publisher.browser import TestRequest


def test_signal_form_dispatch():
    context = mock.Mock()
    request = TestRequest()
    directlyProvides(request, IAttributeAnnotatable)
    form = SignalForm(context, request, "prefix.", "My Button", "signal_name", "{}")

    with (
        mock.patch(
            "collective.bpmproxy.portlets.signal.IStringInterpolator"
        ) as interpolator_mock,
        mock.patch(
            "collective.bpmproxy.portlets.signal.plone.api.user.is_anonymous"
        ) as is_anonymous_mock,
        mock.patch(
            "collective.bpmproxy.portlets.signal.plone.api.user.get_current"
        ) as get_current_mock,
        mock.patch(
            "collective.bpmproxy.portlets.signal.get_tenant_ids"
        ) as get_tenant_ids_mock,
        mock.patch(
            "collective.bpmproxy.portlets.signal._throwSignal"
        ) as throw_signal_mock,
        mock.patch("collective.bpmproxy.portlets.signal.camunda_client"),
        mock.patch(
            "collective.bpmproxy.portlets.signal.get_available_tasks"
        ) as get_tasks_mock,
        mock.patch("collective.bpmproxy.portlets.signal.IUUID"),
        mock.patch(
            "collective.bpmproxy.portlets.signal.IAnnotations"
        ) as annotations_mock,
    ):
        interpolator_mock.return_value = lambda x: x
        is_anonymous_mock.return_value = False
        get_current_mock().getUserName.return_value = "admin"
        get_tenant_ids_mock.return_value = ["tenant1"]

        task_mock = mock.Mock()
        task_mock.id = "task-123"
        get_tasks_mock.return_value = [task_mock]

        context.absolute_url.return_value = "http://127.0.0.1/plone/doc"

        annotations_mock.return_value = mock.MagicMock()
        annotations_mock.return_value.get.return_value = "token-123"

        form.dispatch(mock.Mock(), mock.Mock())

        throw_signal_mock.assert_called_once_with(
            "signal_name", "{}", "admin", ["tenant1"]
        )

        assert request.response.getStatus() in (302, 303)
        assert (
            request.response.getHeader("Location")
            == "http://127.0.0.1/plone/doc/@@bpm-task/task-123?token=token-123"
        )


def test_signal_form_dispatch_anonymous_exception():
    context = mock.Mock()
    request = TestRequest()
    form = SignalForm(context, request, "prefix.", "My Button", "signal_name", "{}")

    with (
        mock.patch("collective.bpmproxy.portlets.signal.IStringInterpolator"),
        mock.patch(
            "collective.bpmproxy.portlets.signal.plone.api.user.is_anonymous"
        ) as is_anonymous_mock,
        mock.patch("collective.bpmproxy.portlets.signal._throwSignal"),
        mock.patch("collective.bpmproxy.portlets.signal.camunda_client"),
        mock.patch(
            "collective.bpmproxy.portlets.signal.get_available_tasks"
        ) as get_tasks_mock,
        mock.patch("collective.bpmproxy.portlets.signal.get_tenant_ids"),
        mock.patch("collective.bpmproxy.portlets.signal.IUUID"),
    ):
        is_anonymous_mock.return_value = True

        from generic_camunda_client import ApiException

        get_tasks_mock.side_effect = ApiException()

        # should pass silently
        form.dispatch(mock.Mock(), mock.Mock())


def test_assignment():
    assignment = Assignment(header="Header", name="sig", payload="{}")
    assert assignment.header == "Header"
    assert assignment.name == "sig"
    assert assignment.payload == "{}"
    assert assignment.title == "Signal dispatch"


def test_add_form():
    form = AddForm(mock.Mock(), mock.Mock())
    assignment = form.create({"header": "H", "name": "N", "payload": "P"})
    assert isinstance(assignment, Assignment)
    assert assignment.header == "H"


def test_edit_form():
    form = EditForm(mock.Mock(), mock.Mock())
    assert form.label == "Edit Signal dispatch"


def test_renderer():
    context = mock.Mock()
    request = TestRequest()
    assignment = Assignment(header="H", name="N", payload="P")

    with mock.patch("collective.bpmproxy.portlets.signal.getMultiAdapter") as gma:
        portal_state_mock = mock.Mock()
        portal_state_mock.anonymous.return_value = False
        gma.return_value = portal_state_mock

        renderer = Renderer(context, request, mock.Mock(), mock.Mock(), assignment)

        assert renderer.available is True

        # mock render to avoid rendering real z3c form
        with mock.patch("collective.bpmproxy.portlets.signal.SignalForm") as form_mock:
            form_mock().render.return_value = "rendered-form"
            res = renderer.render()
            assert res == "rendered-form"
