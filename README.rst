.. This README is meant for consumption by humans and pypi. Pypi can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide.html
   This text does not appear on pypi or github. It is a comment.

.. .. image:: https://travis-ci.org/collective/collective.bpmproxy.svg?branch=master
    :target: https://travis-ci.org/collective/collective.bpmproxy

.. .. image:: https://coveralls.io/repos/github/collective/collective.bpmproxy/badge.svg?branch=master
    :target: https://coveralls.io/github/collective/collective.bpmproxy?branch=master
    :alt: Coveralls

.. .. image:: https://img.shields.io/pypi/v/collective.bpmproxy.svg
    :target: https://pypi.python.org/pypi/collective.bpmproxy/
    :alt: Latest Version

.. .. image:: https://img.shields.io/pypi/status/collective.bpmproxy.svg
    :target: https://pypi.python.org/pypi/collective.bpmproxy
    :alt: Egg Status

.. .. image:: https://img.shields.io/pypi/pyversions/collective.bpmproxy.svg?style=plastic   :alt: Supported - Python Versions

.. .. image:: https://img.shields.io/pypi/l/collective.bpmproxy.svg
    :target: https://pypi.python.org/pypi/collective.bpmproxy/
    :alt: License


===================
collective.bpmproxy
===================

Publish BPMN 2.0 processes from Camunda Platform 7, and interact with the processes with Camunda Forms or BPMN signals.

The add-on requires its bundled Camunda Platform 7 with a special authentication plugin authorizing requests from Plone as their initiating Plone users. See the project repository for details.


Features
--------

* A custom content-type, "BPM Proxy" to publish an existing process with forms from a configured Camunda Platform 7 (later just "C7") instance as a CMS page with "sub pages" for currently open tasks in running instances of that process.

* A portlet to list all tasks available in every running process on the configured C7 instance. (Or just the tasks related to the current Plone page.)

* A Portlet to trigger BPMN signals at the configured C7 instance from Plone.

* A content-rule action to broadcast BPMN signals events at the configured C7 instance from configured events at Plone.

* Support to show related available user task forms also for pages of other types than BPM Proxy.

* Support to map ++add++ and ++edit++ forms as user task forms and complete user task from their completion.


.. Examples
.. --------

.. TODO

Documentation
-------------

.. Full documentation for end users can be found in the "docs" folder, and is also available online at http://docs.plone.org/foo/bar

Generate private key for Plone-Camunda JWT-authentication::

    $ openssl genpkey -algorithm ed25519 -out ec-ed25519-priv-key.pem

Generate public key for Plone-Camunda JWT-authentication::

    $ openssl ec -in ec-ed25519-priv-key.pem -pubout > ec-ed25519-pub-key.pem

Start bundled Camunda application with PostgreSQL backend on docker compose with:

    $ docker-compose up

Start Plone with environment variables::

    CAMUNDA_API_URL=http://localhost:8081/engine-rest CAMUNDA_API_PRIVATE_KEY=$(pwd)/ec-ed25519-priv-key.pem ./bin/instance fg


.. Translations
.. ------------

.. This product has been translated into

.. .. - Klingon (thanks, K'Plai)


Installation
------------

Install collective.bpmproxy by adding it to your buildout::

    [buildout]

    ...

    eggs =
        collective.bpmproxy


and then running ``bin/buildout``


Contribute
----------

- Issue Tracker: https://github.com/collective/collective.bpmproxy/issues
- Source Code: https://github.com/collective/collective.bpmproxy

..  Documentation: https://docs.plone.org/foo/bar


.. Support
.. -------

.. If you are having issues, please let us know.
.. We have a mailing list located at: project@example.com


License
-------

The project is licensed under the GPLv2.
