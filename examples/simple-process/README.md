# Example: Simple Process

A Simple Camunda 7 Process.

The process consist of a Start-Event and an End-Event.
A Form with a commit Button is connected to the Start-Event and clicking the Button triggers the Start-Event.

This Process can be deployed to Camunda and then selected for the "Bpm Proxy" Contenttype in Plone.

## Usage in Plone "Bpm Proxy" Contenttype

### Prerequisites
* Plone with installed "collective.bpmproxy" installed
* Running Camunda service
* Running Camunda Modeler application

### Deploying Process to Camunda
To use the Process it needs to be deployed to Camunda. This is done with the Camunda Modeler application.

* Open Camunda Modeler applikation
* Select: File -> Open File to open "simple-process.bpmn" from your filesystem
* Select: "Deploy current diagram" (rocket icon in lower bar)
* Set: "REST Endpoint" to: http://localhost:8081/engine-rest
* Set: Credentials (default Username: admin, default Password: admin)
* Select: Include addional Files and select "simple-process-submit.form" from your filesystem
* Click: "Deploy" Button

### Use Process in Plone "Bpm Proxy" Contenttype
Processes that are deployed to Camunda could be selected in the "Process Definition" field of the "Bpm Proxy" Contenttype. 

* in Plone 
* Select Add -> Bpm Proxy
* Set: some title
* Choose: "Example: Simple Process" as Process Definition  

In the View of the created content the form of the "Simple Process" is rendered.

Clicking the "Start Simple Process" button triggers the start of a new Process in Camunda.

### View Process History in Camunda
The State and History of the process can be viewed in the "Camunda Cockpit" of Camunda.

* Open Camunda in your browser
* Select "Camunda Cockpit"
* Select Processes
* Select "Example: Simple Process" from the list of deployed processes
* Select the "History" tab to see a list of processes that were run in Camunda
