import "./index.css";
import ModelingModule from "bpmn-js/lib/features/modeling";
import NavigatedViewer from "bpmn-js/lib/NavigatedViewer";
import { ready } from "./common";

// bpmn-js types viewer.get() as unknown; declare the small surface used here.
type Canvas = { zoom: (mode: string) => void };
type ElementRegistry = { get: (id: string) => unknown };
type Modeling = {
  setColor: (element: unknown, attrs: { stroke: string; fill: string }) => void;
};

ready(async () => {
  const diagram = document.getElementById("collective-bpmproxy-diagram");
  if (!diagram || !diagram.dataset.bpmn20_xml) {
    return;
  }

  // The diagram often starts inside a hidden tab, where the container has no
  // layout and "fit-viewport" would zoom to a zero-sized box. Defer rendering
  // until the container is actually visible.
  let rendered = false;
  let visibility: MutationObserver | undefined;

  const render = async () => {
    if (rendered || diagram.offsetParent === null) {
      return;
    }
    // Latch before awaiting so concurrent mutations cannot start a second
    // render into the same container, and stop observing: this is a one-shot.
    rendered = true;
    visibility?.disconnect();

    const viewer = new NavigatedViewer({
      additionalModules: [ModelingModule],
      container: "#collective-bpmproxy-diagram",
    });
    try {
      await viewer.importXML(diagram.dataset.bpmn20_xml);
      const canvas = viewer.get("canvas") as Canvas;
      const modeling = viewer.get("modeling") as Modeling;
      const registry = viewer.get("elementRegistry") as ElementRegistry;
      canvas.zoom("fit-viewport");
      if (diagram.dataset.element) {
        const element = registry.get(diagram.dataset.element);
        modeling.setColor(element, { stroke: "#000000", fill: "#FFFF00" });
      }
    } catch (err) {
      // Re-rendering would fail identically for the same XML, so there is
      // nothing to retry; make the reason visible instead.
      console.error("collective.bpmproxy: failed to render BPMN diagram", err);
    }
  };

  const tabs = diagram.closest(".autotabs") || document.body;
  visibility = new MutationObserver(render);
  visibility.observe(tabs, {
    attributes: true,
    subtree: true,
    attributeFilter: ["class", "style", "aria-hidden"],
  });
  render();
});
