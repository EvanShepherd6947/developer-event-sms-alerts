from src.developer_alerts import (
    BuildEvent,
    DeveloperAlertService,
    DiagnosticEvent,
    ReleaseEvent,
)
from src.infrai_sms import SmsReceipt


class RecordingSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send(self, *, to: str, body: str, idempotency_key: str) -> SmsReceipt:
        self.calls.append({"to": to, "body": body, "idempotency_key": idempotency_key})
        return SmsReceipt(message_id="sms_001", metadata={"pipeline": "test"})


def test_pipeline_sends_only_actionable_developer_events() -> None:
    sender = RecordingSender()
    service = DeveloperAlertService(sender)
    events = [
        BuildEvent(
            kind="build",
            event_id="build-901",
            project="warehouse",
            pipeline="daily-load",
            status="failed",
            commit_sha="2f60d831a10b",
        ),
        ReleaseEvent(
            kind="release",
            event_id="release-77",
            project="warehouse",
            environment="production",
            version="2026.08.26",
            status="completed",
        ),
        DiagnosticEvent(
            kind="diagnostic",
            event_id="diag-42",
            project="warehouse",
            component="schema-check",
            severity="critical",
            summary="Source column type changed",
        ),
    ]

    results = [service.process(event, "+15550102030") for event in events]

    assert [result.action for result in results] == ["sent", "skipped", "sent"]
    assert [result.reason for result in results] == [
        "build_failed",
        "release_completed",
        "critical_diagnostic",
    ]
    assert sender.calls == [
        {
            "to": "+15550102030",
            "body": "BUILD FAILED | warehouse/daily-load | commit 2f60d831",
            "idempotency_key": "developer-alert:build-901",
        },
        {
            "to": "+15550102030",
            "body": "CRITICAL | warehouse/schema-check | Source column type changed",
            "idempotency_key": "developer-alert:diag-42",
        },
    ]
