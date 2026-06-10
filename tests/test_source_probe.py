from __future__ import annotations

import json

import crypto_alpha_agent.cli as cli_module
from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.source_probe import (
    available_probe_targets,
    probe_target,
)
from crypto_alpha_agent.data.store import ResearchDataStore


class FakeResponse:
    def __init__(self, payload, *, status_code: int = 200, json_error: Exception | None = None):
        self.payload = payload
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_code < 200 or self.status_code >= 300:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class SequenceSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_source_probe_catalog_includes_phase8_targets():
    target_ids = {target.target_id for target in available_probe_targets()}

    assert {
        "binance_usdm_funding_rate_history",
        "binance_usdm_open_interest_history",
        "binance_usdm_premium_index_klines",
        "binance_usdm_basis",
        "binance_usdm_global_long_short_account_ratio",
        "binance_usdm_taker_buy_sell_volume",
        "bybit_open_interest_history",
        "okx_open_interest",
        "dexscreener_pairs",
        "defillama_yield_pools",
        "defillama_fundamentals",
        "dune_query_result",
        "thegraph_pool_snapshot",
    }.issubset(target_ids)


def test_source_probe_lists_binance_funding_rate_history_target():
    target = next(
        item
        for item in available_probe_targets()
        if item.target_id == "binance_usdm_funding_rate_history"
    )

    assert target.source == "binance_usdm"
    assert target.feed == "funding_rate_history"
    assert target.endpoint_family == "GET /fapi/v1/fundingRate"
    assert "fundingRate" in target.url
    assert target.credential_requirement == "none"
    assert target.expected_fields == ("symbol", "fundingRate", "fundingTime")


def test_source_probe_lists_binance_taker_buy_sell_volume_target():
    target_ids = {target.target_id for target in available_probe_targets()}

    assert "binance_usdm_taker_buy_sell_volume" in target_ids


def test_binance_taker_buy_sell_volume_target_uses_public_endpoint():
    target = next(
        item
        for item in available_probe_targets()
        if item.target_id == "binance_usdm_taker_buy_sell_volume"
    )

    assert target.source == "binance_usdm"
    assert target.feed == "taker_buy_sell_volume"
    assert target.endpoint_family == "GET /futures/data/takerlongshortRatio"
    assert "takerlongshortRatio" in target.url
    assert target.credential_requirement == "none"
    assert target.expected_fields == ("buySellRatio", "buyVol", "sellVol", "timestamp")


def test_probe_without_network_records_blocked_source_health(tmp_path):
    db_path = tmp_path / "research.sqlite"

    result = probe_target(
        db_path=db_path,
        target_id="binance_usdm_open_interest_history",
        allow_network=False,
        route="direct",
        session=SequenceSession([]),
    )

    records = ResearchDataStore(db_path).load_records(record_type="source_health")
    assert result.provider_status == "Candidate"
    assert result.network_route == "blocked"
    assert result.parse_status == "blocked"
    assert result.blocked_reason == "network_not_allowed"
    assert result.exit_code == 2
    assert result.uses_real_capital is False
    assert result.live_order_routing is False
    assert records[0].payload["provider_status"] == "Candidate"
    assert records[0].payload["blocked_reason"] == "network_not_allowed"
    assert records[0].payload["network_route"] == "blocked"


def test_successful_direct_probe_records_research_usable_evidence(tmp_path):
    db_path = tmp_path / "research.sqlite"
    session = SequenceSession(
        [
            FakeResponse(
                [
                    {
                        "symbol": "BTCUSDT",
                        "sumOpenInterest": "20403.63700000",
                        "sumOpenInterestValue": "150570784.07809979",
                        "timestamp": "1583127900000",
                    }
                ]
            )
        ]
    )

    result = probe_target(
        db_path=db_path,
        target_id="binance_usdm_open_interest_history",
        allow_network=True,
        route="direct",
        session=session,
    )

    records = ResearchDataStore(db_path).load_records(record_type="source_health")
    assert result.provider_status == "ResearchUsable"
    assert result.status_transitions == ["Candidate", "Reachable", "Parseable", "ResearchUsable"]
    assert result.network_route == "direct"
    assert result.http_status == 200
    assert result.parse_status == "parsed"
    assert result.typed_record_count == 1
    assert result.exit_code == 0
    assert records[0].payload["typed_record_count"] == 1
    assert records[0].payload["endpoint_family"] == "GET /futures/data/openInterestHist"
    assert records[0].payload["url_family"] == "binance_usdm_open_interest_history"


def test_successful_proxy_probe_marks_reachable_via_proxy_without_leaking_proxy(tmp_path):
    db_path = tmp_path / "research.sqlite"
    session = SequenceSession(
        [
            FakeResponse(
                {
                    "pairs": [
                        {
                            "chainId": "ethereum",
                            "dexId": "uniswap",
                            "pairAddress": "0xabc",
                        }
                    ]
                }
            )
        ]
    )

    result = probe_target(
        db_path=db_path,
        target_id="dexscreener_pairs",
        allow_network=True,
        route="proxy",
        env={"HTTP_PROXY": "proxy-value-that-must-not-leak"},
        session=session,
    )

    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert result.provider_status == "ResearchUsable"
    assert "ReachableViaProxy" in result.status_transitions
    assert result.network_route == "proxy"
    assert "proxy-value-that-must-not-leak" not in serialized


def test_unexpected_shape_does_not_become_research_usable(tmp_path):
    db_path = tmp_path / "research.sqlite"
    session = SequenceSession([FakeResponse([{"unexpected": "shape"}])])

    result = probe_target(
        db_path=db_path,
        target_id="binance_usdm_open_interest_history",
        allow_network=True,
        route="direct",
        session=session,
    )

    assert result.provider_status == "Parseable"
    assert result.parse_status == "parsed"
    assert result.typed_record_count == 0
    assert result.blocked_reason == "missing_expected_fields:symbol,sumOpenInterest,timestamp"
    assert result.exit_code == 2


def test_credential_required_probe_blocks_without_marker(tmp_path):
    db_path = tmp_path / "research.sqlite"
    session = SequenceSession([])

    result = probe_target(
        db_path=db_path,
        target_id="dune_query_result",
        allow_network=True,
        route="direct",
        session=session,
    )

    assert result.provider_status == "Candidate"
    assert result.blocked_reason == "credential_required"
    assert result.parse_status == "blocked"
    assert result.exit_code == 2
    assert session.calls == []


def test_zero_typed_records_is_parseable_but_not_research_usable(tmp_path):
    db_path = tmp_path / "research.sqlite"
    session = SequenceSession([FakeResponse([])])

    result = probe_target(
        db_path=db_path,
        target_id="binance_usdm_open_interest_history",
        allow_network=True,
        route="direct",
        session=session,
    )

    assert result.provider_status == "Parseable"
    assert result.parse_status == "parsed"
    assert result.typed_record_count == 0
    assert result.blocked_reason == "no_typed_records"
    assert result.exit_code == 2


def test_parse_failure_records_parse_failed(tmp_path):
    db_path = tmp_path / "research.sqlite"
    session = SequenceSession([FakeResponse({}, json_error=ValueError("not json"))])

    result = probe_target(
        db_path=db_path,
        target_id="defillama_yield_pools",
        allow_network=True,
        route="direct",
        session=session,
    )

    assert result.provider_status == "Reachable"
    assert result.parse_status == "parse_failed"
    assert result.blocked_reason == "parse_failed"
    assert result.exit_code == 2


def test_source_probe_cli_lists_targets(capsys):
    exit_code = main(["source-probe", "--list-targets"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "source-probe"
    assert payload["llm_provider"] == "real"
    assert payload["llm_judgement"]["schema_name"] == "SourceResearchJudgement"
    assert "binance_usdm_open_interest_history" in [
        target["target_id"] for target in payload["targets"]
    ]
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False


def test_source_probe_cli_blocks_without_network(capsys, tmp_path):
    exit_code = main(
        [
            "source-probe",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--target",
            "binance_usdm_open_interest_history",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["command"] == "source-probe"
    assert payload["result"]["blocked_reason"] == "network_not_allowed"


def test_source_probe_cli_passes_proxy_environment(monkeypatch, capsys, tmp_path):
    captured = {}

    class DummyResult:
        exit_code = 0
        target_id = "dexscreener_pairs"

        def model_dump(self, **_: object):
            return {"network_route": "proxy"}

    def fake_probe_target(**kwargs):
        captured.update(kwargs)
        return DummyResult()

    monkeypatch.setenv("HTTP_PROXY", "proxy-value-that-must-not-leak")
    monkeypatch.setattr(cli_module, "probe_target", fake_probe_target)

    exit_code = main(
        [
            "source-probe",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--target",
            "dexscreener_pairs",
            "--allow-network",
            "--route",
            "proxy",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["route"] == "proxy"
    assert captured["env"]["HTTP_PROXY"] == "proxy-value-that-must-not-leak"
    assert "proxy-value-that-must-not-leak" not in json.dumps(payload)
