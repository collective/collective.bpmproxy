import functools

import generic_camunda_client
import transaction
from generic_camunda_client import ApiException, CompleteTaskDto
from plone.uuid.interfaces import IUUID
from zope.interface import implementer
from zope.lifecycleevent import IObjectModifiedEvent, IObjectAddedEvent
from zope.globalrequest import getRequest

from collective.bpmproxy.client import camunda_client, get_available_tasks
from collective.bpmproxy.utils import SideEffectDataManager
from collective.bpmproxy.interfaces import ICollectiveBpmproxyLayer

import plone.api


@implementer(IObjectModifiedEvent)
def completeEditTask(obj, event):
    if not ICollectiveBpmproxyLayer.providedBy(getRequest()):
        return
    assert obj
    with camunda_client() as client:
        try:
            next_tasks = get_available_tasks(
                client, context_key=IUUID(event.object)
            )
            for task in next_tasks:
                if task.form_key and task.form_key == "@@edit":
                    api = generic_camunda_client.TaskApi(client)
                    dto = CompleteTaskDto(variables={}, with_variables_in_return=False)
                    transaction.get().join(
                        SideEffectDataManager(
                            functools.partial(api.complete, task.id, complete_task_dto=dto)
                        )
                    )
        except ApiException:
            pass


@implementer(IObjectAddedEvent)
def completeAddTask(obj, event):
    if not ICollectiveBpmproxyLayer.providedBy(getRequest()):
        return
    assert obj
    with camunda_client() as client:
        try:
            next_tasks = get_available_tasks(
                client, context_key=IUUID(event.newParent)
            )
            for task in next_tasks:
                if task.form_key and task.form_key.startswith("++add++") and task.form_key[len("++add++"):].replace("+", " ") == obj.portal_type:
                    api = generic_camunda_client.TaskApi(client)
                    dto = CompleteTaskDto(variables={}, with_variables_in_return=False)
                    transaction.get().join(
                        SideEffectDataManager(
                            functools.partial(api.complete, task.id, complete_task_dto=dto)
                        )
                    )
        except ApiException:
            pass
