*** Settings ***
Library     requests


*** Variables ***
${BPMN:PROCESS}     local

${portalUrl}        http://localhost:8080/Plone
${uuid}             ${EMPTY}
${transition}       ${EMPTY}


*** Tasks ***
Transition content
    Should not be empty    ${uuid}
    Should not be empty    ${transition}

    ${headers}    Get headers

    ${url}    Resolve redirect    ${portalUrl}/resolveuid/${uuid}

    ${response}    Post    ${url}/@workflow/${transition}
    ...    headers=${headers}
    Should be equal    "${response.status_code}"    "200"    ${response.text}


*** Keywords ***
Get headers
    ${headers}    Create dictionary
    ...    Accept=application/json
    ...    Content-Type=application/json
    ...    Authorization=${PLONE_AUTHORIZATION.value}

    RETURN    ${headers}

Resolve redirect
    [Arguments]    ${url}
    ${headers}    Get headers

    ${response}    Get    ${url}
    ...    headers=${headers}    allow_redirects=${FALSE}

    Should be equal    "${response.status_code}"    "301"

    RETURN    ${response.headers}[Location]
