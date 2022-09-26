import "@bpmn-io/form-js-viewer/dist/assets/form-js.css";

import { Form } from "@bpmn-io/form-js-viewer";
import ModelingModule from "bpmn-js/lib/features/modeling";
import NavigatedViewer from "bpmn-js/lib/NavigatedViewer";

const ready = async (fn) => {
  if (document.readyState != "loading") {
    setTimeout(async () => {
      await fn();
    }, 0);
  } else {
    document.addEventListener("DOMContentLoaded", fn);
  }
};

ready(async () => {
  const inputForm = document.getElementById("collective-bpmproxy-form");
  const submitForm = document.getElementById("collective-bpmproxy-form-submit");
  const submitInput = document.getElementById("collective-bpmproxy-form-data");
  if (!!inputForm && !!submitForm && !!submitInput) {
    const form = new Form({ container: inputForm });
    const schema = JSON.parse(inputForm.dataset.schema);
    const data = JSON.parse(inputForm.dataset.data || "{}");
    await form.importSchema(schema, data);
    form.on("submit", (event) => {
      if (Object.keys(event.errors).length === 0) {
        (submitInput as HTMLInputElement).value = JSON.stringify(event.data);
        (submitForm as HTMLFormElement).submit();
      }
    });
  }

  setTimeout(async () => {
      const diagram = document.getElementById("collective-bpmproxy-diagram");
      if (diagram && diagram.dataset.bpmn20_xml) {
          const viewer = new NavigatedViewer({
              additionalModules: [ModelingModule],
              container: "#collective-bpmproxy-diagram",
          });
          try {
              const { warnings } = await viewer.importXML(diagram.dataset.bpmn20_xml);
              setTimeout(() => {
                  const canvas = viewer.get("canvas");
                  canvas.zoom("fit-viewport");
              }, 100);
              if (!!diagram.dataset.element) {
                  setTimeout(() => {
                      const registry = viewer.get("elementRegistry");
                      const element = registry.get(diagram.dataset.element);
                      const modeling = viewer.get("modeling");
                      modeling.setColor(element, {stroke: "#000000", fill: "#FFFF00"});
                  }, 100);
              }
          } catch (err) {
              console.log("error rendering", err);
          }
      }
  }, 100);

});
