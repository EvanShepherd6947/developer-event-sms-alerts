from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .infrai_sms import SmsReceipt


class BuildEvent(BaseModel):
    kind: Literal["build"]
    event_id: str = Field(min_length=1, max_length=100)
    project: str = Field(min_length=1, max_length=80)
    pipeline: str = Field(min_length=1, max_length=80)
    status: Literal["passed", "failed"]
    commit_sha: str = Field(min_length=7, max_length=40)


class ReleaseEvent(BaseModel):
    kind: Literal["release"]
    event_id: str = Field(min_length=1, max_length=100)
    project: str = Field(min_length=1, max_length=80)
    environment: str = Field(min_length=1, max_length=40)
    version: str = Field(min_length=1, max_length=40)
    status: Literal["started", "completed", "failed"]


class DiagnosticEvent(BaseModel):
    kind: Literal["diagnostic"]
    event_id: str = Field(min_length=1, max_length=100)
    project: str = Field(min_length=1, max_length=80)
    component: str = Field(min_length=1, max_length=80)
    severity: Literal["info", "warning", "critical"]
    summary: str = Field(min_length=1, max_length=160)


DeveloperEvent = Annotated[
    BuildEvent | ReleaseEvent | DiagnosticEvent,
    Field(discriminator="kind"),
]


class AlertDecision(BaseModel):
    action: Literal["send", "skip"]
    reason: str
    body: str | None = None


class AlertResult(BaseModel):
    event_id: str
    action: Literal["sent", "skipped"]
    reason: str
    message_id: str | None = None


def decide_alert(event: BuildEvent | ReleaseEvent | DiagnosticEvent) -> AlertDecision:
    if isinstance(event, BuildEvent):
        if event.status != "failed":
            return AlertDecision(action="skip", reason="build_passed")
        return AlertDecision(
            action="send",
            reason="build_failed",
            body=f"BUILD FAILED | {event.project}/{event.pipeline} | commit {event.commit_sha[:8]}",
        )

    if isinstance(event, ReleaseEvent):
        if event.status != "failed":
            return AlertDecision(action="skip", reason=f"release_{event.status}")
        return AlertDecision(
            action="send",
            reason="release_failed",
            body=f"RELEASE FAILED | {event.project} {event.version} | {event.environment}",
        )

    if event.severity != "critical":
        return AlertDecision(action="skip", reason=f"diagnostic_{event.severity}")
    return AlertDecision(
        action="send",
        reason="critical_diagnostic",
        body=f"CRITICAL | {event.project}/{event.component} | {event.summary}",
    )


class DeveloperAlertService:
    def __init__(self, sender: object) -> None:
        if not hasattr(sender, "send"):
            raise TypeError("sender must provide send")
        self._sender = sender

    def process(
        self,
        event: BuildEvent | ReleaseEvent | DiagnosticEvent,
        recipient: str,
    ) -> AlertResult:
        decision = decide_alert(event)
        if decision.action == "skip":
            return AlertResult(event_id=event.event_id, action="skipped", reason=decision.reason)

        receipt: SmsReceipt = self._sender.send(  # type: ignore[attr-defined]
            to=recipient,
            body=decision.body or "",
            idempotency_key=f"developer-alert:{event.event_id}",
        )
        return AlertResult(
            event_id=event.event_id,
            action="sent",
            reason=decision.reason,
            message_id=receipt.message_id,
        )
