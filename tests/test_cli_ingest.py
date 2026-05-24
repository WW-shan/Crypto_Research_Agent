from __future__ import annotations

import json

import pytest

from crypto_alpha_agent.cli import main


class PassingRuntime:
    def health_check(self, *, command: str):
        return object()

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
    assert captured["capital_profile"]["current_capital_usd"] == 300.0


def test_ingest_source_without_allow_network_fails_closed(tmp_path):
    with pytest.raises(SystemExit):
        main(["ingest", "--db", str(tmp_path / "research.sqlite"), "--source", "defillama"])


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
