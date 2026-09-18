from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import delete_deployment
from collective.bpmproxy.client import get_deployments
from plone.restapi.services import Service
import json
import logging


logger = logging.getLogger(__name__)


class DeploymentsGet(Service):
    """GET /@bpmproxy-deployments"""

    def reply(self):
        try:
            with camunda_client() as client:
                deployments = get_deployments(client)

            # Serialize the results since swagger models are not directly JSON serializable
            result = []
            for d in deployments:
                result.append(
                    {
                        "id": d.id,
                        "name": d.name,
                        "source": d.source,
                        "deploymentTime": str(d.deployment_time)
                        if d.deployment_time
                        else None,
                        "tenantId": d.tenant_id,
                    }
                )
            return result
        except Exception:
            # Do not echo internal exception text (paths, connection
            # strings) back to the client; log it and return a generic
            # message. Deliberate, actionable errors are returned above.
            logger.exception("Unexpected error in %s", type(self).__name__)
            self.request.response.setStatus(500)
            return {"error": "Unexpected error; see the Plone log for details."}


class DeploymentsDelete(Service):
    """DELETE /@bpmproxy-deployments"""

    def reply(self):
        try:
            # We expect the ID in the body for delete or query param. Let's use a query string or body payload.
            # Assuming body payload for consistency with deploy
            data = json.loads(self.request.get("BODY", "{}"))
            deployment_id = data.get("id")

            if not deployment_id:
                # Also try to get from request form (query string)
                deployment_id = self.request.form.get("id")

            if not deployment_id:
                self.request.response.setStatus(400)
                return {"error": "Missing 'id' parameter for deletion"}

            with camunda_client() as client:
                delete_deployment(client, deployment_id)

            return {"status": "deleted", "id": deployment_id}
        except Exception:
            # Do not echo internal exception text (paths, connection
            # strings) back to the client; log it and return a generic
            # message. Deliberate, actionable errors are returned above.
            logger.exception("Unexpected error in %s", type(self).__name__)
            self.request.response.setStatus(500)
            return {"error": "Unexpected error; see the Plone log for details."}
