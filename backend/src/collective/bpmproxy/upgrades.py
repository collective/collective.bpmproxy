from plone.registry.interfaces import IRegistry
from zope.component import getUtility
import logging


logger = logging.getLogger(__name__)

# Bundle records are named "<prefix>.<field>", where <field> is a single
# IBundleRegistry field name ("enabled", "jscompilation", ...). Renamed bundles
# nest under the old name -- "plone.bundles/collective.bpmproxy" is a prefix of
# "plone.bundles/collective.bpmproxy.form" -- so removal has to match the field
# part exactly. (This is also why registry.collectionOfInterface()'s __delitem__
# must not be used here: it deletes the whole key range from "<prefix>." up to
# "<prefix>/", and since "." sorts before "/" that range swallows the renamed
# bundles as well.)
LEGACY_BUNDLE_PREFIX = "plone.bundles/collective.bpmproxy"


def remove_records(prefix, nested=False):
    """Remove the registry records of one bundle or resource.

    With nested=False only "<prefix>.<field>" records are removed, leaving
    records of bundles whose name merely starts with prefix alone.
    """
    registry = getUtility(IRegistry)
    for name in list(registry.records.keys()):
        if name == prefix:
            pass
        elif name.startswith(prefix + "."):
            if not nested and "." in name[len(prefix) + 1 :]:
                continue
        else:
            continue
        del registry.records[name]
        logger.info("Removed obsolete registry record %s", name)


def remove_legacy_bundle_records(context=None):
    """Remove the pre-1001 "collective.bpmproxy" bundle.

    It was split into the "collective.bpmproxy.form" and
    "collective.bpmproxy.diagram" bundles and points at a compilation
    (bundle.js) that no longer exists.
    """
    remove_records(LEGACY_BUNDLE_PREFIX)
