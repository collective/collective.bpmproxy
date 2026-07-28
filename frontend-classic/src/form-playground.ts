import { FormPlayground } from '@bpmn-io/form-js';
import '@bpmn-io/form-js/dist/assets/form-js.css';
import '@bpmn-io/form-js/dist/assets/form-js-playground.css';
import '@bpmn-io/form-js/dist/assets/form-js-editor.css';
import './index.css';

import Split from 'split.js';

function init() {
  const container = document.getElementById('form-playground-container');
  if (!container) {
    return;
  }

  const emptyForm = {
    components: [],
    schemaVersion: 8,
    type: "default",
    id: "Form_1"
  };

  const playground = new FormPlayground({
    container: container,
    schema: emptyForm,
    data: {}
  });

  const onRendered = () => {
    const root = container.querySelector<HTMLElement>('.fjs-pgl-root');
    const palette = container.querySelector<HTMLElement>('.fjs-pgl-palette-container');
    const main = container.querySelector<HTMLElement>('.fjs-pgl-main');
    const properties = container.querySelector<HTMLElement>('.fjs-pgl-properties-container');
    const sections = main?.querySelectorAll<HTMLElement>('.fjs-pgl-section');

    const formDefinitionSection = Array.from(sections || []).find((s) => s.textContent?.includes('Form Definition'));
    const formPreviewSection = Array.from(sections || []).find((s) => s.textContent?.includes('Form Preview'));
    const formInputSection = Array.from(sections || []).find((s) => s.textContent?.includes('Form Input'));
    const formOutputSection = Array.from(sections || []).find((s) => s.textContent?.includes('Form Output'));

    if (root && palette && main && properties && formDefinitionSection && formPreviewSection && formInputSection && formOutputSection) {
      main.remove();

      const definitionColumn = document.createElement('div');
      definitionColumn.classList.add('column');
      definitionColumn.appendChild(formDefinitionSection);
      definitionColumn.appendChild(formInputSection);

      const previewColumn = document.createElement('div');
      previewColumn.classList.add('column');
      previewColumn.appendChild(formPreviewSection);
      previewColumn.appendChild(formOutputSection);

      const resizableContainer = document.createElement('div');
      resizableContainer.classList.add('resizable-container');
      resizableContainer.style.display = 'flex';
      resizableContainer.style.flexDirection = 'row';
      resizableContainer.style.width = '100%';
      
      resizableContainer.appendChild(definitionColumn);
      resizableContainer.appendChild(previewColumn);
      resizableContainer.appendChild(properties);

      root.insertBefore(resizableContainer, palette.nextSibling);

      Split([definitionColumn, previewColumn, properties], {
        sizes: [40, 40, 20],
        minSize: [200, 200, 200],
        gutterSize: 8,
        cursor: 'col-resize',
      });

      Split([formDefinitionSection, formInputSection], {
        direction: 'vertical',
        sizes: [50, 50],
        minSize: 100,
        gutterSize: 8,
        cursor: 'row-resize',
      });

      Split([formPreviewSection, formOutputSection], {
        direction: 'vertical',
        sizes: [50, 50],
        minSize: 100,
        gutterSize: 8,
        cursor: 'row-resize',
      });
    }

    playground.off('formPlayground.rendered', onRendered);
  };

  playground.on('formPlayground.rendered', onRendered);

  (window as any).formPlayground = playground;

  // UI logic for JSON toggle and Deploy
  const designBtn = document.getElementById('form-design-btn');
  const jsonBtn = document.getElementById('form-json-btn');
  const designView = document.getElementById('form-design-view');
  const jsonView = document.getElementById('form-json-view');
  const jsonEditor = document.getElementById('form-json-editor') as HTMLTextAreaElement;
  const deployBtn = document.getElementById('form-deploy-btn');

  if (designBtn && jsonBtn && designView && jsonView && jsonEditor && deployBtn) {
    designBtn.addEventListener('click', () => {
      // Switch to design
      jsonBtn.classList.remove('active');
      designBtn.classList.add('active');
      jsonView.style.display = 'none';
      designView.style.display = 'block';
      
      const jsonStr = jsonEditor.value;
      if (jsonStr) {
        try {
          const schema = JSON.parse(jsonStr);
          playground.getEditor().importSchema(schema);
        } catch (err) {
          console.error('Failed to import JSON', err);
          alert('Invalid JSON');
        }
      }
    });

    jsonBtn.addEventListener('click', () => {
      // Switch to JSON
      designBtn.classList.remove('active');
      jsonBtn.classList.add('active');
      designView.style.display = 'none';
      jsonView.style.display = 'block';

      try {
        const schema = playground.getSchema();
        jsonEditor.value = JSON.stringify(schema, null, 2);
      } catch (err) {
        console.error('Failed to save JSON', err);
      }
    });

    deployBtn.addEventListener('click', async () => {
      const name = prompt('Deployment Name:', 'form.form');
      if (!name) return;

      try {
        let jsonToDeploy;
        if (jsonView.style.display !== 'none') {
          jsonToDeploy = jsonEditor.value;
        } else {
          const schema = playground.getSchema();
          jsonToDeploy = JSON.stringify(schema, null, 2);
        }

        const portal_url = document.body.dataset.portalUrl || '';
        const res = await fetch(portal_url + '/@bpmproxy-deploy', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({ name: name, xml: jsonToDeploy })
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
