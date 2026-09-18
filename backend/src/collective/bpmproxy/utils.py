from Acquisition import aq_inner
from Acquisition import aq_parent
from concurrent.futures import ThreadPoolExecutor
from dateutil.parser import isoparse
from plone.stringinterp.interfaces import IStringInterpolator
from transaction.interfaces import IDataManager
from uuid import UUID
from zope.component import getUtility
from zope.interface import implementer
from zope.interface.interfaces import ComponentLookupError
from zope.schema.interfaces import IVocabularyFactory
import datetime
import json
import logging
import plone.api
import pytz
import re
import string
import transaction


MAYBE_ISODT = re.compile(r"[0-9:\-\+T]+")


logger = logging.getLogger(__name__)


def get_tenant_ids():
    return list(
        filter(
            bool,
            plone.api.portal.get_registry_record(
                name="collective.bpmproxy.tenant_ids",
                default=[],
            )
            or [],
        )
    )


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
                return str(dt_utc.date())
            if dt.date() == datetime.date.min:
                # time
                return dt.isoformat().split("T")[-1]
            # datetime
            return iso
        except ValueError:
            return None

    return {
        name: (
            variable.value and parse_date(variable.value)
            if variable.type == "Date"
            else variable.value
        )
        for name, variable in variables.items()
        if variable.value is not None
    }


def interpolate(value, interpolator):
    if interpolator is not None:
        if isinstance(value, str):
            return interpolator(value).strip()
        elif isinstance(value, (list, tuple)):
            return [interpolate(v, interpolator) for v in value]
        elif isinstance(value, dict):
            return {k: interpolate(v, interpolator) for k, v in value.items()}
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
            if isinstance(value, str):
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


class ValidationError(AssertionError):
    """Raised when submitted form data does not satisfy its form schema.

    Subclasses AssertionError so that existing ``except AssertionError``
    handlers keep catching it, but -- unlike the bare ``assert`` statements
    this replaced -- it is not stripped when Python runs with ``-O``.
    """


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def validate_camunda_form(data_json, schema_json, context):
    data = json.loads(data_json)
    schema = json.loads(schema_json)

    for component in schema.get("components") or []:
        if component.get("disabled"):
            # Skip validation of disabled fields
            continue

        key = component.get("key")
        validation = component.get("validate") or {}
        value = data.get(key)

        pattern = validation.get("pattern")
        if pattern:
            _require(
                re.match(pattern, value or ""),
                f"Field {key} must match pattern /{pattern}/.",
            )

        if validation.get("required"):
            _require(value not in [None, ""], f"Field {key} is required.")

        # Numeric bounds only apply to fields that were actually filled in;
        # an empty value is the "required" check's business, not theirs.
        min_value = validation.get("min")
        if min_value is not None and value not in [None, ""]:
            _require(
                value >= min_value,
                f"Field {key} must have minimum value of {min_value}.",
            )

        max_value = validation.get("max")
        if max_value is not None and value not in [None, ""]:
            _require(
                value <= max_value,
                f"Field {key} must have maximum value of {max_value}.",
            )

        min_length = validation.get("minLength")
        if min_length is not None:
            _require(
                len(value or "") >= min_length,
                f"Field {key} must have minimum length of {min_length}.",
            )

        max_length = validation.get("maxLength")
        if max_length is not None:
            _require(
                len(value or "") <= max_length,
                f"Field {key} must have maximum length of {max_length}.",
            )

        if (component.get("properties") or {}).get("vocabulary") and value:
            try:
                name = component["properties"]["vocabulary"]
                factory = getUtility(IVocabularyFactory, name)
                vocabulary = factory(context)
                _require(
                    vocabulary.getTermByToken(value),
                    f"Field {key} must be selected from given options.",
                )
            except ComponentLookupError:
                raise ValidationError(f"Field {key} must define vocabulary.") from None
            except LookupError:
                raise ValidationError(
                    f"Field {key} must be selected from given options."
                ) from None


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
class SideEffectDataManager:
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

    def _log_side_effect_result(self, future):
        # The work runs after the transaction has committed, so there is
        # nothing left to roll back -- but a failure must not be silent.
        try:
            future.result()
        except Exception:
            logger.exception("Deferred side effect failed: %r", self.callable)

    def tpc_finish(self, txn):
        try:
            future = SIDE_EFFECT_WORKER.submit(self.callable, *self.args)
        except Exception:
            # Any exceptions here can cause database corruption.
            logger.exception("Failed in tpc_finish for %r", self.callable)
        else:
            future.add_done_callback(self._log_side_effect_result)

    tpc_abort = abort

    def savepoint(self):
        return transaction._transaction.NoRollbackSavepoint(self)


def is_valid_uuid(uuid_to_test, version=4):
    try:
        uuid_obj = UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test or uuid_obj.hex == uuid_to_test
