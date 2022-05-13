# ============================================================================
# DEXTERITY ROBOT TESTS
# ============================================================================
#
# Run this robot test stand-alone:
#
#  $ bin/test -s collective.bpmproxy -t test_bpm_proxy.robot --all
#
# Run this robot test with robot server (which is faster):
#
# 1) Start robot server:
#
# $ bin/robot-server --reload-path src collective.bpmproxy.testing.COLLECTIVE_BPMPROXY_ACCEPTANCE_TESTING
#
# 2) Run robot tests:
#
# $ bin/robot /src/collective/bpmproxy/tests/robot/test_bpm_proxy.robot
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

Scenario: As a site administrator I can add a Bpm Proxy
  Given a logged-in site administrator
    and an add Bpm Proxy form
   When I type 'My Bpm Proxy' into the title field
    and I submit the form
   Then a Bpm Proxy with the title 'My Bpm Proxy' has been created

Scenario: As a site administrator I can view a Bpm Proxy
  Given a logged-in site administrator
    and a Bpm Proxy 'My Bpm Proxy'
   When I go to the Bpm Proxy view
   Then I can see the Bpm Proxy title 'My Bpm Proxy'


*** Keywords *****************************************************************

# --- Given ------------------------------------------------------------------

a logged-in site administrator
  Enable autologin as  Site Administrator

an add Bpm Proxy form
  Go To  ${PLONE_URL}/++add++Bpm Proxy

a Bpm Proxy 'My Bpm Proxy'
  Create content  type=Bpm Proxy  id=my-bpm_proxy  title=My Bpm Proxy

# --- WHEN -------------------------------------------------------------------

I type '${title}' into the title field
  Input Text  name=form.widgets.IBasic.title  ${title}

I submit the form
  Click Button  Save

I go to the Bpm Proxy view
  Go To  ${PLONE_URL}/my-bpm_proxy
  Wait until page contains  Site Map


# --- THEN -------------------------------------------------------------------

a Bpm Proxy with the title '${title}' has been created
  Wait until page contains  Site Map
  Page should contain  ${title}
  Page should contain  Item created

I can see the Bpm Proxy title '${title}'
  Wait until page contains  Site Map
  Page should contain  ${title}
