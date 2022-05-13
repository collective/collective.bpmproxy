# -*- coding: utf-8 -*-
from __future__ import print_function
import time
import generic_camunda_client
from generic_camunda_client.rest import ApiException
from pprint import pprint

from collective.bpmproxy import _
from Products.Five.browser import BrowserView


# from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

# Defining the host is optional and defaults to http://localhost:8080/engine-rest
# See configuration.py for a list of all supported configuration parameters.
configuration = generic_camunda_client.Configuration(
    host = "http://localhost:8081/engine-rest"
)


class BpmProxyStartFormView(BrowserView):
    # If you want to define a template here, please remove the template from
    # the configure.zcml registration of this view.
    # template = ViewPageTemplateFile('bpm_proxy_start_form_view.pt')

    def __call__(self):
        # Implement your own actions:
        if self.request.method == "POST" \
                and self.request.form.get("action") == "start":
            self.msg = _(u'Started')
            # Enter a context with an instance of the API client
            with generic_camunda_client.ApiClient(configuration) as api_client:
                # Create an instance of the API class
                api_instance = generic_camunda_client.ProcessDefinitionApi(api_client)
                key = self.context.process_definition_key
                start_process_instance_dto = {"variables":{"aVariable":{"value":"aStringValue","type":"String"},"anotherVariable":{"value":True,"type":"Boolean"}},"businessKey":"myBusinessKey"} # StartProcessInstanceDto |  (optional)

                try:
                    # Start Instance
                    api_response = api_instance.start_process_instance_by_key(key, start_process_instance_dto=start_process_instance_dto)
                    pprint(api_response)
                except ApiException as e:
                    print("Exception when calling ProcessDefinitionApi->start_process_instance_by_key: %s\n" % e)
        else:
            self.msg = _(u'A small message')
        return self.index()
