from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    attempts: int = Field(ge=1)
    success: bool
    failure: str | None = None


class HttpClient:
    def __init__(
        self,
        *,
        source: str,
        session: Any,
        max_attempts: int = 3,
        timeout_seconds: float = 30.0,
        backoff_seconds: float = 0.5,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")

        self.source = source
        self.session = session
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep or time.sleep
        self.last_health: SourceHealth | None = None

    def get(self, url: str, **kwargs: Any) -> tuple[Any, SourceHealth]:
        return self._request("get", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> tuple[Any, SourceHealth]:
        return self._request("post", url, **kwargs)

    def _request(self, method: Literal["get", "post"], url: str, **kwargs: Any) -> tuple[Any, SourceHealth]:
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout_seconds

        last_failure: str | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = getattr(self.session, method)(url, **kwargs)
                status_code = getattr(response, "status_code", None)
                if status_code is not None and not 200 <= int(status_code) < 300:
                    raise RuntimeError(f"HTTP {status_code}")
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()

                health = SourceHealth(source=self.source, attempts=attempt, success=True)
                self.last_health = health
                return response, health
            except Exception as exc:
                last_failure = str(exc) or exc.__class__.__name__
                if attempt < self.max_attempts and self.backoff_seconds > 0:
                    self.sleep(self.backoff_seconds)

        health = SourceHealth(
            source=self.source,
            attempts=self.max_attempts,
            success=False,
            failure=last_failure,
        )
        self.last_health = health
        raise RuntimeError(
            f"{self.source} request failed after {health.attempts} attempts: {health.failure}; "
            f"health={health.model_dump()}"
        )
