from __future__ import annotations

import json
from typing import Any

import pytest

from crypto_alpha_agent.cli import main


class FakeSummary:
    def __init__(self, *, feed: str) -> None:
        self.feed = feed

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return {
            "source": "binance_usdm",
            "db_path": "test.sqlite",
            "feed": self.feed,
            "symbols": ["BTCUSDT"],
            "pairs": [],
            "period": "1h",
            "interval": "1h",
            "contract_type": None,
            "records_fetched": 1,
            "records_written": 1,
            "network_allowed": True,
            "uses_real_capital": False,
            "live_order_routing": False,
        }


class FakePublicSummary:
    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return {
            "source": "binance_public",
            "db_path": "test.sqlite",
            "symbols": ["BTCUSDT"],
            "timeframe": "1h",
            "year": 2026,
            "month": 5,
            "records_fetched": 1,
            "records_written": 1,
            "network_allowed": True,
            "uses_real_capital": False,
            "live_order_routing": False,
            "notes": [
                "research_and_paper_validation_only",
                "market=um_futures",
            ],
        }


class PassingLLM:
    def __call__(self, task):
        return json.dumps(
            {
                "schema_name": "DataReadinessJudgement",
                "decision": "add_data",
                "rationale": "Offline ingest check still needs public market rows.",
                "evidence_refs": list(task.evidence_refs),
                "missing_fields": ["market_candle", "funding_rate"],
                "next_actions": ["Ingest CCXT OHLCV and funding history."],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )


class PassingRuntime:
    def __init__(self) -> None:
        self.llm = PassingLLM()

    def health_check(self, *, command: str):
        return object()

    def structured_call(self, task, output_model):
        from crypto_alpha_agent.llm.runtime import parse_structured_llm_json

        return parse_structured_llm_json(self.llm(task), output_model)

    def metadata(self):
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": "research",
            "llm_model": "test-real-model",
        }


@pytest.fixture(autouse=True)
def required_llm_runtime(monkeypatch):
    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="research": PassingRuntime(),
    )


def test_ingest_offline_check_reports_no_live_capital(capsys, tmp_path):
    exit_code = main(["ingest", "--offline-check", "--db", str(tmp_path / "research.sqlite")])

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["command"] == "ingest"
    assert captured["uses_real_capital"] is False
    assert captured["live_order_routing"] is False
    assert captured["llm_provider"] == "real"
    assert captured["llm_judgement"]["schema_name"] == "DataReadinessJudgement"
    assert captured["capital_profile"]["current_capital_usd"] == 300.0


def test_ingest_source_without_allow_network_fails_closed(tmp_path):
    with pytest.raises(SystemExit):
        main(["ingest", "--db", str(tmp_path / "research.sqlite"), "--source", "defillama"])


def test_ingest_rejects_invalid_llm_data_readiness(monkeypatch, capsys, tmp_path):
    class BadLLM:
        def __call__(self, _task):
            return json.dumps(
                {
                    "schema_name": "DataReadinessJudgement",
                    "decision": "add_data",
                    "rationale": "Bad evidence ref should fail closed.",
                    "evidence_refs": ["missing-ref"],
                    "missing_fields": ["market_candle"],
                    "next_actions": ["Do not accept unsupported refs."],
                    "uses_real_capital": False,
                    "live_order_routing": False,
                }
            )

    runtime = PassingRuntime()
    runtime.llm = BadLLM()
    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="research": runtime,
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["ingest", "--offline-check", "--db", str(tmp_path / "research.sqlite")])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "unknown evidence refs" in captured.err


def test_ingest_offline_check_creates_db_and_reports_current_capital(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"

    exit_code = main(
        [
            "ingest",
            "--offline-check",
            "--current-capital-usd",
            "125",
            "--db",
            str(db_path),
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert db_path.exists()
    assert captured["db_path"] == str(db_path)
    assert captured["capital_profile"]["current_capital_usd"] == 125.0


def test_ingest_cli_preserves_binance_public_source_declaration(capsys, tmp_path):
    exit_code = main(
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "binance-public",
            "--allow-network",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "ingest"
    assert payload["mode"] == "network_declared"
    assert payload["sources_requested"] == ["binance-public"]
    assert "ingestion" not in payload
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False


def test_ingest_cli_runs_binance_public_um_futures_klines(capsys, tmp_path, monkeypatch):
    calls = []

    def fake_ingest(db_path, **kwargs):
        calls.append((db_path, kwargs))
        return FakePublicSummary()

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.ingest_binance_public_um_futures_month",
        fake_ingest,
        raising=False,
    )

    exit_code = main(
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "binance-public",
            "--allow-network",
            "--public-data-market",
            "um-futures",
            "--symbol",
            "BTCUSDT",
            "--timeframe",
            "1h",
            "--year",
            "2026",
            "--month",
            "5",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "ingest"
    assert payload["ingestion"]["source"] == "binance_public"
    assert payload["ingestion"]["uses_real_capital"] is False
    assert payload["ingestion"]["live_order_routing"] is False
    assert calls[0][1] == {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "year": 2026,
        "month": 5,
        "allow_network": True,
    }


def test_ingest_cli_runs_binance_usdm_premium_index_klines(capsys, tmp_path, monkeypatch):
    calls = []

    def fake_ingest(db_path, **kwargs):
        calls.append((db_path, kwargs))
        return FakeSummary(feed="premium_index_klines")

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.ingest_binance_usdm_premium_index_klines",
        fake_ingest,
        raising=False,
    )

    exit_code = main(
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "binance-usdm",
            "--allow-network",
            "--binance-usdm-feed",
            "premium-index-klines",
            "--symbol",
            "BTCUSDT",
            "--interval",
            "1h",
            "--limit",
            "1",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ingestion"]["feed"] == "premium_index_klines"
    assert calls[0][1]["symbol"] == "BTCUSDT"
    assert calls[0][1]["interval"] == "1h"
    assert calls[0][1]["allow_network"] is True


def test_ingest_cli_runs_binance_usdm_basis(capsys, tmp_path, monkeypatch):
    calls = []

    def fake_ingest(db_path, **kwargs):
        calls.append((db_path, kwargs))
        return FakeSummary(feed="basis")

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.ingest_binance_usdm_basis",
        fake_ingest,
        raising=False,
    )

    exit_code = main(
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "binance-usdm",
            "--allow-network",
            "--binance-usdm-feed",
            "basis",
            "--pair",
            "BTCUSDT",
            "--contract-type",
            "PERPETUAL",
            "--period",
            "1h",
            "--limit",
            "1",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ingestion"]["feed"] == "basis"
    assert calls[0][1]["pair"] == "BTCUSDT"
    assert calls[0][1]["contract_type"] == "PERPETUAL"
    assert calls[0][1]["period"] == "1h"


@pytest.mark.parametrize(
    ("feed", "args"),
    [
        ("premium-index-klines", ["--interval", "1h"]),
        ("basis", ["--pair", "BTCUSDT", "--period", "1h"]),
        ("global-long-short-account-ratio", ["--symbol", "BTCUSDT"]),
        ("taker-buy-sell-volume", ["--symbol", "BTCUSDT"]),
    ],
)
def test_ingest_cli_rejects_incomplete_binance_usdm_arguments(tmp_path, feed, args):
    with pytest.raises(SystemExit):
        main(
            [
                "ingest",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--source",
                "binance-usdm",
                "--allow-network",
                "--binance-usdm-feed",
                feed,
                *args,
            ]
        )


def test_ingest_cli_rejects_binance_public_without_allow_network(tmp_path):
    with pytest.raises(SystemExit):
        main(
            [
                "ingest",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--source",
                "binance-public",
                "--public-data-market",
                "um-futures",
                "--symbol",
                "BTCUSDT",
                "--timeframe",
                "1h",
                "--year",
                "2026",
                "--month",
                "5",
            ]
        )
