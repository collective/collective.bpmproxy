# -*- coding: utf-8 -*-
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import (
    applyProfile,
    FunctionalTesting,
    IntegrationTesting,
    PloneSandboxLayer,
)
from plone.testing import z2

import collective.bpmproxy


class CollectiveBpmproxyLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.restapi

        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=collective.bpmproxy)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "collective.bpmproxy:default")


COLLECTIVE_BPMPROXY_FIXTURE = CollectiveBpmproxyLayer()


COLLECTIVE_BPMPROXY_INTEGRATION_TESTING = IntegrationTesting(
    bases=(COLLECTIVE_BPMPROXY_FIXTURE,),
    name="CollectiveBpmproxyLayer:IntegrationTesting",
)


COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(COLLECTIVE_BPMPROXY_FIXTURE,),
    name="CollectiveBpmproxyLayer:FunctionalTesting",
)


COLLECTIVE_BPMPROXY_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        COLLECTIVE_BPMPROXY_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name="CollectiveBpmproxyLayer:AcceptanceTesting",
)
