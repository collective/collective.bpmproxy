# collective.bpmproxy

Add-on for Plone that integrates [Camunda Platform 7]((https://camunda.com/platform-7/)).

__Note:__ the add-on requires its [bundled Camunda Platform 7](#camunda-platform-7)
with a special authentication plugin authorizing requests from Plone as their initiating Plone users.
See installation instructions below.

Continue reading, as there are quite a few moving parts that need proper orchestration to get it working.

## Camunda Platform

Camunda is a server to run [BPMN 2.0](https://en.wikipedia.org/wiki/Business_Process_Model_and_Notation) processes.

Processes in this context means workflows that need certain degrees of interaction from different parties,
require running external/internal verifications, like:

- a student wants to enroll in a university degree
    - might require automatic checks to see if there are places available
    - might require the student to provide documents that need to be verified manually
- an employee requests a new laptop that requires approval from several managers
    - a manager needs to approve it
    - a check on the IT department storage might yield if there are ready available laptops
    - the account department might have to check their budget
- a review process of a news article that has to go through an approval process
    - a few quality checks might happen
    - a review from another journalist might be needed
    - the art department might suggest (with its internal process) the assets for the news article
    - the online department might want to update the SEO fields as well as timing the social media publication

See ready to test [examples](./examples/).

Camunda 7 provides an API and a web based UI to administrate the processes and tasks.

### Diagrams, decision tables, forms and processes

Camunda 7 differentiates between _designing the processes_,
with its own standalone designer, and _running those processes_.

Furthermore, a process is composed of the following pieces:

- main diagram: what you expect to see, a few boxes and lines that visually explain the process.
- decision tables: some decision tasks migth get a list of options to decide how to proceed,
  you can think of them like an `if/elif/else` or a `switch` programming instruction.
- forms: at any step of the process more information might be required,
  Camunda 7 provides a form generator that can render the forms with predefined data,
  and upon submission, the process continues.
- subdiagrams: a task within a diagram might be to fulfill another diagram,
  this way you have endless possibilities to expand your business processes.

To create diagrams and its related assets, you need to create them with a BPMN 2.0 compliant editor.

Camunda 7 provides already one such editor, see the [installation instructions](#install) below.

### Diagram examples

See the [examples](./examples/) folder for a few diagram examples to get you started.

### A note regarding the version

There is Camunda Platform 8, but they are like two completely different products.
Specially regarding __the license__.

Version 7 is completely open source and will remain like that forever.

### Camunda 7 resources

- [official website](https://camunda.com/platform-7/)
- [official documentation](https://docs.camunda.org/manual/latest/)
- [Training on BPMN](https://academy.camunda.com/camunda-bpmn) _(it might not be free)_
- [Training on DMN](https://academy.camunda.com/camunda-dmn) _(it might not be free)_

## Add-on high level features

Publish BPMN 2.0 processes from Camunda Platform 7,
and interact with the processes with Camunda Forms or BPMN signals.

- A custom content-type, "BPM Proxy" to publish an existing process
  with forms from a configured Camunda Platform 7 (later just "C7") instance
  as a CMS page with "sub pages" for currently open tasks in running instances of that process.

- A portlet to list all tasks available in every running process on the configured C7 instance.
  (Or just the tasks related to the current Plone page.)

- A Portlet to trigger BPMN signals at the configured C7 instance from Plone.

- A content-rule action to broadcast BPMN signals events at the configured C7 instance
  from configured events at Plone.

- Support to show related available user task forms also for pages of other types than BPM Proxy.

- Support to map `++add++` and `++edit++` forms as user task forms and complete user task from their completion.

## Installation

Given that this is an integration package, there are a few parts that need explanation:

- how to install and create __BPMN 2.0 diagrams__
- how to install and __Camunda Platform 7__
- how to integrate Camunda Platform 7 processes __with Plone__

As all topics are quite involved, it is easier to explain them separately.

### Processes Modeler

Camunda provides a stand alone application named `Desktop Modeler`.

Go to its [download website](https://camunda.com/download/modeler/)
and select the right version for your operating system.

Unzip the app and double click on the `camunda-modeler` binary.

An app will open and you will be able to __start modeling your processes!__

See the [`examples`](./examples/) folder for readily available to learn from.

#### Simulate processes

One designing diagrams, specially if they are involved,
it is important to ensure they work.

To lower the full round trip of designing a process, pushing it to Camunda,
testing it in a controlled environment and check if it works,
there is a __plugin__ for the Desktop Modeler that allows you
to __simulate your processes__ before you push them to Camunda.

This way you can much more easily iterate over your designs,
double check them with the end users that will use them, etc.

To install the plugin:

```shell
# Linux
cd ~/.config/camunda-modeler # note the leading dot in ".config"
# Mac OS X
cd ~/Library/Application Support/camunda-modeler
mkdir -p resources/plugins
cd resources/plugins
git clone https://github.com/camunda/camunda-modeler-token-simulation-plugin.git
```

__Note:__ if the Camunda Modeler folder does not exist,
be sure to open the Modeler app at least once. For Windows users,
please check where the configuration folder of apps is located.

Re-start the Modeler app and you should see at the top left of an BPMN diagram
the following image:

![Simulator button](docs/token-simulator-button.png?raw=true)

With this you can start simulating your process:

- click on the play button on the starting event
- click on the pause buttons found on all elements to stop the process at that point
- on gateways you are able to choose which branch it should go to

See the [plugin repository](https://github.com/camunda/camunda-modeler-token-simulation-plugin)
for more information about it.

#### Publish processes

Once your process is ready for more real testing,
the following steps are needed to get your process published:

- the diagram must be saved in your file system
- there should be no errors (see the bottom bar for the red circled error icon)
    - the most common error is that the `StartEvent` element must define a `<History time to live>`
        - for that click on the background canvas and select the `History cleanup` section on the right panel
        - set the `time to live` field to a number, like `1`
        - _if you don't see the right pane, go to the main menu -> `Window` -> `Toggle Properties Panel`_
- [Camunda needs to be running](#camunda-platform-7) so you can push your processes there!

Once these conditions are met, you are ready to click on the __rocket icon__
located at the bottom bar.

A small popup will show up to establish the connection to the Camunda server.

The `REST endpoint` field should say `http://localhost:8081/engine-rest`,
if it still shown an error message below the field,
double check that your Camunda instance runs fine.

On the `Authentication` section, select `HTTP Basic` and use `admin` for user and password.

__Note:__ if your model includes forms, decision tables and/or other models
you need to either upload them separately, or include them via the `Include additional files` section.

Once everything is set up properly, finally, push the `Deploy` button!

Head to the [Camunda Cockpit](#camunda-cockpit) to manage the processes.

### Camunda Platform 7

There is a [`docker-compose.yml`](./docker-compose.yml)
with the main pieces to get Camunda working locally:

- Camunda 7 itself
- a PostgreSQL database server (where Camunda stores the tasks and processes)
- a debug mail server for local development (a mailhog instance, to check the mails being sent by processes)

For that you will need to get `docker` installed
and a pair of [private keys generated](#authentication-keys).

See the [`docker-compose` install instructions](https://docs.docker.com/compose/install/).

To run Camunda, run:

```shell
docker compose up
```

See the [troubleshooting sections if you are having problems](#troubleshooting).

#### Authentication keys

To get Plone and Camunda to talk to each other, they need to trust each other.

For that a pair of public/private keys are used.

__Plone__ needs a private key to communicate with Camunda via a JWT-authentication token,
see the [installation instructions for Plone](#plone-integration),
to generate it, run:

```shell
openssl genpkey -algorithm ed25519 -out ec-ed25519-priv-key.pem
```

__Camunda__ needs the public key to verify the JWT-authentication token coming from Plone,
to generate it, run:

```shell
openssl ec -in ec-ed25519-priv-key.pem -pubout > ec-ed25519-pub-key.pem
```

The private key, for Plone, needs to be within reach of the Plone instance,
while the public key, for Camunda, needs to be directly in this repository,
otherwise `docker-compose.yml` will not find it.

#### Camunda cockpit

The Camunda cockpit, its web UI to manage processes, can be found at:

<http://localhost:8081/camunda/app/cockpit/default/#/login>

Use `admin` for both user and password.

You should see a three pane layout with the middle column having entries of all your uploaded processes.

If you still haven't uploaded any, [learn how to do it](#publish-processes).

### Plone integration

With [processes created](#processes-modeler) and [Camunda running](#camunda-platform-7)
its time for the last piece of the puzzle.

The `collective.bpmproxy` repository contains an example buildout configuration.
If you are using pip and mxdev to install Plone 6,
please see [the Plone documentation](https://6.docs.plone.org/install/manage-add-ons-packages.html)
on how to add `collective.bpmproxy` to your setup.

You will need to set two environment variables, either in `buildout` or directly on the shell:

Buildout:

```ini
[buildout]
...
[instance]
environment-vars =
    ...
    CAMUNDA_API_URL http://localhost:8081/engine-rest
    CAMUNDA_API_PRIVATE_KEY ${buildout:bin-directory}/../ec-ed25519-priv-key.pem
```

Shell:

```shell
CAMUNDA_API_URL="http://localhost:8081/engine-rest"
CAMUNDA_API_PRIVATE_KEY="/FULL-PATH-TO-YOUR-PRIVATE-KEY/ec-ed25519-priv-key.pem"
```

Run buildout/pip and start Plone:

```shell
buildout
./bin/instance fg
```

Create a Plone (Classic UI) instance and install the `collective.bpmproxy` add-on.

There are two main ways to integrate BPMN processes with Plone:

- via a content type: then the BPMN process _needs_ a form as a first step
- via a signal: a Plone content rule needs to be installed globally or on a folder/document.
  `collective.bpmproxy` already provides a few content rules ready to be used

#### Content type integration

On the Plone Toolbar's `Add` menu you should see a new content type: `Bpm Proxy`.

This new content type allows to select (with autocompletion!) a process you want to manage.

After creating the document, fill it and monitor the process in [Camunda's Cockpit](#camunda-cockpit).

#### Content rules integration

For processes that should happen automatically _given a certain condition_,
install a `collective.bpmproxy` provided content rule with the following steps:

- go to the folder where the content rule should be applied
- on the Plone toolbar select the `Rules` option
- on the view that opens, select from the drop down the content rule that suits your needs
- configure the installed content rule as any other content rules

If, for example, you selected the rule `BPMN signal: submitted any`
your BPMN process needs to have a `Signal StartEvent` element
with a `Signal` configured to `plone-content-submitted`.

Open the [`examples/empire-insider/ReviewAssistant`](./examples/empire-insider/ReviewAssistant.bpmn) diagram
with the [Modeler app](#processes-modeler) for such an example.

## Advanced topics

Note that you need to be already comfortable with Camunda 7 and designing processes,
but for the braves ones, here are some advanced topics:

- [Automation playground](https://datakurre.github.io/automation-playground/)

## Troubleshooting

A few of the installation errors that we have found and solved:

- docker version: `docker` version `17.x` is reported to __not__ work,
  while version series `24.x` are reported to __work__.
  The minimal version supported is something in between.
- `openssl` version: version `3.x` is reported to be working while anything below fails.
  `openssl` is needed to generate the [pair keys](#authentication-keys)
- `docker compose` volumes: if you see the following traceback in Plone
  `AssertionError: Connection is a "hop-by-hop" header; it cannot be used by a WSGI application (see PEP 3333)`
  look at the `docker compose` log lines, Camunda is having a problem trying to read the public key.
  By default the volumes in `docker-compose.yml` are mounted with `:Z`, change it to `:ro` to see if that solves it.

If your problem is not listed here,
please take the time to [create an issue](https://github.com/collective/collective.bpmproxy/issues/new)!

## Contribute

- [Issue Tracker](https://github.com/collective/collective.bpmproxy/issues)
- [Source Code](https://github.com/collective/collective.bpmproxy)

## License

The project is licensed under the GPLv2.
