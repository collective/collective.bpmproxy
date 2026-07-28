"""Pytest fixtures for collective.bpmproxy.

The classic zope.testrunner layers from ``collective.bpmproxy.testing`` are
exposed twice:

* ``gocept.pytestlayer`` (installed via the ``test`` extra) lets pytest run
  the existing ``unittest``-style tests with their ``layer`` attributes.
* ``pytest_plone.fixtures_factory`` provides pytest fixtures (``portal``,
  ``integration``, ``functional``, ...) for new pytest-style tests.
"""

from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING
from collective.bpmproxy.testing import COLLECTIVE_BPMPROXY_INTEGRATION_TESTING
from pytest_plone import fixtures_factory


globals().update(
    fixtures_factory(
        (
            (COLLECTIVE_BPMPROXY_FUNCTIONAL_TESTING, "functional"),
            (COLLECTIVE_BPMPROXY_INTEGRATION_TESTING, "integration"),
        )
    )
)
