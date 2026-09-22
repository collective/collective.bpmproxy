# Parallel Review Process Example

A multi-reviewer delegation and parallel review process demonstrating Plone content rule integration, BPMN 2.0 parallel multi-instance execution with safe variable aggregation, and automated Plone workflow transitions with full review comments.

## Overview

When content is submitted for review in Plone (Simple Publication Workflow), this process:
1. **Listens for Plone content rule signal** (`plone-content-submitted-to-review`).
2. **Binds businessKey** to the Plone content item (`${uuid}:${processInstanceId}`) so that tasks appear in Plone's task views and portlets.
3. **Presents a reviewer triage task** (`review-select-reviewers.form`) where a lead reviewer or administrator selects multiple reviewers.
4. **Initializes a pre-allocated array** (`reviews`) matching the number of selected reviewers.
5. **Spawns parallel review tasks** inside an expanded multi-instance sub-process, one for each selected reviewer (`review-submit.form`).
6. **Merges each review into its assigned array slot** via `${reviews.set(loopCounter, ...)}` to eliminate race conditions and avoid data loss during parallel completion.
7. **Consolidates reviews** into a summary and prompts the coordinator for a final decision (`review-decision.form`): either **Publish** or **Reject**.
8. **Dispatches an external service task** (`Plone Workflow Transition`) handled by `examples/review-bot-py`, which triggers the Plone REST API `/@workflow/{transition}` with the complete aggregated review text submitted as the transition comment.

## Process Diagram

The process definition is in `review-process.bpmn`. It contains:
- **Start Event**: Signal catch event for `plone-content-submitted-to-review`.
- **Bind Key**: Script task binding the business key to `${uuid}:${execution.processInstanceId}`.
- **Choose Reviewers**: User task for group `Reviewers` with form `review-select-reviewers`.
- **Initialize Array**: Script task setting `reviews = reviewers.clone()`.
- **Parallel Review Sub-process**: Multi-instance sub-process (`isSequential="false"`, collection `${reviewers}`, element `reviewer`):
  - User task assigned to `${reviewer}` with form `review-submit`.
  - Script task writing into `reviews[loopCounter]`.
- **Consolidate Reviews**: Script task creating `reviewSummary`.
- **Final Decision**: User task with form `review-decision`.
- **Exclusive Gateway**: Routes to `publish` or `reject` path.
- **Service Task**: External task for topic `Plone Workflow Transition`.
- **End Event**: Process completed.

## Assets

- `review-process.bpmn` — BPMN 2.0 process definition (`example-plone-review-process`).
- `review-select-reviewers.form` — Initial delegation form to select parallel reviewers.
- `review-submit.form` — Individual reviewer feedback form (recommendation + comment).
- `review-decision.form` — Coordinator decision form displaying consolidated reviews.

## Plone Setup & Profile

The fastest way to configure Plone for this example is to apply the extension profile:
**`collective.bpmproxy:review_demo`**

This profile:
- Automatically registers the content rule `plone-content-submitted-to-review` triggered on transition `submit`.
- Automatically registers the content rule `plone-content-retracted` triggered on transition `retract`.
- Assigns and enables both content rules directly on the Plone site root.
- Ensures the `Reviewers` group exists and provisions the `review-bot` user account.

You can activate it via **Site Setup** → **Add-ons** (or via GenericSetup import / Python `applyProfile(portal, "collective.bpmproxy:review_demo")`).

> **Warning:** The `submit`/`retract` transitions are the same ones Plone's stock Simple Publication Workflow uses for ordinary content. Applying this profile to a site with existing content starts this example process for *every* normal "submit for review" / "retract" action site-wide, not just demo content. Only install it on a throwaway or dedicated demo site.

### Manual Content Rule Configuration (Alternative)

If configuring manually instead of using the profile:
1. Navigate to **Site Setup** → **Content Rules**.
2. Add a new content rule:
   - **Trigger**: *Workflow state changed*
   - **Condition**: *Workflow transition* equals `submit` (or workflow state is `pending`)
   - **Action**: *BPM Signal*
     - **BPM Signal name**: `plone-content-submitted-to-review`
     - **JSON Payload**:
       ```json
       {
         "uuid": "${uuid}",
         "title": "${title}",
         "author": "${user_fullname}",
         "portalUrl": "${portal_url}"
       }
       ```
3. Assign the content rule to your Plone site root.

### Demo users

`make bootstrap-review-demo` (run from the repository root with Plone
**stopped**, after `make bootstrap-site`) applies the profile and creates the
users the reviewer picker offers, all with their username as password:
`reviewer1`, `reviewer2`, `reviewer3` and `editor` (all in `Reviewers`), plus
`author`, who creates and submits content. It also sets the `review-bot`
password to `review-bot`. The profile grants `Reviewers` the `Reviewer` role
(so they can open content that is pending review) and puts a Tasks portlet on
the site root, which is where reviewers find their tasks.

## Deploying to Operaton

Deploy all assets using `pur` or the BPM Proxy modeler:

```bash
pur operaton deploy review-process.bpmn review-select-reviewers.form review-submit.form review-decision.form
```

Next, run the Python external task worker in `../review-bot-py`:

```bash
cd ../review-bot-py
make serve
```

Copy `../review-bot-py/secrets.example.env` to `secrets.env` first; the
example already holds the `review-bot` credentials.

## Walkthrough

1. `author` adds a Page and submits it for review.
2. `reviewer3` opens **Choose reviewers** from the *Review tasks* portlet and
   assigns `reviewer1` and `reviewer2`.
3. Each of them opens their own **Submit review** task.
4. `reviewer3` opens **Consolidate review & decide**, sees both reviews and
   publishes or rejects. The worker applies the transition with the reviews as
   the workflow comment.

## Implementation notes

- The external task's variables are declared as input parameters in the BPMN,
  because `operaton-tasks` fetches only local variables.
- The Operaton fixture has no scripting engine (JUEL only), so reviews are
  accumulated in a plain string variable, in completion order, by an
  `asyncBefore` script task: the engine retries it on optimistic-locking
  conflicts instead of failing the reviewer's form submit.
- The reviewer's `recommendation` and `comment` are declared as local input
  parameters, so parallel reviewers do not overwrite each other's values.
- Two reviewers completing at the very same instant can still make one submit
  fail with an optimistic-locking error; resubmitting works.
