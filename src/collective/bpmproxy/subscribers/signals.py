from collective.bpmproxy.client import camunda_admin_client
from collective.bpmproxy.utils import infer_variables, SideEffectDataManager
from generic_camunda_client import SignalDto
from plone.uuid.interfaces import IUUID
from Products.CMFCore.interfaces import IActionSucceededEvent

import functools
import generic_camunda_client
import transaction


def _throwSignal(signal, payload):
    with camunda_admin_client() as client:
        api = generic_camunda_client.SignalApi(client)
        dto = SignalDto(name=signal, variables=infer_variables(payload))
        api.throw_signal(signal_dto=dto)


def throwSignal(ob, event):
    uuid = IUUID(ob)
    payload = {}  # Careful! By default, payload would override process variables.
    for iface in event.__provides__.interfaces():
        signal = iface.__identifier__ + ":" + uuid
        transaction.get().join(
            SideEffectDataManager(functools.partial(_throwSignal, signal, payload))
        )
    if IActionSucceededEvent.providedBy(event):
        signal = IActionSucceededEvent.__identifier__ + ":" + uuid + ":" + event.action
        transaction.get().join(
            SideEffectDataManager(functools.partial(_throwSignal, signal, payload))
        )
