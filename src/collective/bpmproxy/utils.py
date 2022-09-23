from Acquisition import aq_inner, aq_parent
from concurrent.futures import ThreadPoolExecutor
from transaction.interfaces import IDataManager
from zope.interface import implementer

import json
import logging
import re
import six
import transaction


logger = logging.getLogger(__name__)


def infer_variable(value):
    if isinstance(value, list):
        return {"value": json.dumps(value), "type": "Json"}
    elif isinstance(value, bool):
        return {"value": value, "type": "Boolean"}
    elif isinstance(value, int):
        return {"value": value, "type": "Integer"}
    else:
        return {"value": str(value), "type": "String"}


def infer_variables(data):
    if not isinstance(data, dict):
        return []

    variables = {}
    for key, value in data.items():
        variables[key] = infer_variable(value)
    return variables


def flatten_variables(variables):
    return dict(
        [
            (name, variable.value)
            for name, variable in variables.items()
            if variable.value is not None
        ]
    )


def interpolate(value, interpolator):
    if interpolator is not None:
        if isinstance(value, six.text_type):
            return interpolator(value).strip()
        elif isinstance(value, list) or isinstance(value, tuple):
            return [interpolate(v) for v in value]
        elif isinstance(value, dict):
            return dict([(k, interpolate(v)) for k, v in value.items()])
    return value


def prepare_camunda_form(schema_json, default_data, default_values, interpolator):
    schema = json.loads(schema_json)
    data = {}
    for component in schema.get("components") or []:
        key = component.get("key")
        if default_data.get(key) is not None:
            value = default_data[key]
            if isinstance(value, six.text_type):
                data[key] = value.strip()
            else:
                data[key] = value
        elif key in default_values:
            data[key] = interpolate(default_values[key], interpolator)
    return (
        json.dumps(data),
        json.dumps(schema),
    )


def validate_camunda_form(data_json, schema_json):
    data = json.loads(data_json)
    schema = json.loads(schema_json)

    for component in schema.get("components") or []:
        if component.get("disabled"):
            # Skip validation of disabled fields
            continue

        key = component.get("key")
        validation = component.get("validate") or {}

        pattern = validation.get("pattern")
        assert not pattern or re.match(pattern, data.get(key) or ""), (
            "Field " + key + " must match pattern /" + pattern + "/."
        )

        required = validation.get("required")
        assert not required or data.get(key) not in [None, ""], (
            "Field " + key + " is required."
        )

        min_value = validation.get("min")
        assert min_value is None or data.get(key) or 0 >= min_value, (
            "Field " + key + " must have minimum value of " + min_value + "."
        )

        max_value = validation.get("max")
        assert max_value is None or data.get(key) or 0 <= max_value, (
            "Field " + key + " must have maximum value of " + max_value + "."
        )

        min_length = validation.get("minLength")
        assert min_length is None or len(data.get(key) or "") >= min_length, (
            "Field " + key + " must have minimum length of " + min_length + "."
        )

        max_length = validation.get("maxLength")
        assert max_length is None or len(data.get(key) or "") <= max_length, (
            "Field " + key + " must have maximum length of " + max_length + "."
        )


# noinspection PyUnresolvedReferences
def parents(context, iface=None):
    """Iterate through parents for the context (providing the given interface).
    Return generator to walk the acquisition chain of object, considering that
    it could be a function.
    Source: http://plone.org/documentation/manual/developer-manual/archetypes/
    appendix-practicals/b-org-creating-content-types-the-plone-2.5-way/
    writing-a-custom-pas-plug-in
    """
    context = aq_inner(context)

    while context is not None:
        if iface is None or iface.providedBy(context):
            yield context

        func = getattr(context, "im_self", None)
        if func is not None:
            context = aq_inner(func)
        else:
            # Don't use Acquisition.aq_inner() since portal_factory (and
            # probably other) things, depends on being able to wrap itself in a
            # fake context.
            context = aq_parent(context)


SIDE_EFFECT_WORKER = ThreadPoolExecutor(max_workers=1)


@implementer(IDataManager)
class SideEffectDataManager(object):
    def __init__(self, callable, args=(), vote=None, onAbort=None):
        self.callable = callable
        self.args = args
        self.vote = vote
        self.onAbort = onAbort
        # Use the default thread transaction manager.
        self.transaction_manager = transaction.manager

    def commit(self, txn):
        pass

    def abort(self, txn):
        if self.onAbort:
            self.onAbort()

    def sortKey(self):
        return str(id(self))

    # No subtransaction support.
    def abort_sub(self, txn):
        """This object does not do anything with subtransactions"""
        pass

    commit_sub = abort_sub

    def beforeCompletion(self, txn):
        """This object does not do anything in beforeCompletion"""
        pass

    afterCompletion = beforeCompletion

    def tpc_begin(self, txn, subtransaction=False):
        assert not subtransaction

    def tpc_vote(self, txn):
        if self.vote is not None:
            return self.vote(*self.args)

    def tpc_finish(self, txn):
        try:
            SIDE_EFFECT_WORKER.submit(self.callable, *self.args)
        except Exception:
            # Any exceptions here can cause database corruption.
            logger.exception("Failed in tpc_finish for %r", self.callable)

    tpc_abort = abort

    def savepoint(self):
        return transaction._transaction.NoRollbackSavepoint(self)
