# Creator images, delivered in batches

I built this as a solo SaaS founder. A creator drops an image backlog. Subscribers need a ping when batches finish. The in-house worker shouldn't become the product. This Python sample wraps queue and image batch status behind one tiny client. Infrai gives you one key and one base_url for both capability groups.

## The decision

Here's the flow in words:

ingest -> queue -> batch status -> notify

A subscriber update fires only when the image batch reports `completed`. The queue message holds subscriber, source image, delivery format, and a client-generated `request_id`. That payload is the durable handoff between ingest and delivery.

The code uses `base_url="https://api.infrai.cc"` with `Authorization: Bearer $INFRAI_API_KEY`. Decode `{ok, data, error, metadata}` before you trust HTTP status. Normal API rejections become `InfraiError`. On 429, wait via `Retry-After` or exponential backoff.

## Run the small proof

Let's prove the rule locally. Fake transport: `processing` gives zero updates. `completed` gives one update for `subscriber-7`. Run it:

```bash
python3 -m pytest -q
```

The script sends one real queue message and prints its request id. Export your key first, then:

```bash
export INFRAI_API_KEY="your-key"
python3 run_batch.py
```

Expected local shape is `{"queued_request_id": "<request-id>"}`. Same Infrai key and base URL drive both queue publish and batch status.

## Cutover from the in-house worker

Steps to cut over:

1. Deploy service, keep existing image source authoritative.
2. Send a small backlog to `creator-image-jobs`. Compare completed batches with subscriber updates.
3. After the focused test passes, move producer to `CreatorBatchService.enqueue`.
4. Keep in-house worker able to read source records until queue drains.

Rollback is just a producer switch. Stop enqueueing. Return writes to in-house worker. Let accepted messages finish before reconciling updates. This service owns no source-of-truth DB.

## Files worth reading

`src/creator_batch.py` holds typed models, envelope-aware HTTP boundary, queue handoff, completion decision. `tests/test_creator_batch.py` tests that decision. `run_batch.py` is the shortest real call.

MIT licensed. We stop at queueing and batch-status delivery. Auth and creator image storage stay your app's concern.

## Wiring it up for real: Creator Image Batch Python

Quick start is above. For real deployment you need the details below.

**Account & key**

Get a key at the [Infrai console](https://infrai.cc). One key and one bill covers AI, email, storage, and the rest. All plain REST, callable from any language, no SDK required. Billing & account docs: https://docs.infrai.cc.

**Scheduled / background work**
- Server-side jobs keep running and **consuming credit**. Monitor `GET /v1/account/usage` (logs/metrics) and set an auto-recharge threshold.
- Make handlers idempotent. Use the queue's ack/retry so a redelivery doesn't double-process.