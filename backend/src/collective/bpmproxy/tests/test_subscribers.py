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
            patch("collective.bpmproxy.subscribers.tasks.transaction.get"),
            patch("collective.bpmproxy.subscribers.tasks.SideEffectDataManager"),
            patch("collective.bpmproxy.subscribers.tasks.IUUID", return_value="uuid"),
        ):
            completeEditTask(obj, event)

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
            patch("collective.bpmproxy.subscribers.tasks.transaction.get"),
            patch("collective.bpmproxy.subscribers.tasks.SideEffectDataManager"),
            patch("collective.bpmproxy.subscribers.tasks.IUUID", return_value="uuid"),
        ):
            completeAddTask(obj, event)
