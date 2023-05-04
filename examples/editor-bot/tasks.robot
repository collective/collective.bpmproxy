*** Settings ***
Library     RPA.Robocorp.WorkItems
Library     RPA.Robocorp.Vault
Library     RPA.OpenAI
Library     Collections
Library     OperatingSystem
Library     re
Library     requests


*** Variables ***
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


*** Tasks ***
Create article
    Set task variables from work item
    ###

    ${secrets}    Get Secret    secret_name=env
    Authorize To OpenAI    api_key=${secrets}[OPENAI_API_KEY]
    ${text}    @{conversation}    Chat Completion Create
    ...    ${context}\\n\\n${instructions}\\n\\n${format}
    ...    temperature=0.6
    IF    ${text.startswith("# ")}
        ${title}    Set variable    ${text.split("\n", 1)[0].strip("#").strip()}
        ${text}    Set variable    ${text.split("\n", 1)[-1].strip()}
    END

    ###
    Create Output Work Item
    Set Work Item Variable    title    ${title}
    Set Work Item Variable    text    ${text}
    Set Work Item Variable    conversation    ${conversation}
    Save Work Item

Iterate article
    Set task variables from work item
    ###

    ${secrets}    Get Secret    secret_name=env
    Authorize To OpenAI    api_key=${secrets}[OPENAI_API_KEY]
    ${text}    @{conversation}    Chat Completion Create
    ...    ${instructions}
    ...    temperature=0.6
    ...    conversation=${conversation}
    IF    ${text.startswith("# ")}
        ${title}    Set variable    ${text.split("\n", 1)[0].strip("#").strip()}
        ${text}    Set variable    ${text.split("\n", 1)[-1].strip()}
    END

    ###
    Create Output Work Item
    Set Work Item Variable    title    ${title}
    Set Work Item Variable    text    ${text}
    Set Work Item Variable    conversation    ${conversation}
    Save Work Item

Create titles
    Set task variables from work item
    ###

    ${secrets}    Get Secret    secret_name=env
    Authorize To OpenAI    api_key=${secrets}[OPENAI_API_KEY]
    ${response}    @{conversation}    Chat Completion Create
    ...    Please, list five title options with varying length, including some very short ones, for: ${text}
    ...    temperature=0.6

    ${titles}    Create list
    FOR    ${title}    IN    @{{$response.split("\n")}}
        ${title}    sub    ^[0-9]+\\.    ${EMPTY}    ${title}
        Append To List    ${titles}    ${{$title.strip().strip('"')}}
    END

    ###
    Create Output Work Item
    Set Work Item Variable    titles    ${titles}
    Save Work Item

Create description
    Set task variables from work item
    ###

    ${secrets}    Get Secret    secret_name=env
    Authorize To OpenAI    api_key=${secrets}[OPENAI_API_KEY]
    ${description}    @{conversation}    Chat Completion Create
    ...    Please, create a introductory paragraph under 300 characters: ${text}
    ...    temperature=0.6

    ###
    Create Output Work Item
    Set Work Item Variable    description    ${description}
    Save Work Item

Create image
    Set task variables from work item
    ###

    ${secrets}    Get Secret    secret_name=env
    Authorize To OpenAI    api_key=${secrets}[OPENAI_API_KEY]
    ${instructions}    @{conversation}    Chat Completion Create
    ...    Create super minimal instructions to illustrate this without text:\\n\\n ${description}
    ...    temperature=0.6

    ${images}    Image Create
    ...    ${instructions}
    ...    size=256x256
    ...    num_images=1

    ###
    Create Output Work Item
    FOR    ${url}    IN    @{images}
        ${response}    Get    ${url}
        Create binary file    image.png    ${response.content}
        Add Work Item File    image.png
        Set Work Item Variable    imageUrl    ${url}
    END
    Save Work Item

Create keywords
    Set task variables from work item
    ###

    ${secrets}    Get Secret    secret_name=env
    Authorize To OpenAI    api_key=${secrets}[OPENAI_API_KEY]
    ${response}    @{conversation}    Chat Completion Create
    ...    Please, list five top keywords for: ${text}
    ...    temperature=0.6

    ${keywords}    Create list
    FOR    ${keyword}    IN    @{{$response.split("\n")}}
        ${keyword}    sub    ^[0-9]+\\.    ${EMPTY}    ${keyword}
        Append To List    ${keywords}    ${{$keyword.strip().strip('"')}}
    END

    ###
    Create Output Work Item
    Set Work Item Variable    keywords    ${keywords}
    Save Work Item
