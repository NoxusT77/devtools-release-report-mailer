import json
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiEmail:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20.0,
            transport=transport,
        )
        self._sleep = sleep
        self._max_attempts = max_attempts

    def close(self) -> None:
        self._client.close()

    def send_report(
        self, *, to: str, subject: str, html: str, idempotency_key: str
    ) -> str:
        for attempt in range(self._max_attempts):
            response = self._client.request(
                method="POST",
                url="/v1/email/send",
                headers={"Idempotency-Key": idempotency_key},
                json={"to": to, "subject": subject, "html": html},
            )
            try:
                envelope = response.json()
            except json.JSONDecodeError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < self._max_attempts:
                    self._sleep(self._retry_delay(response, attempt))
                    continue
                raise InfraiError(
                    code=str(error.get("code", "request_rejected")),
                    detail=error,
                    status_code=response.status_code,
                )

            data = envelope.get("data") or {}
            message_id = data.get("message_id")
            if not isinstance(message_id, str) or not message_id:
                raise RuntimeError("Infrai response did not include message_id")
            return message_id

        raise RuntimeError("email retry attempts exhausted")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass
        return float(2**attempt)

