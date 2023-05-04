*** Settings ***
Library     RPA.Robocorp.WorkItems
Library     RPA.Robocorp.Vault
Library     OperatingSystem
Library     requests
Library     markdown
Library     markdownify
Library     re
Library     base64


*** Variables ***
${type}             News Item
${title}            ${EMPTY}
${description}      ${EMPTY}
${text}             ${EMPTY}
${keywords}         ${EMPTY}

${portalUrl}        http://localhost:8080/Plone
${path}             /news
${uuid}             ${EMPTY}


*** Tasks ***
Get content
    Set task variables from work item

    Should not be empty    ${uuid}

    ${headers}    Get headers

    ${response}    Get    ${portalUrl}/resolveuid/${uuid}
    ...    headers=${headers}
    ${data}    Set variable    ${response.json()}

    ${text}    markdownify    ${data}[text][data]

    Create output work item
    Set Work Item Variable    text    ${text}
    Set Work Item Variable    title    ${data}[title]
    Set Work Item Variable    description    ${data}[description]
    Set Work Item Variable    keywords    ${data}[subjects]
    Save work item

Submit content
    Set task variables from work item

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

    ${images}    Get work item files    image
    FOR    ${path}    IN    @{images}
        ${bytes}    Get binary file    ${path}
        ${data}    b64encode    ${bytes}
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

    Create output work item
    Set Work Item Variable    url    ${url}
    Save work item

Update title
    Set task variables from work item

    ${headers}    Get headers

    ${payload}    Create dictionary
    ...    title=${title}

    ${url}    Resolve redirect    ${portalUrl}/resolveuid/${uuid}

    ${response}    Patch    ${url}
    ...    headers=${headers}
    ...    json=${payload}
    Should be equal    "${response.status_code}"    "204"

    ${url}    Set variable    ${response.headers}[Location]

    Create output work item
    Save work item

Update description
    Set task variables from work item

    ${headers}    Get headers

    ${payload}    Create dictionary
    ...    description=${description}

    ${url}    Resolve redirect    ${portalUrl}/resolveuid/${uuid}

    ${response}    Patch    ${url}
    ...    headers=${headers}
    ...    json=${payload}
    Should be equal    "${response.status_code}"    "204"

    Create output work item
    Save work item

Update text
    Set task variables from work item

    ${headers}    Get headers

    ${html}    markdown    ${text}

    ${payload}    Create dictionary
    ...    text=${html}
    ${url}    Resolve redirect    ${portalUrl}/resolveuid/${uuid}

    ${response}    Patch    ${url}
    ...    headers=${headers}
    ...    json=${payload}
    Should be equal    "${response.status_code}"    "204"

    Create output work item
    Save work item


*** Keywords ***
Get headers
    ${secrets}    Get Secret    secret_name=env

    ${headers}    Create dictionary
    ...    Accept=application/json
    ...    Content-Type=application/json
    ...    Authorization=${secrets}[PLONE_AUTHORIZATION]

    RETURN    ${headers}

Resolve redirect
    [Arguments]    ${url}
    ${headers}    Get headers

    ${response}    Get    ${url}
    ...    headers=${headers}    allow_redirects=${FALSE}

    Should be equal    "${response.status_code}"    "301"

    RETURN    ${response.headers}[Location]
