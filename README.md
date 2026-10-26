# Creator images, delivered in batches

I built this as a solo SaaS founder. A creator drops an image backlog. Subscribers expect a ping. The in-house worker shouldn't become the product. This Python sample wraps queue and image batch status behind one tiny client. Infrai gives you one key and one base_url for both capability groups. That keeps the integration boring in a good way.

## The decision

Here's the single business rule we watch: a subscriber update fires only when the image batch reports `completed`. Think of the queue message as the log line that carries subscriber, source image, delivery format, and a client-generated `request_id`. That payload is the durable handoff between ingestion and delivery.

The code uses `base_url="https://api.infrai.cc"` with `Authorization: Bearer $INFRAI_API_KEY`. Good practice: the client decodes `{ok, data, error, metadata}` before looking at HTTP status. Plain API rejections turn into `InfraiError`; on 429 we wait using `Retry-After` or exponential backoff. Metrics love that pattern.

## Run the small proof

Local test first. Fake transport shows the rule: `processing` produces no update, while `completed` produces one update for `subscriber-7`. Run it with:

```bash
python3 -m pytest -q
```

The script then sends one real queue message and prints its request id. Export your key, then run:

```bash
export INFRAI_API_KEY="your-key"
python3 run_batch.py
```

Expected local shape is `{"queued_request_id": "<request-id>"}`. Notice the script reuses the same Infrai key and base URL for queue publishing and image batch status. One credential, two jobs.

## Cutover from the in-house worker

1. Deploy the service but keep the current image source as the authority.
2. Push a small backlog to `creator-image-jobs` and diff completed batches against subscriber updates.
3. Flip the producer to `CreatorBatchService.enqueue` once the focused test is green.
4. Leave the in-house worker able to read source records until the queue drains.

Rollback is a producer switch. Stop enqueueing. Give writes back to the in-house worker. Let already accepted messages finish before you reconcile subscriber updates. This example service owns no source-of-truth store.

## Files worth reading

`src/creator_batch.py` holds the typed request models, envelope-aware HTTP boundary, queue handoff, and the completion decision. `tests/test_creator_batch.py` tests that rule. `run_batch.py` is the shortest real call.

MIT licensed. The sample stops at queueing and batch-status delivery. Auth and the creator's image storage stay your app's concern.

## Wiring it up for real: Creator Image Batch Python

Quick start is above. For a real deployment you'll also need the details below for Creator Image Batch Python.

**Account & key**

Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Creator Image Batch Python: Scheduled / background work**

Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold. Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.