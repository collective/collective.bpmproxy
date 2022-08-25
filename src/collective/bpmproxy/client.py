from collective.bpmproxy.interfaces import (
    CAMUNDA_API_PRIVATE_KEY_ENV,
    CAMUNDA_API_URL_DEFAULT,
    CAMUNDA_API_URL_ENV,
)
from collective.bpmproxy.utils import (
    flatten_variables,
    infer_variables,
    prepare_camunda_form,
)
from contextlib import contextmanager
from generic_camunda_client import ApiException
from plone.uuid.interfaces import IUUID

import datetime
import generic_camunda_client
import jwt
import logging
import os
import plone.api


logger = logging.getLogger(__name__)


def get_api_url():
    return os.environ.get(CAMUNDA_API_URL_ENV) or CAMUNDA_API_URL_DEFAULT


def get_token(username, groups):
    private_key = os.environ.get(CAMUNDA_API_PRIVATE_KEY_ENV)
    if private_key and os.path.exists(private_key):
        with open(private_key, "r", encoding="utf-8") as fp:
            private_key = fp.read()
    if not private_key:
        return None
    return jwt.encode(
        {
            "sub": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=3600),
            "groups": groups,
        },
        private_key,
        algorithm="ES256",
    )


def get_authorization():
    user = plone.api.user.get_current()
    token = get_token(
        username=user and user.getUserName() or None,
        groups=user
        and [g.getId() for g in plone.api.group.get_groups(user=user) or []],
    )
    return token and "Bearer " + token or None


@contextmanager
def camunda_client():
    configuration = generic_camunda_client.Configuration(host=get_api_url())
    authorization = get_authorization() or None
    with generic_camunda_client.ApiClient(
        configuration,
        header_name=authorization and "Authorization" or None,
        header_value=authorization,
    ) as client:
        yield client


def get_start_form(
    client, definition_key, current_values=None, default_values=None, interpolator=None
):
    api = generic_camunda_client.ProcessDefinitionApi(client)
    with open(api.get_deployed_start_form_by_key(definition_key)) as fp:
        return prepare_camunda_form(
            fp.read(), current_values or {}, default_values or {}, interpolator
        )


def get_task_form(
    client, task_id, current_values=None, default_values=None, interpolator=None
):
    api = generic_camunda_client.TaskApi(client)
    with open(api.get_deployed_form(task_id)) as fp:
        return prepare_camunda_form(
            fp.read(), current_values or {}, default_values or {}, interpolator
        )


def get_available_tasks(client, context_key=None, attachments_key=None):
    api = generic_camunda_client.TaskApi(client)
    needle = (context_key or "%") + ":" + (attachments_key or "%")
    return api.query_tasks(
        task_query_dto=dict(processInstanceBusinessKeyLike=needle),
    )


def get_next_tasks(client, process_id=None):
    api = generic_camunda_client.TaskApi(client)
    return api.query_tasks(
        task_query_dto=dict(processInstanceId=process_id),
    )


def submit_start_form(
    client,
    definition_key,
    business_key,
    form_variables,
    process_variables=None,
    interpolator=None,
):
    api = generic_camunda_client.ProcessDefinitionApi(client)
    variables = form_variables.copy()
    variables.update(
        dict([(k, interpolator(v)) for k, v in (process_variables or {}).items()])
    )
    payload = {
        "businessKey": business_key,
        "variables": infer_variables(variables),
    }
    try:
        return api.start_process_instance_by_key(
            definition_key, start_process_instance_dto=payload
        )
    except ApiException as e:
        logger.error(
            "Exception when calling ProcessDefinitionApi->start_process_instance_by_key: %s\n%s",
            e,
            payload,
        )
        raise


def submit_task_form(
    client,
    task_id,
    form_variables,
):
    api = generic_camunda_client.TaskApi(client)
    payload = {
        "variables": infer_variables(form_variables),
        "withVariablesInReturn": True,
    }
    try:
        return api.complete(task_id, complete_task_dto=payload)
    except ApiException as e:
        logger.error("Exception when calling TaskApi->complete: %s\n%s", e, payload)
        raise


def get_task_variables(client, task_id):
    api = generic_camunda_client.TaskVariableApi(client)
    variables = api.get_task_variables(task_id)
    return flatten_variables(variables)


def get_diagram_xml(client, definition_id):
    api = generic_camunda_client.ProcessDefinitionApi(client)
    dto = api.get_process_definition_bpmn20_xml(definition_id)
    return dto.bpmn20_xml
