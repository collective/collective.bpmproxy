import BpmnModeler from 'bpmn-js/lib/Modeler';
import { BpmnPropertiesPanelModule, BpmnPropertiesProviderModule, CamundaPlatformPropertiesProviderModule } from 'bpmn-js-properties-panel';
import camundaModdleDescriptor from 'camunda-bpmn-moddle/resources/camunda.json';
import Split from 'split.js';

// Import CSS
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn-embedded.css';
import '@bpmn-io/properties-panel/assets/properties-panel.css';
import './index.css';

function init() {
  const container = document.getElementById('bpmn-modeler-container');
  const panel = document.getElementById('bpmn-properties-panel');
  if (!container || !panel) {
    return;
  }

  // Set up split pane
  Split(['#bpmn-modeler-container', '#bpmn-properties-panel'], {
    sizes: [75, 25],
    minSize: [300, 250],
    gutterSize: 8,
    cursor: 'col-resize'
  });

  const modeler = new BpmnModeler({
    container: container,
    propertiesPanel: {
      parent: panel
    },
    additionalModules: [
      BpmnPropertiesPanelModule,
      BpmnPropertiesProviderModule,
      CamundaPlatformPropertiesProviderModule
    ],
    moddleExtensions: {
      camunda: camundaModdleDescriptor
    }
  });

  const emptyBpmn = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="_BPMNShape_StartEvent_2" bpmnElement="StartEvent_1">
        <dc:Bounds x="152" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;

  modeler.importXML(emptyBpmn).catch(err => {
    console.error('Failed to render empty BPMN', err);
  });

  // Expose modeler to window for external interactions (e.g. from the Plone template)
  (window as any).bpmnModeler = modeler;

  // UI logic for XML toggle and Deploy
  const designBtn = document.getElementById('bpmn-design-btn');
  const xmlBtn = document.getElementById('bpmn-xml-btn');
  const designView = document.getElementById('bpmn-design-view');
  const xmlView = document.getElementById('bpmn-xml-view');
  const xmlEditor = document.getElementById('bpmn-xml-editor') as HTMLTextAreaElement;
  const deployBtn = document.getElementById('bpmn-deploy-btn');

  if (designBtn && xmlBtn && designView && xmlView && xmlEditor && deployBtn) {
    designBtn.addEventListener('click', async () => {
      // Switch to design
      xmlBtn.classList.remove('active');
      designBtn.classList.add('active');
      xmlView.style.display = 'none';
      designView.style.display = 'flex';
      
      const xml = xmlEditor.value;
      if (xml) {
        try {
          await modeler.importXML(xml);
        } catch (err) {
          console.error('Failed to import XML', err);
          alert('Invalid XML');
        }
      }
    });

    xmlBtn.addEventListener('click', async () => {
      // Switch to XML
      designBtn.classList.remove('active');
      xmlBtn.classList.add('active');
      designView.style.display = 'none';
      xmlView.style.display = 'block';

      try {
        const { xml } = await modeler.saveXML({ format: true });
        xmlEditor.value = xml || '';
      } catch (err) {
        console.error('Failed to save XML', err);
      }
    });

    deployBtn.addEventListener('click', async () => {
      const name = prompt('Deployment Name:', 'process.bpmn');
      if (!name) return;

      try {
        let xmlToDeploy;
        if (xmlView.style.display !== 'none') {
          xmlToDeploy = xmlEditor.value;
        } else {
          const { xml } = await modeler.saveXML({ format: true });
          xmlToDeploy = xml;
        }

        const portal_url = document.body.dataset.portalUrl || '';
        const res = await fetch(portal_url + '/@bpmproxy-deploy', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({ name: name, xml: xmlToDeploy })
        });
        
        if (res.ok) {
          alert('Deployed successfully!');
          const fetchDeployments = (window as any).fetchDeployments;
          if (fetchDeployments) fetchDeployments();
        } else {
          const error = await res.json();
          alert('Deployment failed: ' + JSON.stringify(error));
        }
      } catch (err) {
        console.error('Deployment error', err);
        alert('Deployment error');
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
