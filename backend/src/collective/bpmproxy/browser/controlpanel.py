from Products.Five.browser import BrowserView


class DeploymentsControlPanel(BrowserView):
    """View for BPMN/DMN Deployments Control Panel"""

    def __call__(self):
        self.request.set("bpmproxy_modeler_required", True)
        return self.index()
