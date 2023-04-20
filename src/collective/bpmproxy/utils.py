from Acquisition import aq_inner, aq_parent
from concurrent.futures import ThreadPoolExecutor
from plone.stringinterp.interfaces import IStringInterpolator
from transaction.interfaces import IDataManager
from uuid import UUID
from dateutil.parser import isoparse
from zope.component import getUtility
from zope.interface import implementer
from zope.interface.interfaces import ComponentLookupError
from zope.schema.interfaces import IVocabularyFactory

import datetime
import json
import logging
import pytz
import re
import six
import string
import transaction
import plone.api

MAYBE_ISODT = re.compile(r"[0-9:\-\+T]+")


logger = logging.getLogger(__name__)


def get_tenant_ids():
    return plone.api.portal.get_registry_record(
        name="collective.bpmproxy.tenant_ids", default=[],
    ) or []

def datetime_to_c7(dt):
    iso = dt.isoformat()
    if len(iso) < 25:
        # 0001-01-01T11:30:00
        return iso + ".0+0000"
    else:
        # 0001-01-01T11:30:00+00:00
        return iso[:-6] + ".0" + iso[-6:].replace(":", "")


def infer_variable(value):
    if isinstance(value, list):
        return {"value": json.dumps(value), "type": "Json"}
    elif isinstance(value, bool):
        return {"value": value, "type": "Boolean"}
    elif isinstance(value, int):
        return {"value": value, "type": "Integer"}
    else:
        if MAYBE_ISODT.match(value):
            dt = None
            try:
                dt = isoparse(value)
            except ValueError:
                try:
                    dt = isoparse(datetime.date.today().isoformat() + "T" + value)
                    dt = dt.combine(datetime.date.min, dt.time(), tzinfo=dt.tzinfo)
                except ValueError:
                    pass
            if dt:
                # print(value, datetime_to_c7(dt))
                return {"value": datetime_to_c7(dt), "type": "Date"}
        return {"value": str(value), "type": "String"}


def infer_variables(data):
    if not isinstance(data, dict):
        return []

    variables = {}
    for key, value in data.items():
        variables[key] = infer_variable(value)
    return variables


def flatten_variables(variables):
    def parse_date(iso):
        try:
            dt = isoparse(iso)
            dt_utc = dt.astimezone(pytz.utc)
            if dt_utc.time().isoformat() == "00:00:00":
                # date
                # print(iso, str(dt_utc.date()))
                return str(dt_utc.date())
            if dt.date() == datetime.date.min:
                # time
                # print(iso, dt.isoformat().split("T")[-1])
                return dt.isoformat().split("T")[-1]
            # datetime
            # print(iso, iso)
            return iso
        except ValueError:
            return None
        return value

    return dict(
        [
            (
                name,
                variable.value and parse_date(variable.value)
                if variable.type == "Date"
                else variable.value,
            )
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


def prepare_camunda_form(schema_json, default_data, default_values, context):
    schema = json.loads(schema_json)
    data = {}
    options = {}
    interpolator = IStringInterpolator(context)

    for component in schema.get("components") or []:
        key = component.get("key")
        default_value = component.get("defaultValue")

        if default_value:
            component["defaultValue"] = interpolate(
                component["defaultValue"], interpolator
            )
            # Allow saving of default value for disabled fields
            if component.get("disabled"):
                data[key] = component["defaultValue"]

        if default_data.get(key) is not None:
            value = default_data[key]
            if isinstance(value, six.text_type):
                data[key] = value.strip()
            else:
                data[key] = value

        elif key in default_values:
            data[key] = interpolate(default_values[key], interpolator)

        # Set options from task variables
        if component.get("valuesKey") and component["valuesKey"] in default_data:
            options[component["valuesKey"]] = default_data[component["valuesKey"]]

        # Populate dynamic data for fields with property vocabulary
        # See: https://github.com/bpmn-io/form-js/pull/270
        if context and (component.get("properties") or {}).get("vocabulary"):
            name = component["properties"]["vocabulary"]
            try:
                factory = getUtility(IVocabularyFactory, name)
                vocabulary = factory(context)
                component["valuesKey"] = name + ".values"
                options[component["valuesKey"]] = [
                    {"label": term.title, "value": term.token} for term in vocabulary
                ]
            except ComponentLookupError:
                pass

        if component.get("type") == "text":
            component["text"] = string.Template(component["text"]).safe_substitute(
                default_data
            )
            component["text"] = string.Template(component["text"]).safe_substitute(
                default_values
            )

    options.update(data)
    return (
        json.dumps(data),
        json.dumps(options),
        json.dumps(schema),
    )


def validate_camunda_form(data_json, schema_json, context):
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

        if (component.get("properties") or {}).get("vocabulary") and data.get(key):
            try:
                name = component["properties"]["vocabulary"]
                factory = getUtility(IVocabularyFactory, name)
                vocabulary = factory(context)
                assert vocabulary.getTermByToken(data.get(key)), (
                    "Field " + key + " must be selected from given options."
                )
            except ComponentLookupError:
                raise AssertionError("Field " + key + " must define vocabulary.")
            except LookupError:
                raise AssertionError(
                    "Field " + key + " must be selected from given options."
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


def is_valid_uuid(uuid_to_test, version=4):
    try:
        uuid_obj = UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test or uuid_obj.hex == uuid_to_test
