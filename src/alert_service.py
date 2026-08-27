from __future__ import annotations

import os
from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .developer_alerts import DeveloperAlertService, DeveloperEvent
from .infrai_sms import InfraiError, InfraiSmsClient


class AlertRequest(BaseModel):
    recipient: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    event: DeveloperEvent


app = FastAPI(title="Developer Event SMS Alerts")


def alert_pipeline() -> DeveloperAlertService:
    return DeveloperAlertService(InfraiSmsClient(os.environ.get("INFRAI_API_KEY", "")))


@app.post("/alerts", status_code=202)
def submit_alert(request: AlertRequest) -> dict[str, str | None]:
    try:
        return alert_pipeline().process(request.event, request.recipient).model_dump()
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code}) from exc
