// Control panel bundle: the BPMN modeler, the DMN modeler and the form
// playground are only ever used together on @@bpmproxy-modeler-controlpanel,
// and each of them no-ops when its container element is missing.
import "./modeler";
import "./dmn";
import "./form-playground";
