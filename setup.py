# -*- coding: utf-8 -*-
"""Installer for the collective.bpmproxy package."""

from setuptools import find_packages
from setuptools import setup


long_description = '\n\n'.join([
    open('README.rst').read(),
    open('CONTRIBUTORS.rst').read(),
    open('CHANGES.rst').read(),
])


setup(
    name='collective.bpmproxy',
    version='1.0a1',
    description="Minimal Camunda Platform 7 integration for Plone",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 5.2",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.7",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords='Python Plone CMS',
    author='Asko Soukka',
    author_email='asko.soukka@iki.fi',
    url='https://github.com/collective/collective.bpmproxy',
    project_urls={
        'PyPI': 'https://pypi.python.org/pypi/collective.bpmproxy',
        'Source': 'https://github.com/collective/collective.bpmproxy',
        'Tracker': 'https://github.com/collective/collective.bpmproxy/issues',
        # 'Documentation': 'https://collective.bpmproxy.readthedocs.io/en/latest/',
    },
    license='GPL version 2',
    packages=find_packages('src', exclude=['ez_setup']),
    namespace_packages=['collective'],
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*",
    install_requires=[
        'setuptools',
        # -*- Extra requirements: -*-
        'dateutil',
        'generic-camunda-client',
        'plone.api>=1.8.4',
        'plone.app.dexterity',
        'plone.restapi',
        'pyjwt',
        'pytz',
        'z3c.jbot',
    ],
    extras_require={
        'test': [
            'plone.app.testing',
            # Plone KGS does not use this version, because it would break
            # Remove if your package shall be part of coredev.
            # plone_coredev tests as of 2016-04-01.
            'plone.testing>=5.0.0',
            'plone.app.contenttypes',
            'plone.app.robotframework[debug]',
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    update_locale = collective.bpmproxy.locales.update:update_locale
    """,
)
