from collective.bpmproxy.client import complete_task
from collective.bpmproxy.subscribers.tasks import completeAddTask
from collective.bpmproxy.subscribers.tasks import completeEditTask
from unittest.mock import MagicMock
from unittest.mock import patch
import unittest


class TestTasksSubscribers(unittest.TestCase):
    def test_completeEditTask_no_layer(self):
        with (
            patch("collective.bpmproxy.subscribers.tasks.getRequest"),
            patch(
                "collective.bpmproxy.subscribers.tasks.ICollectiveBpmproxyLayer.providedBy",
                return_value=False,
            ),
        ):
            completeEditTask(MagicMock(), MagicMock())

    def test_completeEditTask_with_layer(self):
        obj = MagicMock()
        event = MagicMock()
        event.object = obj

        task = MagicMock()
        task.form_key = "@@edit"
        task.id = "task_id"

        with (
            patch("collective.bpmproxy.subscribers.tasks.getRequest"),
            patch(
                "collective.bpmproxy.subscribers.tasks.ICollectiveBpmproxyLayer.providedBy",
                return_value=True,
            ),
            patch("collective.bpmproxy.subscribers.tasks.camunda_client"),
            patch(
                "collective.bpmproxy.subscribers.tasks.get_available_tasks",
                return_value=[task],
            ),
            patch(
                "collective.bpmproxy.subscribers.tasks.generic_camunda_client.TaskApi"
            ),
            patch("collective.bpmproxy.subscribers.tasks.CompleteTaskDto"),
            patch(
                "collective.bpmproxy.subscribers.tasks.join_side_effect"
            ) as mock_join_side_effect,
            patch("collective.bpmproxy.subscribers.tasks.IUUID", return_value="uuid"),
        ):
            completeEditTask(obj, event)

        mock_join_side_effect.assert_called_once()
        assert mock_join_side_effect.call_args[0][0] is complete_task
        assert mock_join_side_effect.call_args[1]["args"][1] == "task_id"

    def test_completeAddTask_no_layer(self):
        with (
            patch("collective.bpmproxy.subscribers.tasks.getRequest"),
            patch(
                "collective.bpmproxy.subscribers.tasks.ICollectiveBpmproxyLayer.providedBy",
                return_value=False,
            ),
        ):
            completeAddTask(MagicMock(), MagicMock())

    def test_completeAddTask_with_layer(self):
        obj = MagicMock()
        obj.portal_type = "MyType"
        event = MagicMock()
        event.newParent = MagicMock()

        task = MagicMock()
        task.form_key = "++add++MyType"
        task.id = "task_id"

        with (
            patch("collective.bpmproxy.subscribers.tasks.getRequest"),
            patch(
                "collective.bpmproxy.subscribers.tasks.ICollectiveBpmproxyLayer.providedBy",
                return_value=True,
            ),
            patch("collective.bpmproxy.subscribers.tasks.camunda_client"),
            patch(
                "collective.bpmproxy.subscribers.tasks.get_available_tasks",
                return_value=[task],
            ),
            patch(
                "collective.bpmproxy.subscribers.tasks.generic_camunda_client.TaskApi"
            ),
            patch("collective.bpmproxy.subscribers.tasks.CompleteTaskDto"),
            patch(
                "collective.bpmproxy.subscribers.tasks.join_side_effect"
            ) as mock_join_side_effect,
            patch("collective.bpmproxy.subscribers.tasks.IUUID", return_value="uuid"),
        ):
            completeAddTask(obj, event)

        mock_join_side_effect.assert_called_once()
        assert mock_join_side_effect.call_args[0][0] is complete_task
        assert mock_join_side_effect.call_args[1]["args"][1] == "task_id"
