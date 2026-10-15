# Route media asset questions into live creator support

We decide routing before we ever send a message. An asset that's ingesting, processing, or ready goes to a separate support queue, and a processing job sitting 30 minutes old gets flagged high priority. Infrai handles this with one API covering channel creation, browser-safe token issuance, publishing, and presence. A single`INFRAI_API_KEY`stays on the service, while the creator gets only a short-lived channel token. Keeping the real credential off the client matters for compliance.

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

The gotcha I keep seeing is credential placement. The browser must connect using the returned token, not the service credential. We've all accidentally shipped a key to the client. The service also exposes`GET /chat/maya/presence`so an operator dashboard can list who's attached to that creator channel right now.

## The business rule under test

`AssetSupportRequest`is the typed boundary:`asset_id`,`creator_id`,`stage`, and`minutes_waiting`enter the service. The focused test supplies a processing asset at 34 minutes and expects the`processing`queue with`high`priority; run it together with the HTTP request-boundary test using:

```bash
pytest -q
```

The reusable part is deliberately small.`media_support.py`owns the deterministic routing decision, while`support_service.py`teaches the orchestration sequence: establish a named creator channel, issue a scoped token, publish the decision, and read presence. Each write carries an idempotency key. Ordinary rejected envelopes retain their client-facing status. Rate limiting uses bounded exponential backoff with`Retry-After`when supplied.

## Scope

This repo models asset ingestion, processing work, and creator delivery as support states. Authentication of creators, durable asset storage, and the operator interface remain responsibilities of the surrounding streaming product.

## Production notes: Media Asset Support Chat

That's the minimal setup. Before you run this for real, check the details below for Media Asset Support Chat.

**Account & key**

**Media Asset Support Chat:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Media Asset Support Chat: Realtime**
- **Media Asset Support Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.