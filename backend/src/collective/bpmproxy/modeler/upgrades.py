from collective.bpmproxy.upgrades import remove_records


# Replaced in 1004 by the single "plone.bundles/collective.bpmproxy.modeler"
# bundle; reimporting the profile does not remove the old records.
LEGACY_PREFIXES = (
    "plone.bundles/collective-bpmproxy-modeler",
    "plone.resources/collective-bpmproxy-modeler",
    "plone.resources/collective-bpmproxy-dmn",
    "plone.resources/collective-bpmproxy-form-playground",
)


def remove_legacy_modeler_records(context=None):
    """Remove the pre-1004 resource and bundle records."""
    for prefix in LEGACY_PREFIXES:
        remove_records(prefix, nested=True)
