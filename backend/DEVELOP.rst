Developing collective.bpmproxy
==============================

The development environment is managed with `devenv <https://devenv.sh>`_.

Two terminals, both starting with ``make shell`` (an alias for ``devenv
shell``; generates the JWT signing keys on first run and exports
``CAMUNDA_API_URL`` / ``CAMUNDA_API_PRIVATE_KEY``)::

    # Terminal 1: start the backing services (PostgreSQL, Keycloak, Mailpit, Operaton)
    $ make shell
    $ make services

    # Terminal 2: install and start Plone in the foreground
    $ make shell
    $ make install
    $ make start


Running tests
-------------

::

    $ make test

or directly (dependencies are managed by `uv <https://docs.astral.sh/uv/>`_)::

    $ uv run pytest

Linting and formatting (Ruff)::

    $ make lint
    $ make format

Run the tests against all supported Python versions with tox (this applies
Plone's official constraints for the 6.1 line independently of ``uv.lock``)::

    $ tox

After changing dependencies in ``pyproject.toml``, regenerate the lockfile::

    $ make lock


Operaton application
--------------------

The custom Operaton Spring Boot application lives in ``fixture/operaton/``.
See its ``Makefile`` for build targets (``make build``, ``make test``,
``make dist``). After changing ``pom.xml``, regenerate the Nix lockfile::

    $ cd fixture/operaton
    $ nix develop --command make mvn2nix-lock.json
