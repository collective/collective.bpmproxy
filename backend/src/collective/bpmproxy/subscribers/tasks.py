from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import get_available_tasks
from collective.bpmproxy.interfaces import ICollectiveBpmproxyLayer
from collective.bpmproxy.utils import SideEffectDataManager
from generic_camunda_client import ApiException
from generic_camunda_client import CompleteTaskDto
from plone.uuid.interfaces import IUUID
from zope.globalrequest import getRequest
from zope.interface import implementer
from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectModifiedEvent
import functools
import generic_camunda_client
import transaction
import urllib3.exceptions


@implementer(IObjectModifiedEvent)
def completeEditTask(obj, event):
    if not ICollectiveBpmproxyLayer.providedBy(getRequest()):
        return
    assert obj
    with camunda_client() as client:
        try:
            next_tasks = get_available_tasks(client, context_key=IUUID(event.object))
            for task in next_tasks:
                if task.form_key and task.form_key == "@@edit":
                    api = generic_camunda_client.TaskApi(client)
                    dto = CompleteTaskDto(variables={}, with_variables_in_return=False)
                    transaction.get().join(
                        SideEffectDataManager(
                            functools.partial(
                                api.complete, task.id, complete_task_dto=dto
                            )
                        )
                    )
        except (ApiException, urllib3.exceptions.HTTPError):
            pass


@implementer(IObjectAddedEvent)
def completeAddTask(obj, event):
    if not ICollectiveBpmproxyLayer.providedBy(getRequest()):
        return
    assert obj
    with camunda_client() as client:
        try:
            next_tasks = get_available_tasks(client, context_key=IUUID(event.newParent))
            for task in next_tasks:
                if (
                    task.form_key
                    and task.form_key.startswith("++add++")
                    and task.form_key[len("++add++") :].replace("+", " ")
                    == obj.portal_type
                ):
                    api = generic_camunda_client.TaskApi(client)
                    dto = CompleteTaskDto(variables={}, with_variables_in_return=False)
                    transaction.get().join(
                        SideEffectDataManager(
                            functools.partial(
                                api.complete, task.id, complete_task_dto=dto
                            )
                        )
                    )
        except (ApiException, urllib3.exceptions.HTTPError):
            pass
