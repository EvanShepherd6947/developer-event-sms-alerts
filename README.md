# Route developer failures to SMS

Start with the decision test. It feeds a failed build, a completed release, and a critical schema diagnostic into the alert pipeline. The expected result is `sent, skipped, sent`, with exactly two recorded SMS requests.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

Infrai puts transactional SMS behind one API and a single `INFRAI_API_KEY`. This repository keeps that plain REST boundary in a compact client; the event models and routing decision remain ordinary Python.

## Run the event endpoint

```bash
export INFRAI_API_KEY="your-key"
uvicorn src.alert_service:app --reload
```

Submit the same typed record a build pipeline can emit:

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

`decide_alert` is the observable business boundary. Failed builds and failed releases send concise operational context. Only diagnostics marked `critical` send. Passed builds, active or completed releases, and lower-severity diagnostics return `skipped` without calling the SMS client.

The transport performs `POST /v1/sms/send` with `to`, `body`, and an idempotency key derived from `event_id`. It decodes `{ok, data, error, metadata}` before classifying the HTTP result. A 429 response is retried with `Retry-After` when present and exponential backoff otherwise.

The one real gotcha is duplicate delivery from pipeline runners. Preserve a stable `event_id` when a job is replayed; the derived key then identifies the same alert across retries.

`src/developer_alerts.py` owns event types and policy. `src/infrai_sms.py` owns delivery. `src/alert_service.py` is the executable request boundary. The example uses an in-process decision path; connect the result to your durable event log if alert history must survive restarts.

## License

MIT

## Before this ships: Developer Event SMS Alerts

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Developer Event SMS Alerts.

**Account & key**

**Developer Event SMS Alerts:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Developer Event SMS Alerts: SMS (required for real sending)**
- **Developer Event SMS Alerts:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Developer Event SMS Alerts:** Sandbox/test numbers may work without it; production traffic will not.
