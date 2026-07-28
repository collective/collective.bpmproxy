# ============================================================================
# DEXTERITY ROBOT TESTS
# ============================================================================
#
# Run this robot test stand-alone:
#
#  $ bin/test -s collective.bpmproxy -t test_bpm_attachment.robot --all
#
# Run this robot test with robot server (which is faster):
#
# 1) Start robot server:
#
# $ bin/robot-server --reload-path src collective.bpmproxy.testing.COLLECTIVE_BPMPROXY_ACCEPTANCE_TESTING
#
# 2) Run robot tests:
#
# $ bin/robot /src/collective/bpmproxy/tests/robot/test_bpm_attachment.robot
#
# See the http://docs.plone.org for further details (search for robot
# framework).
#
# ============================================================================

*** Settings *****************************************************************

Resource  plone/app/robotframework/selenium.robot
Resource  plone/app/robotframework/keywords.robot

Library  Remote  ${PLONE_URL}/RobotRemote

Test Setup  Open test browser
Test Teardown  Close all browsers


*** Test Cases ***************************************************************

Scenario: As a site administrator I can add a Bpm Attachment
  Given a logged-in site administrator
    and an add Bpm Attachments form
   When I type 'My Bpm Attachment' into the title field
    and I submit the form
   Then a Bpm Attachment with the title 'My Bpm Attachment' has been created

Scenario: As a site administrator I can view a Bpm Attachment
  Given a logged-in site administrator
    and a Bpm Attachment 'My Bpm Attachment'
   When I go to the Bpm Attachment view
   Then I can see the Bpm Attachment title 'My Bpm Attachment'


*** Keywords *****************************************************************

# --- Given ------------------------------------------------------------------

a logged-in site administrator
  Enable autologin as  Site Administrator

an add Bpm Attachments form
  Go To  ${PLONE_URL}/++add++Bpm Attachments

a Bpm Attachment 'My Bpm Attachment'
  Create content  type=Bpm Attachments  id=my-bpm_attachment  title=My Bpm Attachment

# --- WHEN -------------------------------------------------------------------

I type '${title}' into the title field
  Input Text  name=form.widgets.IBasic.title  ${title}

I submit the form
  Click Button  Save

I go to the Bpm Attachment view
  Go To  ${PLONE_URL}/my-bpm_attachment
  Wait until page contains  Site Map


# --- THEN -------------------------------------------------------------------

a Bpm Attachment with the title '${title}' has been created
  Wait until page contains  Site Map
  Page should contain  ${title}
  Page should contain  Item created

I can see the Bpm Attachment title '${title}'
  Wait until page contains  Site Map
  Page should contain  ${title}
