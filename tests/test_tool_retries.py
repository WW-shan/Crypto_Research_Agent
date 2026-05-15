from __future__ import annotations

import pytest


class FakeResponse:
    def __init__(self, payload: dict, *, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code < 200 or self.status_code >= 300:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.payload


class SequenceSession:
    def __init__(self, outcomes: list[FakeResponse | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_http_client_retries_once_then_returns_health_without_real_sleep():
    from crypto_alpha_agent.tools.http import HttpClient

    sleeps: list[float] = []
    session = SequenceSession(
        [
            TimeoutError("temporary timeout"),
            FakeResponse({"ok": True}),
        ]
    )
    client = HttpClient(
        source="dune",
        session=session,
        max_attempts=3,
        timeout_seconds=7,
        backoff_seconds=0.25,
        sleep=sleeps.append,
    )

    response, health = client.get("https://example.test/data")

    assert response.json() == {"ok": True}
    assert health.source == "dune"
    assert health.attempts == 2
    assert health.success is True
    assert health.failure is None
    assert sleeps == [0.25]


def test_http_client_exhausts_attempts_with_clear_health_details():
    from crypto_alpha_agent.tools.http import HttpClient

    session = SequenceSession(
        [
            FakeResponse({"error": "busy"}, status_code=503),
            FakeResponse({"error": "still busy"}, status_code=503),
        ]
    )
    client = HttpClient(
        source="defillama",
        session=session,
        max_attempts=2,
        timeout_seconds=3,
        backoff_seconds=0,
        sleep=lambda _: None,
    )

    with pytest.raises(RuntimeError, match="defillama request failed after 2 attempts.*HTTP 503"):
        client.get("https://example.test/protocol/aave")

    assert client.last_health is not None
    assert client.last_health.source == "defillama"
    assert client.last_health.attempts == 2
    assert client.last_health.success is False
    assert "HTTP 503" in str(client.last_health.failure)


def test_http_client_passes_timeout_to_fake_session():
    from crypto_alpha_agent.tools.http import HttpClient

    session = SequenceSession([FakeResponse({"ok": True})])
    client = HttpClient(
        source="thegraph",
        session=session,
        timeout_seconds=11,
        sleep=lambda _: None,
    )

    client.post("https://example.test/subgraph", json={"query": "{ pools { id } }"})

    assert session.calls == [
        (
            "POST",
            "https://example.test/subgraph",
            {"json": {"query": "{ pools { id } }"}, "timeout": 11},
        )
    ]


def test_adapter_exposes_source_health_after_successful_fake_request():
    from crypto_alpha_agent.tools.dune import DuneClient

    session = SequenceSession([FakeResponse({"result": {"rows": [{"asset": "SOL"}]}})])
    client = DuneClient(
        api_key="test-key",
        session=session,
        timeout_seconds=5,
        sleep=lambda _: None,
    )

    result = client.execute_query(42)

    assert result.rows == [{"asset": "SOL"}]
    assert client.last_health is not None
    assert client.last_health.source == "dune"
    assert client.last_health.attempts == 1
    assert client.last_health.success is True
