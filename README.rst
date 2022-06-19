.. This README is meant for consumption by humans and pypi. Pypi can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide.html
   This text does not appear on pypi or github. It is a comment.

.. image:: https://travis-ci.org/collective/collective.bpmproxy.svg?branch=master
    :target: https://travis-ci.org/collective/collective.bpmproxy

.. image:: https://coveralls.io/repos/github/collective/collective.bpmproxy/badge.svg?branch=master
    :target: https://coveralls.io/github/collective/collective.bpmproxy?branch=master
    :alt: Coveralls

.. image:: https://img.shields.io/pypi/v/collective.bpmproxy.svg
    :target: https://pypi.python.org/pypi/collective.bpmproxy/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/status/collective.bpmproxy.svg
    :target: https://pypi.python.org/pypi/collective.bpmproxy
    :alt: Egg Status

.. image:: https://img.shields.io/pypi/pyversions/collective.bpmproxy.svg?style=plastic   :alt: Supported - Python Versions

.. image:: https://img.shields.io/pypi/l/collective.bpmproxy.svg
    :target: https://pypi.python.org/pypi/collective.bpmproxy/
    :alt: License


===================
collective.bpmproxy
===================

Tell me what your product does

Features
--------

- Can be bullet points


Examples
--------

This add-on can be seen in action at the following sites:
- Is there a page on the internet where everybody can see the features?


Documentation
-------------

Full documentation for end users can be found in the "docs" folder, and is also available online at http://docs.plone.org/foo/bar

Generate private key for Plone-Camunda JWT-authentication::

    $ openssl ecparam -name prime256v1 -genkey -noout -out ec-prime256v1-priv-key.pem

Generate public key for Plone-Camunda JWT-authentication::

    $ openssl ec -in ec-prime256v1-priv-key.pem -pubout > ec-prime256v1-pub-key.pem

Configure Plone with environment variables::

    CAMUNDA_API_URL=http://localhost:8081/engine-rest
    CAMUNDA_API_PRIVATE_KEY=ec-prime256v1-priv-key.pem

where http://localhost:8081/engine-rest is full Camunda Platform 7 REST API base URL and ec-prime256v1-priv-key.pem is full path to your Camunda-Plone JWT-authentication private key (or the value of the private key).

Configure Camunda with the usual Micronaut Camunda Platform 7 environment variables, and::

    PLONE_PUBLIC_KEY=ec-prime256v1-pub-key.pem

where ec-prime256v1-pub-key.pem is full path to your Camunda-Plone JWT-authentication public key (or the value of the private key).

Translations
------------

This product has been translated into

- Klingon (thanks, K'Plai)


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
- Documentation: https://docs.plone.org/foo/bar


Support
-------

If you are having issues, please let us know.
We have a mailing list located at: project@example.com


License
-------

The project is licensed under the GPLv2.
