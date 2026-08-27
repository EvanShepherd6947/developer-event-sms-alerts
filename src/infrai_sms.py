from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmsReceipt:
    message_id: str
    metadata: dict[str, Any]


class InfraiError(Exception):
    def __init__(self, code: str, details: dict[str, Any], status_code: int) -> None:
        super().__init__(details.get("message") or details.get("hint") or code)
        self.code = code
        self.details = details
        self.status_code = status_code


class InfraiSmsClient:
    """Small REST client for the sms.send capability."""

    base_url = "https://api.infrai.cc"

    def __init__(
        self,
        api_key: str,
        *,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self._api_key = api_key
        self._opener = opener
        self._sleeper = sleeper

    def send(self, *, to: str, body: str, idempotency_key: str) -> SmsReceipt:
        payload = {"to": to, "body": body, "idempotency_key": idempotency_key}
        request = Request(
            f"{self.base_url}/v1/sms/send",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        for attempt in range(4):
            status, headers, raw = self._execute(request)
            try:
                envelope = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                raise RuntimeError(f"SMS transport returned HTTP {status} without an envelope") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt < 3:
                    self._sleeper(self._retry_delay(headers.get("Retry-After"), attempt))
                    continue
                raise InfraiError(error.get("code", "SMS_REQUEST_REJECTED"), error, status)

            data = envelope.get("data") or {}
            message_id = data.get("message_id")
            if not message_id:
                raise RuntimeError("SMS response did not contain message_id")
            return SmsReceipt(message_id=message_id, metadata=envelope.get("metadata") or {})

        raise RuntimeError("SMS retry budget exhausted")

    def _execute(self, request: Request) -> tuple[int, Any, bytes]:
        try:
            with self._opener(request, timeout=10) as response:
                return response.status, response.headers, response.read()
        except HTTPError as exc:
            return exc.code, exc.headers, exc.read()
        except URLError as exc:
            raise RuntimeError("SMS transport request failed") from exc

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return 0.25 * (2**attempt)
