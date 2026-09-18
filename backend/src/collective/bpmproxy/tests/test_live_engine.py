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
