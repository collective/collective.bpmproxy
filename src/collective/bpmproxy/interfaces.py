# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""

from zope.publisher.interfaces.browser import IDefaultBrowserLayer


ANONYMOUS_USER_ANNOTATION_KEY = "collective.bpmproxy.anonymous"
ATTACHMENTS_CONTAINER_TYPE = "Bpm Attachments"
ATTACHMENTS_DEFAULT_TYPE = "Bpm Attachment"
ATTACHMENTS_KEY_KEY = "attachmentsKey"
CAMUNDA_ADMIN_USER = "admin"
CAMUNDA_ADMIN_GROUP = "camunda-admin"
CAMUNDA_API_PRIVATE_KEY_ENV = "CAMUNDA_API_PRIVATE_KEY"
CAMUNDA_API_URL_DEFAULT = "http://localhost:8081/engine-rest"
CAMUNDA_API_URL_ENV = "CAMUNDA_API_URL"
FORM_DATA_KEY = "collective-bpmproxy-form-data"
PLONE_ADMIN_GROUP = "Administrators"


class HTTPMethod:
    GET = "GET"
    POST = "POST"


class PloneNotificationLevel:
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class ICollectiveBpmproxyLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""
