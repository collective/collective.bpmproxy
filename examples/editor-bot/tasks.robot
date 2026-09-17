*** Settings ***
Library     RPA.OpenAI
Library     Collections
Library     OperatingSystem
Library     re


*** Variables ***
${BPMN:PROCESS}     local
${context}          SEPARATOR=
...                 Make it Star Wars context, but without mentioning Star Wars.\\n
...                 Make it look like a news article.\\n
...                 Make it from the view point of Galactic Empire.\\n
...                 Make it end with "Long live the Emperor."\\n
...                 Make it glorius.
${instructions}     ${EMPTY}
${format}           SEPARATOR=
...                 Make it in markdown syntax.
@{conversation}     @{EMPTY}
${title}            ${EMPTY}
${description}      ${EMPTY}
${text}             ${EMPTY}
${imageUrl}         ${EMPTY}


*** Tasks ***
Create draft
    Authorize To OpenAI    api_key=${OPENAI_API_KEY.value}
    ${text}    @{conversation}    Chat Completion Create
    ...    ${context}\\n\\n${instructions}\\n\\n${format}
    ...    temperature=0.6
    IF    ${text.startswith("# ")}
        ${title}    Set variable    ${text.split("\n", 1)[0].strip("#").strip()}
        ${text}    Set variable    ${text.split("\n", 1)[-1].strip()}
    END

    VAR    ${title}    ${title}    scope=${BPMN:PROCESS}
    VAR    ${text}    ${text}    scope=${BPMN:PROCESS}
    VAR    ${conversation}    ${conversation}    scope=${BPMN:PROCESS}

Iterate draft
    Authorize To OpenAI    api_key=${OPENAI_API_KEY.value}
    ${text}    @{conversation}    Chat Completion Create
    ...    ${instructions}
    ...    temperature=0.6
    ...    conversation=${conversation}
    IF    ${text.startswith("# ")}
        ${title}    Set variable    ${text.split("\n", 1)[0].strip("#").strip()}
        ${text}    Set variable    ${text.split("\n", 1)[-1].strip()}
    END

    VAR    ${title}    ${title}    scope=${BPMN:PROCESS}
    VAR    ${text}    ${text}    scope=${BPMN:PROCESS}
    VAR    ${conversation}    ${conversation}    scope=${BPMN:PROCESS}

Create title
    Authorize To OpenAI    api_key=${OPENAI_API_KEY.value}
    ${response}    @{conversation}    Chat Completion Create
    ...    Please, list five title options with varying length, including some very short ones, for: ${text}
    ...    temperature=0.6

    ${titles}    Create list
    FOR    ${title}    IN    @{{$response.split("\n")}}
        ${title}    sub    ^[0-9]+\\.    ${EMPTY}    ${title}
        Append To List    ${titles}    ${{$title.strip().strip('"')}}
    END

    VAR    ${titles}    ${titles}    scope=${BPMN:PROCESS}

Create description
    Authorize To OpenAI    api_key=${OPENAI_API_KEY.value}
    ${description}    @{conversation}    Chat Completion Create
    ...    Please, create a introductory paragraph under 300 characters: ${text}
    ...    temperature=0.6

    VAR    ${description}    ${description}    scope=${BPMN:PROCESS}

Create image
    Authorize To OpenAI    api_key=${OPENAI_API_KEY.value}
    ${instructions}    @{conversation}    Chat Completion Create
    ...    Create super minimal instructions to illustrate this without text:\\n\\n ${description}
    ...    temperature=0.6

    ${images}    Image Create
    ...    ${instructions}
    ...    size=256x256
    ...    num_images=1

    ${imageUrl}    Set variable    ${EMPTY}
    FOR    ${url}    IN    @{images}
        ${imageUrl}    Set variable    ${url}
    END
    VAR    ${imageUrl}    ${imageUrl}    scope=${BPMN:PROCESS}

Create keywords
    Authorize To OpenAI    api_key=${OPENAI_API_KEY.value}
    ${response}    @{conversation}    Chat Completion Create
    ...    Please, list five top keywords for: ${text}
    ...    temperature=0.6

    ${keywords}    Create list
    FOR    ${keyword}    IN    @{{$response.split("\n")}}
        ${keyword}    sub    ^[0-9]+\\.    ${EMPTY}    ${keyword}
        Append To List    ${keywords}    ${{$keyword.strip().strip('"')}}
    END

    VAR    ${keywords}    ${keywords}    scope=${BPMN:PROCESS}
