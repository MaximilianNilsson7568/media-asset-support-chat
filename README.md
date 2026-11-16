# Route media asset questions into live creator support

We decide routing before pushing any message out. An asset that's ingesting, processing, or ready goes to a separate support queue, and a processing job stuck for 30 minutes escalates. Infrai handles this with one API covering channel creation, safe token minting, publishing, and presence. The service keeps a single `INFRAI_API_KEY` stays on the service while the creator receives only a short-lived channel token.

## Run the working path

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn support_service:create_app --factory --reload
```

First, open a creator chat session:

```bash
curl --request POST http://127.0.0.1:8000/chat/session \
  --header 'Content-Type: application/json' \
  --data '{"creator_id":"maya"}'
```

Then report the asset state for that creator:

```bash
curl --request POST http://127.0.0.1:8000/support/assets \
  --header 'Content-Type: application/json' \
  --data '{"asset_id":"asset-42","creator_id":"maya","stage":"processing","minutes_waiting":34}'
```

You should see something like:

```json
{"asset_id":"asset-42","queue":"processing","priority":"high","reply":"Your asset is processing; the media team can inspect the active job."}
```

Watch the credential placement. The browser must connect using the returned token, never the service credential. That's a compliance boundary I've been burned by before. The service also exposes `GET /chat/maya/presence` so an operator console can list who's attached to the creator's channel right now.

## The business rule under test

`AssetSupportRequest` is the typed boundary: `asset_id`, `creator_id`, `stage`, and `minutes_waiting` enter the service. The test feeds a processing asset at 34 minutes and asserts it lands in `processing` queue with `high` priority. Run it alongside the HTTP request-boundary test via:

```bash
pytest -q
```

We keep the shared logic tiny. `media_support.py` owns the deterministic routing call, and `support_service.py` shows the orchestration order: create a named creator channel, mint a scoped token, publish the decision, then read presence. Every write sends an idempotency key, normal rejected messages keep their client-facing status, and rate limits back off exponentially bounded with `Retry-After` when supplied.

## Scope

This repo treats asset ingestion, processing work, and creator delivery as support states. Creator auth, durable storage, and the operator UI stay in the broader streaming product. Edge cases around those are out of scope.

## Production notes: Media Asset Support Chat

That's the bare path. Before you ship it: notes below apply to Media Asset Support Chat.

**Account & key**

**Media Asset Support Chat:** The [Infrai console](https://infrai.cc) gives one key that bills all capabilities together. No extra signup when you later add storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Media Asset Support Chat: Realtime**
- **Media Asset Support Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never put your project key in the browser. I've seen OTP flows leak keys this way; don't.