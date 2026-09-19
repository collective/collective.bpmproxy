from collective.bpmproxy import _
from collective.bpmproxy.interfaces import ANONYMOUS_USER_ANNOTATION_KEY
from collective.bpmproxy.interfaces import ANONYMOUS_USER_PREFIX
from collective.bpmproxy.interfaces import CAMUNDA_ADMIN_GROUP
from collective.bpmproxy.interfaces import CAMUNDA_ADMIN_USER
from collective.bpmproxy.interfaces import CAMUNDA_API_PRIVATE_KEY_ENV
from collective.bpmproxy.interfaces import CAMUNDA_API_URL_DEFAULT
from collective.bpmproxy.interfaces import CAMUNDA_API_URL_ENV
from collective.bpmproxy.interfaces import PENDING_TASKS_MAX_RESULTS
from collective.bpmproxy.utils import flatten_variables
from collective.bpmproxy.utils import get_tenant_ids
from collective.bpmproxy.utils import infer_variables
from collective.bpmproxy.utils import prepare_camunda_form
from collective.bpmproxy.utils import sign_anonymous_token
from collective.bpmproxy.utils import verify_anonymous_token
from contextlib import contextmanager
from generic_camunda_client import ApiException
from generic_camunda_client import CompleteTaskDto
from generic_camunda_client import StartProcessInstanceDto
from generic_camunda_client import TaskQueryDto
from generic_camunda_client import TaskQueryDtoSorting
from plone.stringinterp.interfaces import IStringInterpolator
from zope.annotation import IAnnotations
import datetime
import generic_camunda_client
import json
import jwt
import logging
import os
import plone.api
import requests
import uuid


logger = logging.getLogger(__name__)

# Deployments are proxied with plain requests (the generated client has no
# multipart deployment API). Always bound the call so a stalled engine cannot
# pin a Zope worker indefinitely.
DEPLOYMENT_TIMEOUT = 60


def get_api_url():
    return os.environ.get(CAMUNDA_API_URL_ENV) or CAMUNDA_API_URL_DEFAULT


def get_token(username, groups, tenant_ids=None):
    private_key = os.environ.get(CAMUNDA_API_PRIVATE_KEY_ENV)
    if private_key and os.path.exists(private_key):
        with open(private_key, encoding="utf-8") as fp:
            private_key = fp.read()
    if not private_key:
        return None
    if tenant_ids is None:
        tenant_ids = get_tenant_ids()
    return jwt.encode(
        {
            "sub": username,
            "exp": datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=3600),
            "groups": groups,
            "tenant_ids": tenant_ids,
        },
        private_key,
        algorithm="EdDSA",
    )


def get_authorization():
    if plone.api.user.is_anonymous():
        request = plone.api.portal.getRequest()
        # The identity that ties an anonymous visitor's requests together
        # travels as a bare "?token=" URL value (see views/bpm_form_view.py),
        # so it has to keep working as a plain string a link can carry -- but
        # unlike a bare UUID, it must be one this call issued: verifying the
        # signature is what stops a client from just picking any syntactically
        # valid UUID4 and assuming that identity. Its unguessability is by
        # design the *only* thing that keeps two visitors' sessions apart, so
        # anyone holding the (signed) link can resume it -- that is how the
        # anonymous requester flow hands off across a reviewer's turn.
        signed = IAnnotations(request).get(
            ANONYMOUS_USER_ANNOTATION_KEY
        ) or request.form.get("token")
        token = verify_anonymous_token(signed)
        if not token:
            token = str(uuid.uuid4())
            signed = sign_anonymous_token(token)
        IAnnotations(request)[ANONYMOUS_USER_ANNOTATION_KEY] = signed
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
def camunda_admin_client(username=None, tenant_ids=None):
    configuration = generic_camunda_client.Configuration(host=get_api_url())
    authorization = "Bearer " + get_token(
        username=username or CAMUNDA_ADMIN_USER,
        groups=[CAMUNDA_ADMIN_GROUP],
        tenant_ids=tenant_ids,
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
    if ":" in definition_key:
        definition_key, tenant_id = definition_key.rsplit(":", 1)
        with open(
            api.get_deployed_start_form_by_key_and_tenant_id(definition_key, tenant_id)
        ) as fp:
            return prepare_camunda_form(
                fp.read(),
                current_values,
                default_values,
                context,
            )
    else:
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


def business_key_needle(context_key=None, attachments_key=None):
    """Build the LIKE pattern matching a ``{context}:{attachments}`` key.

    Business keys are written by the form views as
    ``IUUID(context) + ":" + uuid4().hex`` -- two dash-less hex strings around
    a colon. Two things therefore have to happen here, and neither is
    optional:

    * the colon has to be in the pattern, otherwise a query narrowed by both
      halves matches the concatenation of them and never the real key;
    * the attachments half has to be normalised to hex, because callers pass
      the attachment container's id, which is the *dashed* ``str(UUID(...))``
      form of the same value.

    Missing halves become ``%`` so a query narrowed by one still matches.
    """

    def normalize(value):
        if value is None:
            return "%"
        return str(value).replace("-", "")

    return f"{normalize(context_key)}:{normalize(attachments_key)}"


def get_available_tasks(
    client,
    context_key=None,
    attachments_key=None,
    for_display=False,
    process_definition_key=None,
):
    # we assume that authentication is enough to filter tasks by tenants
    task_api = generic_camunda_client.TaskApi(client)
    needle = business_key_needle(context_key, attachments_key)
    # Vocabulary tokens are "{key}:{tenant}" when a tenant is set (see
    # AvailableProcessDefinitions), but the engine's own processDefinitionKey
    # filter takes a bare key -- tenant scoping already happens through the
    # JWT's tenant_ids claim, not a second query parameter here.
    definition_key = (
        process_definition_key.split(":", 1)[0] if process_definition_key else None
    )
    tasks = (
        task_api.query_tasks(
            task_query_dto=TaskQueryDto(
                process_instance_business_key_like=needle,
                process_definition_key=definition_key,
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
                process_definition_key=definition_key,
                sorting=[
                    TaskQueryDtoSorting(sort_by="dueDate", sort_order="asc"),
                    TaskQueryDtoSorting(sort_by="created", sort_order="desc"),
                ],
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
    if ":" in definition_key:
        definition_key, tenant_id = definition_key.rsplit(":", 1)
    else:
        tenant_id = None

    if process_variables and context:
        interpolator = IStringInterpolator(context)
        variables.update(
            dict([(k, interpolator(v)) for k, v in (process_variables or {}).items()])  # noqa
        )

    dto = StartProcessInstanceDto(
        business_key=business_key,
        variables=infer_variables(variables),
    )

    try:
        return (
            api.start_process_instance_by_key_and_tenant_id(
                definition_key, tenant_id, start_process_instance_dto=dto
            )
            if tenant_id
            else api.start_process_instance_by_key(
                definition_key, start_process_instance_dto=dto
            )
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

    # Json values require separate call with deserialized=False
    if any(v.type == "Json" for v in variables.values()):
        serialized = api.get_task_variables(task_id, deserialize_values=False)
        for k, v in serialized.items():
            if v.type == "Json":
                variables[k].value = json.loads(v.value)

    return flatten_variables(variables)


def get_diagram_xml(client, definition_id=None, definition_key=None, tenant_id=None):
    if definition_key and ":" in definition_key and tenant_id is None:
        definition_key, tenant_id = definition_key.rsplit(":", 1)
    api = generic_camunda_client.ProcessDefinitionApi(client)
    dto = (
        api.get_process_definition_bpmn20_xml(definition_id)
        if definition_id
        else api.get_process_definition_bpmn20_xml_by_key_and_tenant_id(
            definition_key, tenant_id
        )
        if tenant_id
        else api.get_process_definition_bpmn20_xml_by_key(definition_key)
    )
    return dto.bpmn20_xml


def deploy_process(client, name, xml_data, tenant_id=None):
    """Deploys a BPMN process XML to Operaton."""
    files = {
        "deployment-name": (None, name),
        "deployment-source": (None, "Plone Proxy"),
        "data": (name, xml_data, "application/octet-stream"),
    }
    if tenant_id:
        files["tenant-id"] = (None, tenant_id)

    url = f"{get_api_url()}/deployment/create"
    headers = {}
    if client.default_headers and client.default_headers.get("Authorization"):
        headers["Authorization"] = client.default_headers["Authorization"]

    response = requests.post(
        url, files=files, headers=headers, timeout=DEPLOYMENT_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def get_deployments(client, tenant_id=None):
    api = generic_camunda_client.DeploymentApi(client)
    return api.get_deployments(tenant_id_in=tenant_id if tenant_id else None)


def delete_deployment(client, deployment_id):
    api = generic_camunda_client.DeploymentApi(client)
    # generic_camunda_client's query-param serialization stringifies a
    # Python bool with str(), producing "True" -- the engine's boolean query
    # parsing for this endpoint doesn't recognize that capitalization as
    # true, so a deployment with running instances silently fails to
    # cascade-delete them (ENGINE-03076) despite this call asking it to.
    # The lowercase string is what a raw REST client sends and what the
    # engine actually expects.
    return api.delete_deployment(id=deployment_id, cascade="true")
