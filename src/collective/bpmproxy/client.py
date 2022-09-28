from collective.bpmproxy import _
from collective.bpmproxy.interfaces import (
    ANONYMOUS_USER_ANNOTATION_KEY,
    ANONYMOUS_USER_PREFIX,
    CAMUNDA_ADMIN_GROUP,
    CAMUNDA_ADMIN_USER,
    CAMUNDA_API_PRIVATE_KEY_ENV,
    CAMUNDA_API_URL_DEFAULT,
    CAMUNDA_API_URL_ENV,
    PENDING_TASKS_MAX_RESULTS,
)
from collective.bpmproxy.utils import (
    flatten_variables,
    infer_variables,
    is_valid_uuid,
    prepare_camunda_form,
)
from contextlib import contextmanager
from generic_camunda_client import (
    ApiException,
    CompleteTaskDto,
    StartProcessInstanceDto,
    TaskQueryDto,
    TaskQueryDtoSorting,
)
from plone.stringinterp.interfaces import IStringInterpolator
from zope.annotation import IAnnotations

import datetime
import generic_camunda_client
import jwt
import logging
import os
import plone.api
import uuid


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
    if plone.api.user.is_anonymous():
        request = plone.api.portal.getRequest()
        token = IAnnotations(request).get(
            ANONYMOUS_USER_ANNOTATION_KEY
        ) or request.form.get("token")
        if not (token and is_valid_uuid(token)):
            token = str(uuid.uuid4())
            IAnnotations(request)[ANONYMOUS_USER_ANNOTATION_KEY] = token
        token = get_token(
            username=ANONYMOUS_USER_PREFIX + token,
            groups=[],
        )
    else:
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


@contextmanager
def camunda_admin_client():
    configuration = generic_camunda_client.Configuration(host=get_api_url())
    authorization = "Bearer " + get_token(
        username=CAMUNDA_ADMIN_USER, groups=[CAMUNDA_ADMIN_GROUP]
    )
    with generic_camunda_client.ApiClient(
        configuration,
        header_name=authorization and "Authorization" or None,
        header_value=authorization,
    ) as client:
        yield client


def get_start_form(
    client,
    definition_key,
    current_values,
    default_values,
    context,
):
    api = generic_camunda_client.ProcessDefinitionApi(client)
    with open(api.get_deployed_start_form_by_key(definition_key)) as fp:
        return prepare_camunda_form(
            fp.read(),
            current_values,
            default_values,
            context,
        )


def get_task_form(
    client,
    task_id,
    current_values,
    default_values,
    context,
):
    api = generic_camunda_client.TaskApi(client)
    with open(api.get_deployed_form(task_id)) as fp:
        return prepare_camunda_form(
            fp.read(),
            current_values,
            default_values,
            context,
        )


def get_available_tasks(
    client, context_key=None, attachments_key=None, for_display=False
):
    task_api = generic_camunda_client.TaskApi(client)
    needle = (context_key or "%") + ":" + (attachments_key or "%")
    tasks = (
        task_api.query_tasks(
            task_query_dto=TaskQueryDto(
                process_instance_business_key_like=needle,
                sorting=[
                    TaskQueryDtoSorting(sort_by="dueDate", sort_order="asc"),
                    TaskQueryDtoSorting(sort_by="created", sort_order="desc"),
                ],
            ),
        )
        if context_key or attachments_key
        else task_api.query_tasks(
            max_results=PENDING_TASKS_MAX_RESULTS,
            task_query_dto=TaskQueryDto(
                sorting=[
                    TaskQueryDtoSorting(sort_by="dueDate", sort_order="asc"),
                    TaskQueryDtoSorting(sort_by="created", sort_order="desc"),
                ]
            ),
        )
    )

    # Resolve users
    if for_display:
        get_member = plone.api.portal.get_tool("portal_membership").getMemberById
        for task in tasks:
            assignee_name = task.assignee or ""
            if assignee_name.startswith(ANONYMOUS_USER_PREFIX):
                task.assignee = _("Anonymous User")
            elif task.assignee:
                assignee = get_member(task.assignee)
                if assignee:
                    task.assignee = assignee.getProperty("fullname", "") or assignee
    return tasks


def get_next_tasks(client, process_id=None):
    api = generic_camunda_client.TaskApi(client)
    return api.query_tasks(
        task_query_dto=TaskQueryDto(process_instance_id=process_id),
    )


def submit_start_form(
    client,
    definition_key,
    business_key,
    form_variables,
    process_variables=None,
    context=None,
):
    api = generic_camunda_client.ProcessDefinitionApi(client)
    variables = form_variables.copy()

    if process_variables and context:
        interpolator = IStringInterpolator(context)
        variables.update(
            dict(
                [(k, interpolator(v)) for k, v in (process_variables or {}).items()]
            )  # noqa
        )

    dto = StartProcessInstanceDto(
        business_key=business_key,
        variables=infer_variables(variables),
    )

    try:
        return api.start_process_instance_by_key(
            definition_key, start_process_instance_dto=dto
        )
    except ApiException as e:
        logger.error(
            "Exception when calling ProcessDefinitionApi->start_process_instance_by_key: %s\n%s",
            e,
            dto,
        )
        raise


def submit_task_form(
    client,
    task_id,
    form_variables,
):
    api = generic_camunda_client.TaskApi(client)
    dto = CompleteTaskDto(
        variables=infer_variables(form_variables), with_variables_in_return=True
    )
    try:
        return api.complete(task_id, complete_task_dto=dto)
    except ApiException as e:
        logger.error("Exception when calling TaskApi->complete: %s\n%s", e, dto)
        raise


def get_task_variables(client, task_id):
    api = generic_camunda_client.TaskVariableApi(client)
    variables = api.get_task_variables(task_id)
    return flatten_variables(variables)


def get_diagram_xml(client, definition_id=None, definition_key=None):
    api = generic_camunda_client.ProcessDefinitionApi(client)
    dto = (
        api.get_process_definition_bpmn20_xml(definition_id)
        if definition_id
        else api.get_process_definition_bpmn20_xml_by_key(definition_key)
    )
    return dto.bpmn20_xml
