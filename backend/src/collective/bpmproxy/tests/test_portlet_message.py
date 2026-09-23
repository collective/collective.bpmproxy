from collective.bpmproxy.portlets.message import AddForm
from collective.bpmproxy.portlets.message import Assignment
from collective.bpmproxy.portlets.message import EditForm
from collective.bpmproxy.portlets.message import IMessagePortlet
from collective.bpmproxy.portlets.message import MessageForm
from collective.bpmproxy.portlets.message import Renderer
from unittest import mock
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.interface import directlyProvides
from zope.publisher.browser import TestRequest


def test_message_form_dispatch():
    context = mock.Mock()
    request = TestRequest()
    directlyProvides(request, IAttributeAnnotatable)
    form = MessageForm(
        context,
        request,
        "prefix.",
        "My Button",
        "message_name",
        "bk",
        {"uuid": "x"},
        "{}",
    )

    with (
        mock.patch(
            "collective.bpmproxy.portlets.message.IStringInterpolator"
        ) as interpolator_mock,
        mock.patch(
            "collective.bpmproxy.portlets.message.plone.api.user.is_anonymous"
        ) as is_anonymous_mock,
        mock.patch(
            "collective.bpmproxy.portlets.message.plone.api.user.get_current"
        ) as get_current_mock,
        mock.patch(
            "collective.bpmproxy.portlets.message.get_tenant_ids"
        ) as get_tenant_ids_mock,
        mock.patch(
            "collective.bpmproxy.portlets.message._throwMessage"
        ) as throw_message_mock,
        mock.patch("collective.bpmproxy.portlets.message.camunda_client"),
        mock.patch(
            "collective.bpmproxy.portlets.message.get_available_tasks"
        ) as get_tasks_mock,
        mock.patch("collective.bpmproxy.portlets.message.IUUID"),
        mock.patch(
            "collective.bpmproxy.portlets.message.IAnnotations"
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

        throw_message_mock.assert_called_once_with(
            "message_name", "bk", {"uuid": "x"}, "{}", "admin", ["tenant1"]
        )

        assert request.response.getStatus() in (302, 303)
        assert (
            request.response.getHeader("Location")
            == "http://127.0.0.1/plone/doc/@@bpm-task/task-123?token=token-123"
        )


def test_message_form_dispatch_anonymous_exception():
    context = mock.Mock()
    request = TestRequest()
    form = MessageForm(
        context, request, "prefix.", "My Button", "message_name", "bk", {}, "{}"
    )

    with (
        mock.patch("collective.bpmproxy.portlets.message.IStringInterpolator"),
        mock.patch(
            "collective.bpmproxy.portlets.message.plone.api.user.is_anonymous"
        ) as is_anonymous_mock,
        mock.patch("collective.bpmproxy.portlets.message._throwMessage"),
        mock.patch("collective.bpmproxy.portlets.message.camunda_client"),
        mock.patch(
            "collective.bpmproxy.portlets.message.get_available_tasks"
        ) as get_tasks_mock,
        mock.patch("collective.bpmproxy.portlets.message.get_tenant_ids"),
        mock.patch("collective.bpmproxy.portlets.message.IUUID"),
    ):
        is_anonymous_mock.return_value = True

        from generic_camunda_client import ApiException

        get_tasks_mock.side_effect = ApiException()

        # should pass silently
        form.dispatch(mock.Mock(), mock.Mock())


def test_assignment():
    assignment = Assignment(
        header="Header", name="msg", businessKey="bk", correlationKeys={}, payload="{}"
    )
    assert assignment.header == "Header"
    assert assignment.name == "msg"
    assert assignment.businessKey == "bk"
    assert assignment.correlationKeys == {}
    assert assignment.payload == "{}"
    assert assignment.title == "Message dispatch"


def test_add_form():
    form = AddForm(mock.Mock(), mock.Mock())
    assignment = form.create(
        {
            "header": "H",
            "name": "N",
            "businessKey": "bk",
            "correlationKeys": {},
            "payload": "P",
            "review_states": ["pending"],
        }
    )
    assert isinstance(assignment, Assignment)
    assert assignment.header == "H"
    assert assignment.review_states == ["pending"]


def test_edit_form():
    form = EditForm(mock.Mock(), mock.Mock())
    assert form.label == "Edit Message dispatch"


def test_review_states_uses_workflow_states_vocabulary():
    field = IMessagePortlet["review_states"]
    assert field.value_type.vocabularyName == "plone.app.vocabularies.WorkflowStates"


def test_renderer_unavailable_for_non_matching_review_state():
    context = mock.Mock()
    request = TestRequest()
    assignment = Assignment(review_states=["published"])

    with (
        mock.patch("collective.bpmproxy.portlets.message.getMultiAdapter") as gma,
        mock.patch(
            "collective.bpmproxy.portlets.message.plone.api.content.get_state",
            return_value="private",
        ),
    ):
        portal_state_mock = mock.Mock()
        portal_state_mock.anonymous.return_value = False
        gma.return_value = portal_state_mock

        renderer = Renderer(context, request, mock.Mock(), mock.Mock(), assignment)

        assert renderer.available is False


def test_renderer():
    context = mock.Mock()
    request = TestRequest()
    assignment = Assignment(
        header="H", name="N", businessKey="bk", correlationKeys={}, payload="P"
    )

    with mock.patch("collective.bpmproxy.portlets.message.getMultiAdapter") as gma:
        portal_state_mock = mock.Mock()
        portal_state_mock.anonymous.return_value = False
        gma.return_value = portal_state_mock

        renderer = Renderer(context, request, mock.Mock(), mock.Mock(), assignment)

        assert renderer.available is True

        # mock render to avoid rendering real z3c form
        with mock.patch(
            "collective.bpmproxy.portlets.message.MessageForm"
        ) as form_mock:
            form_mock().render.return_value = "rendered-form"
            res = renderer.render()
            assert res == "rendered-form"
