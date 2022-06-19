# -*- coding: utf-8 -*-
from collective.bpmproxy.interfaces import CAMUNDA_ADMIN_GROUP, PLONE_ADMIN_GROUP
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


def uninstall(context):
    """Uninstall script"""
    # Do something at the end of the uninstallation of this package.
