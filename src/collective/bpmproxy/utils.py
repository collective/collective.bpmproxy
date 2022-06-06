from __future__ import print_function

import datetime
import jwt
import os
import plone.api


CAMUNDA_API_URL_ENV = "CAMUNDA_API_URL"
CAMUNDA_API_URL_DEFAULT = "http://localhost:8081/engine-rest"
CAMUNDA_API_PRIVATE_KEY_ENV = "CAMUNDA_API_PRIVATE_KEY"


def get_api_url():
    return os.environ.get(CAMUNDA_API_URL_ENV) or CAMUNDA_API_URL_DEFAULT


def get_token(username, groups):
    private_key = os.environ.get(CAMUNDA_API_PRIVATE_KEY_ENV)
    if private_key and os.path.exists(private_key):
        with open(private_key, "r", encoding="utf-8") as fp:
            private_key = fp.read()
    if not private_key:
        return None
    return jwt.encode(
        {
            "sub": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=3600),
            "groups": groups,
        },
        private_key,
        algorithm="ES256",
    ).decode("utf-8")


def get_authorization():
    user = plone.api.user.get_current()
    token = get_token(
        username=user and user.getUserName() or None,
        groups=user
        and [g.getId() for g in plone.api.group.get_groups(user=user) or []],
    )
    return token and "Bearer " + token or None
