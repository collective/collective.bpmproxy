import DmnModeler from 'dmn-js/lib/Modeler';
import { DmnPropertiesPanelModule, DmnPropertiesProviderModule, CamundaPropertiesProviderModule } from 'dmn-js-properties-panel';
// note: camunda dmn moddle is built-in or usually not required for basic DMN in dmn-js unless specifically needed.
import Split from 'split.js';

// Import CSS
import 'dmn-js/dist/assets/diagram-js.css';
import 'dmn-js/dist/assets/dmn-js-shared.css';
import 'dmn-js/dist/assets/dmn-js-drd.css';
import 'dmn-js/dist/assets/dmn-js-decision-table.css';
import 'dmn-js/dist/assets/dmn-js-decision-table-controls.css';
import 'dmn-js/dist/assets/dmn-js-literal-expression.css';
import 'dmn-js/dist/assets/dmn-font/css/dmn.css';
import 'dmn-js-properties-panel/dist/assets/properties-panel.css';
import '@bpmn-io/properties-panel/assets/properties-panel.css';
import './index.css';

function init() {
  const container = document.getElementById('dmn-modeler-container');
  const panel = document.getElementById('dmn-properties-panel');
  if (!container || !panel) {
    return;
  }

  // Set up split pane
  Split(['#dmn-modeler-container', '#dmn-properties-panel'], {
    sizes: [75, 25],
    minSize: [300, 250],
    gutterSize: 8,
    cursor: 'col-resize'
  });

  const modeler = new DmnModeler({
    container: container,
    drd: {
      propertiesPanel: {
        parent: panel
      },
      additionalModules: [
        DmnPropertiesPanelModule,
        DmnPropertiesProviderModule,
        CamundaPropertiesProviderModule
      ]
    }
  });

  const emptyDmn = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/" id="Definitions_1" name="DRD" namespace="http://camunda.org/schema/1.0/dmn">
  <decision id="Decision_1" name="Decision 1">
    <decisionTable id="DecisionTable_1">
      <input id="Input_1">
        <inputExpression id="InputExpression_1" typeRef="string">
          <text></text>
        </inputExpression>
      </input>
      <output id="Output_1" typeRef="string" />
    </decisionTable>
  </decision>
</definitions>`;

  modeler.importXML(emptyDmn).then(() => {
    // Optionally open the decision by default
    const views = modeler.getViews();
    if (views.length > 0) {
      modeler.open(views[0]);
    }
  }).catch(err => {
    console.error('Failed to render empty DMN', err);
  });

  (window as any).dmnModeler = modeler;

  // UI logic for XML toggle and Deploy
  const designBtn = document.getElementById('dmn-design-btn');
  const xmlBtn = document.getElementById('dmn-xml-btn');
  const designView = document.getElementById('dmn-design-view');
  const xmlView = document.getElementById('dmn-xml-view');
  const xmlEditor = document.getElementById('dmn-xml-editor') as HTMLTextAreaElement;
  const deployBtn = document.getElementById('dmn-deploy-btn');

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
      const name = prompt('Deployment Name:', 'decision.dmn');
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
