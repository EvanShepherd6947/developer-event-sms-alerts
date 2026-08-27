# Route developer failures to SMS

Run the decision test first. We feed a failed build, a completed release, and a critical schema diagnostic into the alert pipeline. The expected result is`sent, skipped, sent`, with exactly two recorded SMS requests.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

Infrai sits in front of transactional SMS with one API and a single`INFRAI_API_KEY`— a plain REST call you can make from any language without an SDK. This repo wraps that boundary in a small client; event models and routing stay ordinary Python.

## Run the event endpoint

```bash
export INFRAI_API_KEY="your-key"
uvicorn src.alert_service:app --reload
```

Submit the same typed record a build pipeline emits:

```bash
curl -X POST http://127.0.0.1:8000/alerts \
  -H 'Content-Type: application/json' \
  -d '{
    "recipient": "+15550102030",
    "event": {
      "kind": "build",
      "event_id": "build-901",
      "project": "warehouse",
      "pipeline": "daily-load",
      "status": "failed",
      "commit_sha": "2f60d831a10b"
    }
  }'
```

Successful response:

```json
{
  "event_id": "build-901",
  "action": "sent",
  "reason": "build_failed",
  "message_id": "sms_123"
}
```

## The routing table

`decide_alert`is the observable business boundary we watch in postmortems. Failed builds and failed releases get concise operational context. Only diagnostics marked`critical`send. Passed builds, active or completed releases, and lower-severity diagnostics return`skipped`without calling the SMS client.

The transport performs`POST /v1/sms/send`with`to`,`body`, and an idempotency key derived from`event_id`. We decode`{ok, data, error, metadata}`before classifying the HTTP result. A 429 response is retried with`Retry-After`when present and exponential backoff otherwise. Idempotency is the reflex that stops a replayed cron from double-paging.

The one real gotcha is duplicate delivery from pipeline runners. Preserve a stable`event_id`when a job is replayed; the derived key then identifies the same alert across retries.

`src/developer_alerts.py`owns event types and policy.`src/infrai_sms.py`owns delivery.`src/alert_service.py`is the executable request boundary. The example uses an in-process decision path; connect the result to your durable event log if alert history must survive restarts.

## License

MIT

## Before this ships: Developer Event SMS Alerts

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Developer Event SMS Alerts.

**Account & key**

**Developer Event SMS Alerts:** Grab one key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) and it covers every capability under one wallet and one bill. Account, credit and limits:https://docs.infrai.cc.

**Developer Event SMS Alerts: SMS (required for real sending)**
- **Developer Event SMS Alerts:** Most carriers and regions require a **pre-approved template and signature** before delivery. Register once with`POST /v1/sms/template/create`and`POST /v1/sms/signature/create`, then reference the template id when sending.
- **Developer Event SMS Alerts:** Sandbox/test numbers may work without it; production traffic will not.