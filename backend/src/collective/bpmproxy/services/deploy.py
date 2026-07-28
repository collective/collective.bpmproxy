from collective.bpmproxy.client import camunda_client
from collective.bpmproxy.client import deploy_process
from plone.restapi.services import Service
import json


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
        except Exception as e:
            self.request.response.setStatus(500)
            return {"error": str(e)}
