import "./index.css";
import ModelingModule from "bpmn-js/lib/features/modeling";
import NavigatedViewer from "bpmn-js/lib/NavigatedViewer";
import { ready } from "./common";

ready(async () => {
  const diagram = document.getElementById("collective-bpmproxy-diagram");
  if (diagram && diagram.dataset.bpmn20_xml) {
    const viewer = new NavigatedViewer({
      additionalModules: [ModelingModule],
      container: "#collective-bpmproxy-diagram",
    });
    try {
      const { warnings } = await viewer.importXML(diagram.dataset.bpmn20_xml);
      const canvas = viewer.get("canvas");
      const modeling = viewer.get("modeling");
      const registry = viewer.get("elementRegistry");
      canvas.zoom("fit-viewport");
      if (!!diagram.dataset.element) {
          const element = registry.get(diagram.dataset.element);
          modeling.setColor(element, { stroke: "#000000", fill: "#FFFF00" });
      }
    } catch (err) {
      console.log("error rendering", err);
    }
  }
});
