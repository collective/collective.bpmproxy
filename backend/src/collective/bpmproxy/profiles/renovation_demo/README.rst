Renovation-project demo profile
================================

Install this profile manually after installing the main
``collective.bpmproxy`` profile. It adds a folderish ``Renovation Project``
type with the ``BPM process context`` behavior, a stateful workflow for the
project's lifecycle, and three Camunda/Operaton groups used as candidate
groups on the demo's BPMN processes: ``Renovation Owners``,
``Renovation Contractors`` and ``Renovation Inspectors``.

The project's workflow has five states: ``drafting_plan`` -> ``plan_review``
-> ``in_progress`` -> ``final_review`` -> ``closed``. Only the first
transition, ``submit-plan``, is triggered manually from Plone's workflow
menu. Every other transition (``approve-plan``, ``reject-plan``,
``submit-for-final-review``, ``reject-final-review``, ``close-project``) is
driven by Camunda, through content rules that broadcast a BPMN signal
scoped to the project's UUID on each Plone-side transition, and an external
task worker (see ``examples/renovation-bot/``) that performs the matching
Plone-side transition back once each phase's review completes.

Deploy the three BPMN processes under ``examples/renovation-project/`` (and
their ``.form`` files) to Operaton, and run the ``renovation-bot`` purjo
worker (``examples/renovation-bot/``) against the same engine, before
exercising the demo project created by this profile
(``renovation-project-demo``).

Sub-content uses built-in Plone types directly inside the project:
``Document``/``Image``/``File`` for the plan and drawings, and a
``Document`` tagged "Work Log" added directly into the project (not into a
sub-folder -- see the BPM task auto-complete mechanism in
``subscribers/tasks.py``, which matches on the *direct* parent's UUID) to
log completed work. Extra-work request evidence uses this add-on's
task-scoped ``Bpm Attachments``/``Bpm Attachment`` mechanism.
