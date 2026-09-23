# Review Bot (Python Worker)

An `operaton-tasks` worker for the parallel review process example (`examples/review-process`).

It subscribes to the `Plone Workflow Transition` external task topic, resolves the Plone content item's URL by UUID, aggregates all reviewer feedback and coordinator notes, and triggers the workflow transition (`publish` or `retract`) via Plone's REST API (`/@workflow/{transition}`) with the consolidated review submitted as the transition comment.

## Setup

1. Copy `secrets.example.env` to `secrets.env`:
   ```bash
   cp secrets.example.env secrets.env
   ```
2. Update `PLONE_AUTHORIZATION` if required (for example `Basic YWRtaW46YWRtaW4=`).

## Running the Worker

Run with `uv` directly or via `make`:

```bash
make serve
```

## How It Works

1. Operaton locks and fetches tasks under the topic `"Plone Workflow Transition"`.
2. The worker retrieves `uuid`, `transition` (`publish` or `retract`), `reviews`, and `mainReviewerComment`.
3. It formats a structured markdown comment containing the individual reviewers' ratings/feedback and any coordinator notes.
4. It resolves the content path using `GET {PLONE_URL}/resolveuid/{uuid}`.
5. It performs `POST {url}/@workflow/{transition}` with JSON payload `{"comment": full_comment}`.
6. It completes the external task in Operaton.
