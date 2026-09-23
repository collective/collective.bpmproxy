"""Shared test helpers, not collected as tests themselves."""

from contextlib import contextmanager
from plone.dexterity.interfaces import IDexterityFTI
from plone.dexterity.schema import SCHEMA_CACHE
from zope.component import queryUtility


@contextmanager
def process_context_behavior_enabled(type_name="Folder"):
    """Temporarily add the process_context behavior to a type's FTI.

    Used to exercise the behavior against a type other than Bpm Proxy,
    which already provides it by composing IProcessContextBehavior
    directly. Restores the FTI's original behaviors on exit.

    plone.dexterity caches each type's behavior list (SCHEMA_CACHE, keyed
    by portal_type) separately from the FTI object itself, and only a
    GenericSetup import or a ZMI edit invalidates it -- a direct attribute
    assignment like this one does not -- so the cache has to be invalidated
    by hand on both sides of the change.
    """
    fti = queryUtility(IDexterityFTI, name=type_name)
    original = fti.behaviors
    fti.behaviors = tuple(original) + ("collective.bpmproxy.process_context",)
    SCHEMA_CACHE.invalidate(fti)
    try:
        yield
    finally:
        fti.behaviors = original
        SCHEMA_CACHE.invalidate(fti)
