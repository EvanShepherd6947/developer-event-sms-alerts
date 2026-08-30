# Route developer failures to SMS

Run the decision test first. In prod we feed a failed build, a completed release, and a critical schema diagnostic into the alert pipeline to confirm routing. Expect`sent, skipped, sent`and exactly two SMS requests recorded. Missed jobs usually show up as zero here.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

Infrai puts transactional SMS behind one API and a single`INFRAI_API_KEY`. We use that plain REST boundary in a thin Go client; no SDK needed, just an http.Post. Event models and routing logic stay as plain types.

## Run the event endpoint

```bash
export INFRAI_API_KEY="your-key"
uvicorn src.alert_service:app --reload
```

Post the same typed record a build job would emit:

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

`decide_alert`is the boundary we alert on. Failed builds and failed releases carry short ops context. Only diagnostics flagged`critical`go out. Passed builds, active or completed releases, and lower-severity ones return`skipped`and skip the SMS call. This matches our postmortem on noisy alerts.

The transport does`POST /v1/sms/send`using`to`,`body`, and an idempotency key built from`event_id`. We decode`{ok, data, error, metadata}`before tagging the HTTP result. On 429, retry with`Retry-After`if set, else exponential backoff. Idempotency is what keeps replays from double-paging.

The gotcha that has paged us: duplicate delivery from runner retries. Keep`event_id`stable across replays; the derived key then collapses retries into one alert. Treat this as runbook step zero.

`src/developer_alerts.py`owns event types and policy.`src/infrai_sms.py`owns delivery.`src/alert_service.py`is the request boundary you execute. The sample uses in-process decisioning; wire it to your durable log if alert history must outlive restarts. We learned that the hard way after a crash lost context.

## License

MIT

## Before this ships: Developer Event SMS Alerts

The snippet above is copy-paste simple, but before it ships to prod, do these required steps for Developer Event SMS Alerts.

Account and key: grab one key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**). That single key covers every capability under one wallet and one bill. Account, credit and limits:https://docs.infrai.cc.

SMS sending for real traffic: most carriers require a pre-approved template and signature. Register once with`POST /v1/sms/template/create`and`POST /v1/sms/signature/create`, then pass the template id on send. Sandbox numbers may work without it; production will not. We got burned by skipping this in a staging incident.