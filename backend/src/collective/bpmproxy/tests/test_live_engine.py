"""Tests that need a real Operaton engine.

Everything else in this suite mocks ``camunda_client``, which means the one
thing never exercised is the part most likely to break in a deployment: that
Plone's ed25519-signed JWT is actually accepted by the engine's
``JWTAuthenticationProvider``, and that the generated client can round-trip a
deployment.

These carry the ``operaton`` marker, so the default ``make test`` skips them
and ``make test-live`` runs them. Start the engine first::

    devenv up -d
    devenv processes wait
    make test-live
"""

from collective.bpmproxy.client import camunda_admin_client
from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import delete_deployment
from collective.bpmproxy.client import deploy_process
from collective.bpmproxy.client import get_deployments
from collective.bpmproxy.interfaces import CAMUNDA_ADMIN_GROUP
from collective.bpmproxy.portlets.tasks import Assignment as TasksAssignment
from collective.bpmproxy.portlets.tasks import Renderer as TasksRenderer
from unittest import mock
from unittest.mock import MagicMock
import generic_camunda_client
import os
import pytest
import requests
import uuid


pytestmark = pytest.mark.operaton


PROCESS_KEY = "collective-bpmproxy-live-check"

MINIMAL_BPMN = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
    id="Definitions_live" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="{PROCESS_KEY}" name="Live check" isExecutable="true"
      camunda:historyTimeToLive="P1D">
    <bpmn:startEvent id="StartEvent_1" />
  </bpmn:process>
</bpmn:definitions>
"""


def _one_user_task_bpmn(process_key):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
    id="Definitions_{process_key}" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="{process_key}" name="{process_key}" isExecutable="true"
      camunda:historyTimeToLive="P1D">
    <bpmn:startEvent id="StartEvent_1">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:userTask id="Task_1" name="A task">
      <bpmn:incoming>Flow_1</bpmn:incoming>
    </bpmn:userTask>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1" />
  </bpmn:process>
</bpmn:definitions>
"""


@pytest.fixture
def engine_configured():
    """Skip rather than fail when the engine's environment is not set up."""
    if not os.environ.get("CAMUNDA_API_PRIVATE_KEY"):
        pytest.skip("CAMUNDA_API_PRIVATE_KEY is not set; run inside devenv shell")


def test_engine_accepts_a_plone_signed_token(integration, engine_configured):
    """A JWT signed by Plone is accepted on /engine-rest.

    This is the whole trust relationship in one assertion: if the key pair or
    the EdDSA algorithm ever drift apart, every other feature fails with an
    opaque 401 and this is the test that says why.
    """
    with camunda_admin_client(tenant_ids=[]) as client:
        deployments = get_deployments(client)
    assert isinstance(deployments, list)


def test_deploy_and_delete_round_trip(integration, engine_configured):
    """Deploying and deleting through the add-on's own client works."""
    name = f"live-check-{uuid.uuid4().hex[:8]}.bpmn"

    with camunda_admin_client(tenant_ids=[]) as client:
        # deploy_process goes through `requests` rather than the generated
        # client, so it returns the parsed JSON dict, not a model object.
        deployment = deploy_process(client, name, MINIMAL_BPMN)
        assert isinstance(deployment, dict)
        assert deployment["id"]

        try:
            names = [d.name for d in get_deployments(client)]
            assert name in names
        finally:
            delete_deployment(client, deployment["id"])

        assert name not in [d.name for d in get_deployments(client)]


def test_unprivileged_user_token_is_refused_engine_rights(
    integration, engine_configured
):
    """A token without the camunda-admin group cannot deploy.

    The add-on relies on the engine -- not only on Plone permissions -- to
    keep deployment to administrators, so this asserts the second half of the
    B7 case that the browser suite checks from the outside.
    """
    assert CAMUNDA_ADMIN_GROUP == "camunda-admin"

    # camunda_client() signs for the *current* user, which in the integration
    # layer is a plain test user outside camunda-admin. deploy_process raises
    # requests.HTTPError rather than the generated client's ApiException --
    # the two halves of the client do not share an error type, which is why
    # the deploy service has to catch both.
    with camunda_client() as client:
        with pytest.raises(requests.HTTPError) as caught:
            deploy_process(client, "refused.bpmn", MINIMAL_BPMN)
    assert caught.value.response.status_code in (401, 403)


def test_tasks_portlet_filters_by_process_definition_key(
    integration, engine_configured
):
    """L3: filtering now happens in the engine query, not by parsing IDs in
    Python. Deploy two definitions, start one instance of each, and assert
    the portlet configured for one key only ever lists that one's task.

    The task carries no candidateGroups/assignee, so it is only visible to
    a query the engine's authorization model treats as broad-read (the
    camunda-admin group) -- unrelated to what this test is checking, so the
    portlet's own camunda_client() (which signs for the current, unprivileged
    integration-layer user) is patched to camunda_admin_client() here.
    """
    key_a = f"collective-bpmproxy-live-a-{uuid.uuid4().hex[:8]}"
    key_b = f"collective-bpmproxy-live-b-{uuid.uuid4().hex[:8]}"

    with camunda_admin_client(tenant_ids=[]) as client:
        deployment_a = deploy_process(
            client, f"{key_a}.bpmn", _one_user_task_bpmn(key_a)
        )
        deployment_b = deploy_process(
            client, f"{key_b}.bpmn", _one_user_task_bpmn(key_b)
        )
        try:
            definition_api = generic_camunda_client.ProcessDefinitionApi(client)
            # Not necessarily "{key}:{version}:{uuid}" -- Operaton's default
            # ID generator can also hand out a bare UUID, which is exactly
            # why filtering happens through the engine's own
            # processDefinitionKey query field now, not by parsing this
            # string. Assert against the started instance's id instead of
            # assuming a particular id shape.
            pi_a = definition_api.start_process_instance_by_key(key_a)
            definition_api.start_process_instance_by_key(key_b)

            assignment = TasksAssignment(
                header="Tasks",
                use_context=False,
                process_definition_key=key_a,
            )
            portal = integration["portal"]
            renderer = TasksRenderer(
                portal, portal.REQUEST, MagicMock(), MagicMock(), assignment
            )
            with mock.patch(
                "collective.bpmproxy.portlets.tasks.camunda_client",
                lambda: camunda_admin_client(tenant_ids=[]),
            ):
                tasks = renderer.tasks()

            assert len(tasks) == 1
            assert tasks[0].process_instance_id == pi_a.id
        finally:
            delete_deployment(client, deployment_a["id"])
            delete_deployment(client, deployment_b["id"])
