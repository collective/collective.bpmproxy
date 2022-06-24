# -*- coding: utf-8 -*-
from collective.bpmproxy.interfaces import (
    ATTACHMENTS_DEFAULT_TYPE,
    CAMUNDA_ADMIN_GROUP,
    PLONE_ADMIN_GROUP,
)
from Products.CMFPlone.interfaces import INonInstallable
from zope.interface import implementer

import plone.api


@implementer(INonInstallable)
class HiddenProfiles(object):
    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller."""
        return [
            "collective.bpmproxy:uninstall",
        ]


def post_install(context):
    """Post install script"""
    # Create "camunda-admin" to allow Plone admins to access Camunda controlled resources
    if not plone.api.group.get(CAMUNDA_ADMIN_GROUP):
        plone.api.group.create(
            CAMUNDA_ADMIN_GROUP,
            "Camunda Administrators",
            "Camunda administrators have full access to all Camunda resources through Plone",
            groups=[PLONE_ADMIN_GROUP],
        )
    # Add BPM Attachment to view in listings types
    types = plone.api.portal.get_registry_record(
        "plone.types_use_view_action_in_listings", default=[]
    )
    if ATTACHMENTS_DEFAULT_TYPE not in types:
        types.append(ATTACHMENTS_DEFAULT_TYPE)
        plone.api.portal.set_registry_record(
            "plone.types_use_view_action_in_listings", types
        )


def uninstall(context):
    """Uninstall script"""
    # Do something at the end of the uninstallation of this package.
