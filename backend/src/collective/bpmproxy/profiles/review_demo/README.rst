collective.bpmproxy:review_demo
==============================

GenericSetup extension profile for the parallel review process example.

When applied, it registers the required Plone content rules:
- ``plone-content-submitted-to-review``: Sends a BPMN message when content is submitted for review (transition ``submit``).
- ``plone-content-retracted``: Dispatches BPMN signal when content is retracted (transition ``retract``).

Both rules are automatically assigned and enabled on the Plone site root.
The post-install handler also ensures the ``Reviewers`` group and a ``review-bot`` service account exist.

.. warning::
   Unlike ``renovation_demo``, this profile does not scope its rules to a
   dedicated content type or workflow. It hooks the ``submit``/``retract``
   transitions of Plone's stock Simple Publication Workflow, which is the
   same workflow ordinary content (Documents, News Items, etc.) uses by
   default. Applying this profile to a site with existing content therefore
   starts the example review process for *every* normal "submit for review"
   / "retract" action site-wide, not just demo content. Only install it on
   a throwaway or dedicated demo site.
