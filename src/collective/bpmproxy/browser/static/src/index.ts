import { Form } from '@bpmn-io/form-js-viewer';

import '@bpmn-io/form-js-viewer/dist/assets/form-js.css';

const ready = async (fn) => {
  if (document.readyState != 'loading'){
    await fn();
  } else {
    document.addEventListener('DOMContentLoaded', fn);
  }
}

ready(async() => {
  const inputForm = document.getElementById("collective-bpmproxy-form");
  const submitForm = document.getElementById("collective-bpmproxy-form-submit");
  const submitInput = document.getElementById("collective-bpmproxy-form-data");
  if (!!inputForm && !!submitForm && !!submitInput) {
    const form = new Form({ container: inputForm });
    const schema = JSON.parse(inputForm.dataset.schema);
    const data = JSON.parse(inputForm.dataset.data || "{}");
    await form.importSchema(schema, data);
    form.on('submit', (event) => {
      if (Object.keys(event.errors).length === 0) {
        (submitInput as HTMLInputElement).value = JSON.stringify(event.data);
        (submitForm as HTMLFormElement).submit();
      }
   });
  }
});
