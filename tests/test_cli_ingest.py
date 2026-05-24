from __future__ import annotations

import json

import pytest

from crypto_alpha_agent.cli import main


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
