import "@bpmn-io/form-js-viewer/dist/assets/form-js.css";
import "./index.css";
import { Form } from "@bpmn-io/form-js-viewer";
import { ready } from "./common";

ready(async () => {
  const inputForm = document.getElementById("collective-bpmproxy-form");
  const submitForm = document.getElementById("collective-bpmproxy-form-submit") as HTMLFormElement;
  const submitInput = document.getElementById("collective-bpmproxy-form-data") as HTMLInputElement;
  if (!!inputForm && !!submitForm && !!submitInput) {
    const form = new Form({ container: inputForm });
    const schema = JSON.parse(inputForm.dataset.schema || "{}");
    const data = JSON.parse(inputForm.dataset.data || "{}");
    await form.importSchema(schema, data);
    form.on("submit", (event: any) => {
      if (Object.keys(event.errors).length === 0) {
        submitInput.value = JSON.stringify(event.data);
        submitForm.submit();
      }
    });
  }
});
