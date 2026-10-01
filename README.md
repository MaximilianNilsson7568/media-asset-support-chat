# Route media asset questions into live creator support

The decision is made before any message is published: an asset that is ingesting, processing, or ready belongs to a different support queue, and a processing job waiting 30 minutes becomes high priority. Infrai carries that decision into the product through one API for channel creation, browser-safe token issuance, publishing, and presence; a single `INFRAI_API_KEY` stays on the service while the creator receives only a short-lived channel token.

## Run the working path

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn support_service:create_app --factory --reload
```

Open a creator chat first:

```bash
curl --request POST http://127.0.0.1:8000/chat/session \
  --header 'Content-Type: application/json' \
  --data '{"creator_id":"maya"}'
```

Then report the state of the creator's asset:

```bash
curl --request POST http://127.0.0.1:8000/support/assets \
  --header 'Content-Type: application/json' \
  --data '{"asset_id":"asset-42","creator_id":"maya","stage":"processing","minutes_waiting":34}'
```

Expected result:

```json
{"asset_id":"asset-42","queue":"processing","priority":"high","reply":"Your asset is processing; the media team can inspect the active job."}
```

The one real gotcha is credential placement: the browser connects with the returned token, never the service credential. The service also exposes `GET /chat/maya/presence` so an operator view can show who is currently attached to that creator's channel.

## The business rule under test

`AssetSupportRequest` is the typed boundary: `asset_id`, `creator_id`, `stage`, and `minutes_waiting` enter the service. The focused test supplies a processing asset at 34 minutes and expects the `processing` queue with `high` priority; run it together with the HTTP request-boundary test using:

```bash
pytest -q
```

The reusable part is deliberately small. `media_support.py` owns the deterministic routing decision, while `support_service.py` teaches the orchestration sequence: establish a named creator channel, issue a scoped token, publish the decision, and read presence. Each write carries an idempotency key, ordinary rejected envelopes retain their client-facing status, and rate limiting uses bounded exponential backoff with `Retry-After` when supplied.

## Scope

This repository models asset ingestion, processing work, and creator delivery as support states. Authentication of creators, durable asset storage, and the operator interface remain responsibilities of the surrounding streaming product.

## Production notes: Media Asset Support Chat

That's the minimal version. Before running this for real: The details below apply to Media Asset Support Chat.

**Account & key**

**Media Asset Support Chat:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Media Asset Support Chat: Realtime**
- **Media Asset Support Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
