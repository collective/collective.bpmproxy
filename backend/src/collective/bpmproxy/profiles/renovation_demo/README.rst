Renovation case-management demo profile
========================================

Install this profile after installing the main ``collective.bpmproxy``
profile. It adds a plain folderish ``Renovation Project`` case type, a Plone
workflow, the case-specific content rules, and a Tasks portlet assignment for
the ``Renovation Project`` content type. It does not create users, groups, or
cases; ``scripts/bootstrap_renovation_demo.py`` creates those disposable demo
fixtures.

Creating a ``Renovation Project`` emits the ``renovation-case-created`` signal
and starts ``examples/renovation-project/renovation-case.bpmn``. The main case
process waits for the case to close. Direct child Documents and the extra-work
portlet start independent correlated event subprocesses; all messages include
the case UUID as the ``caseUuid`` correlation key.

The case workflow is simply ``open`` -> ``closed``. The case manager advances
it independently of the BPMN event subprocesses.

The case allows ``Document`` children. A direct Document creation delivers
``renovation-case-document-created`` to the main process's non-interrupting
event subprocess, which calls the separate ``renovation-page-review`` process.
The page review process has its own business key containing the case and page
UUIDs, while remaining a child in the Operaton process tree.

Deploy the case BPMN and forms from ``examples/renovation-project/`` to
Operaton. No external task worker is required for this example.
