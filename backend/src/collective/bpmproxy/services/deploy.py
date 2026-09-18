from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import deploy_process
from plone.restapi.services import Service
import json
import logging
import requests


logger = logging.getLogger(__name__)


class DeployProcess(Service):
    """POST /@bpmproxy-deploy"""

    def reply(self):
        try:
            data = json.loads(self.request.get("BODY", "{}") or "{}")
        except ValueError as e:
            self.request.response.setStatus(400)
            return {"error": f"Invalid JSON payload: {e}"}

        xml_content = data.get("xml")
        if not xml_content:
            self.request.response.setStatus(400)
            return {"error": "Missing 'xml' payload"}

        name = data.get("name") or "plone-deployment"
        if not name.endswith((".bpmn", ".dmn", ".form")):
            # Default to bpmn if no extension is provided
            name = f"{name}.bpmn"

        try:
            with camunda_client() as client:
                result = deploy_process(client, name, xml_content)
            return {"status": "deployed", "result": result}
        except requests.HTTPError as e:
            # The engine rejected the deployment. Its own status and body say
            # why -- most often a modelling error the author can fix, such as
            # a missing history time to live. Collapsing all of that into a
            # bare 500 leaves the modeler's "Deploy" button unable to tell the
            # user anything actionable.
            response = e.response
            status = response.status_code if response is not None else 500
            self.request.response.setStatus(status if 400 <= status < 600 else 500)
            detail = {"error": str(e)}
            if response is not None:
                detail["status"] = status
                try:
                    detail["engine"] = response.json()
                except ValueError:
                    detail["engine"] = response.text[:2000]
            return detail
        except Exception:
            # Do not echo internal exception text (paths, connection
            # strings) back to the client; log it and return a generic
            # message. Deliberate, actionable errors are returned above.
            logger.exception("Unexpected error in %s", type(self).__name__)
            self.request.response.setStatus(500)
            return {"error": "Unexpected error; see the Plone log for details."}
