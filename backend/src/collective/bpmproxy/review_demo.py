"""Setup helpers for the optional review-process demo profile.

Unlike ``renovation_demo``, this profile assigns its content rules to the
stock ``submit``/``retract`` transitions of Plone's default Simple
Publication Workflow, so it affects *any* content site-wide, not just
dedicated demo content. Only apply it to a throwaway or dedicated demo
site.
"""

import plone.api


REVIEW_BOT_USER = "review-bot"
REVIEWERS_GROUP = "Reviewers"


def install(context):
    """Post-install handler for collective.bpmproxy:review_demo."""
    # Ensure Reviewers group exists
    if not plone.api.group.get(REVIEWERS_GROUP):
        plone.api.group.create(groupname=REVIEWERS_GROUP, title="Reviewers")

    # Create review-bot user if needed
    if not plone.api.user.get(username=REVIEW_BOT_USER):
        bot = plone.api.user.create(
            username=REVIEW_BOT_USER,
            email="review-bot@example.com",
            properties={"fullname": "Review Bot"},
        )
        plone.api.group.add_user(groupname="Site Administrators", user=bot)
        plone.api.group.add_user(groupname=REVIEWERS_GROUP, user=bot)
