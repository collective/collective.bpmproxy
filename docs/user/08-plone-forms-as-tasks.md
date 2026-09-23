# Plone forms as task forms

A user task does not have to be answered with a Camunda form. If its
`form_key` names a Plone form, Plone shows that form instead, and completing it
completes the task.

| `form_key` | What the user sees |
| --- | --- |
| `@@edit` | The edit form of the page the task belongs to |
| `++add++Document` | The add form for a Document in that container |

Opening such a task redirects to the Plone form. When the user saves:

- `++add++<Type>` — adding an object of that type in that container completes
  the task;
- `@@edit` — modifying the object completes the task.

This is how a process asks for real content rather than form data: the step
"write the announcement" becomes an ordinary Plone add form, and the process
continues once the announcement exists.

Both completions are deferred to transaction commit, so a failed save leaves
the task open.
