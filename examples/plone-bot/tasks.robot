*** Settings ***
Library     OperatingSystem
Library     requests
Library     markdown
Library     markdownify
Library     re
Library     base64


*** Variables ***
${BPMN:PROCESS}     local
${type}             News Item
${title}            ${EMPTY}
${description}      ${EMPTY}
${text}             ${EMPTY}
${keywords}         ${EMPTY}
${imageUrl}         ${EMPTY}

${portalUrl}        http://localhost:8080/Plone
${path}             /news
${uuid}             ${EMPTY}


*** Tasks ***
Get Article
    Should not be empty    ${uuid}

    ${headers}    Get headers

    ${response}    Get    ${portalUrl}/resolveuid/${uuid}
    ...    headers=${headers}
    ${data}    Set variable    ${response.json()}

    ${text}    markdownify    ${data}[text][data]

    VAR    ${text}    ${text}    scope=${BPMN:PROCESS}
    VAR    ${title}    ${data}[title]    scope=${BPMN:PROCESS}
    VAR    ${description}    ${data}[description]    scope=${BPMN:PROCESS}
    VAR    ${keywords}    ${data}[subjects]    scope=${BPMN:PROCESS}

Submit for review
    ${html}    markdown    ${text}

    ${headers}    Get headers

    ${payload}    Create dictionary
    ...    @type=${type}
    ...    title=${title}
    ...    description=${description}
    ...    text=${html}
    ...    subjects=${keywords}

    ${response}    Post    ${portalUrl}/${path}
    ...    headers=${headers}
    ...    json=${payload}
    Should be equal    "${response.status_code}"    "201"

    ${url}    Set variable    ${response.headers}[Location]

    IF    '${imageUrl}' != '${EMPTY}'
        ${response}    Get    ${imageUrl}
        ${data}    b64encode    ${response.content}
        ${image}    Create dictionary
        ...    data=${data.decode("utf-8")}
        ...    encoding=base64
        ...    filename=image.png
        ...    content-type=image/png
        ${payload}    Create dictionary
        ...    image=${image}
        ${response}    Patch    ${url}
        ...    headers=${headers}
        ...    json=${payload}
        Should be equal    "${response.status_code}"    "204"    ${response.text}
    END

    ${response}    Post    ${url}/@workflow/submit
    ...    headers=${headers}
    Should be equal    "${response.status_code}"    "200"

    VAR    ${url}    ${url}    scope=${BPMN:PROCESS}

Update title
    ${headers}    Get headers

    ${payload}    Create dictionary
    ...    title=${title}

    ${url}    Resolve redirect    ${portalUrl}/resolveuid/${uuid}

    ${response}    Patch    ${url}
    ...    headers=${headers}
    ...    json=${payload}
    Should be equal    "${response.status_code}"    "204"

    ${url}    Set variable    ${response.headers}[Location]

    VAR    ${url}    ${url}    scope=${BPMN:PROCESS}

Update description
    ${headers}    Get headers

    ${payload}    Create dictionary
    ...    description=${description}

    ${url}    Resolve redirect    ${portalUrl}/resolveuid/${uuid}

    ${response}    Patch    ${url}
    ...    headers=${headers}
    ...    json=${payload}
    Should be equal    "${response.status_code}"    "204"

    VAR    ${url}    ${url}    scope=${BPMN:PROCESS}

Update article text
    ${headers}    Get headers

    ${html}    markdown    ${text}

    ${payload}    Create dictionary
    ...    text=${html}
    ${url}    Resolve redirect    ${portalUrl}/resolveuid/${uuid}

    ${response}    Patch    ${url}
    ...    headers=${headers}
    ...    json=${payload}
    Should be equal    "${response.status_code}"    "204"

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
