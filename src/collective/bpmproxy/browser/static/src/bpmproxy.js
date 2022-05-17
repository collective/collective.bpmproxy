import { Form } from '@bpmn-io/form-js';

const ready = async (fn) => {
  if (document.readyState != 'loading'){
    await fn();
  } else {
    document.addEventListener('DOMContentLoaded', fn);
  }
}

ready(async() => {
  const el = document.getElementById("collective-bpmproxy-form");
  const el2 = document.getElementById("collective-bpmproxy-form-submit");
  const el3 = document.getElementById("collective-bpmproxy-form-data");
  if (!!el && !!el2 && !!el3) {
    const form = new Form({ container: el });
    const schema = JSON.parse(el.dataset.schema);
    const data = JSON.parse(el.dataset.data || "{}");
    await form.importSchema(schema, data);
    form.on('submit', (event) => {
      if (Object.keys(event.errors).length === 0) {
        el3.value = JSON.stringify(event.data);
        el2.submit();
      }
   });
  }
});
