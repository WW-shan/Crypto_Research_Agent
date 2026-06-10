from __future__ import annotations

from datetime import UTC, datetime, timedelta
import inspect
import json
import subprocess
import sys
from types import MappingProxyType

import pytest

from crypto_alpha_agent.data.models import (
    DataSuitability,
    DefiYieldSnapshot,
    DexPairSnapshot,
    MarketCandle,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore


START = datetime(2026, 5, 1, tzinfo=UTC)
SCREEN_IDS = {
    "short_horizon_momentum_volatility_filter",
    "short_horizon_reversal_volatility_filter",
    "perp_spot_basis_funding_deviation",
    "derivatives_crowding_price_action",
    "defi_dex_regime_discovery",
    "cross_asset_ranking_turnover_cap",
    "regime_gated_cross_asset_momentum",
    "regime_gated_cross_asset_reversal",
    "funding_basis_convergence_liquidity_filter",
    "derivatives_crowding_recent_window_price_action",
    "defi_dex_liquidity_regime_watchlist",
}


def test_candidate_screen_catalog_declares_required_metadata():
    from crypto_alpha_agent.pipeline.candidate_screens import (
        candidate_screen_catalog,
    )

    catalog = candidate_screen_catalog()

    assert isinstance(catalog, MappingProxyType)
    assert set(catalog) == SCREEN_IDS
    for screen_id, definition in catalog.items():
        assert definition.screen_id == screen_id
        assert definition.required_record_types
        assert definition.min_history_bars >= 0
        assert isinstance(definition.cost_model_required, bool)
        assert definition.lookahead_risk_level in {"low", "medium", "high", "watchlist_only"}
        assert definition.execution_role in {"research_only", "watchlist_or_regime_only"}
        assert definition.blocked_reasons
        assert definition.uses_real_capital is False
        assert definition.live_order_routing is False


def test_candidate_screen_models_are_strict_and_catalog_avoids_strategy_registry():
    from pydantic import ValidationError

    from crypto_alpha_agent.pipeline import candidate_screens
    from crypto_alpha_agent.pipeline.candidate_screens import (
        CandidateScreenDefinition,
        CandidateScreenResult,
        CandidateScreenSignal,
    )

    assert "default_strategy_registry" not in inspect.getsource(candidate_screens)

    with pytest.raises(ValidationError):
        CandidateScreenDefinition(
            screen_id="short_horizon_momentum_volatility_filter",
            required_record_types=("market_candle",),
            min_history_bars="24",
            cost_model_required=True,
            lookahead_risk_level="low",
            execution_role="research_only",
            blocked_reasons=("missing_required_records",),
        )
    with pytest.raises(ValidationError):
        CandidateScreenDefinition(
            screen_id="short_horizon_momentum_volatility_filter",
            required_record_types=("market_candle",),
            min_history_bars=24,
            cost_model_required=True,
            lookahead_risk_level="low",
            execution_role="research_only",
            blocked_reasons=("missing_required_records",),
            unexpected="not allowed",
        )
    with pytest.raises(ValidationError):
        CandidateScreenSignal(
            screen_id="short_horizon_momentum_volatility_filter",
            symbol="BTC/USDT",
            observed_at=START,
            score="1.0",
            direction="long",
            evidence_record_count=1,
        )
    with pytest.raises(ValidationError):
        CandidateScreenResult(
            screen_id="short_horizon_momentum_volatility_filter",
            generated_at=START,
            symbols=("BTC/USDT",),
            timeframe="1h",
            readiness="candidate",
            required_record_types=("market_candle",),
            record_counts={"market_candle": 1},
            signals=[],
            blocked_reasons=[],
        )


def test_candidate_screen_import_does_not_load_strategy_or_paper_runtime():
    script = """
import importlib
import json
import sys

importlib.import_module("crypto_alpha_agent.pipeline.candidate_screens")

forbidden = sorted(
    name
    for name in sys.modules
    if name.startswith(("crypto_alpha_agent.strategy", "crypto_alpha_agent.evidence.paper", "crypto_alpha_agent.execution.paper", "crypto_alpha_agent.risk"))
)
print(json.dumps(forbidden))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == []


def test_candidate_screen_blocks_missing_database_without_creating_it(tmp_path):
    db_path = tmp_path / "missing.sqlite"

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "short_horizon_momentum_volatility_filter",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
    )

    assert not db_path.exists()
    assert result.readiness == "blocked"
    assert "missing_required_records" in result.blocked_reasons
    assert result.signals == ()
    assert result.uses_real_capital is False
    assert result.live_order_routing is False


def test_candidate_screen_blocks_when_required_records_are_missing(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            _market_candle("BTC/USDT", START + timedelta(hours=1), close=101),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "derivatives_crowding_price_action",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
    )

    assert result.readiness == "blocked"
    assert result.record_counts["market_candle"] == 2
    assert result.record_counts["long_short_account_ratio"] == 0
    assert result.record_counts["taker_buy_sell_volume"] == 0
    assert "missing_required_records" in result.blocked_reasons
    assert result.signals == ()


def test_candidate_screen_derives_signal_from_local_market_history_read_only(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            _market_candle("BTC/USDT", START + timedelta(hours=1), close=104),
            _market_candle("BTC/USDT", START + timedelta(hours=2), close=108),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    before = _record_snapshot(db_path)
    result = evaluate_candidate_screen(
        db_path,
        "short_horizon_momentum_volatility_filter",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
        min_history_bars=3,
    )

    assert result.readiness == "candidate"
    assert result.blocked_reasons == ()
    assert result.record_counts["market_candle"] == 3
    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.screen_id == "short_horizon_momentum_volatility_filter"
    assert signal.symbol == "BTC/USDT"
    assert signal.direction == "long"
    assert signal.score > 0
    assert signal.evidence_record_count == 3
    assert signal.uses_real_capital is False
    assert signal.live_order_routing is False
    assert _record_snapshot(db_path) == before


def test_redesigned_momentum_family_derives_read_only_signal(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            _market_candle("BTC/USDT", START + timedelta(hours=1), close=104),
            _market_candle("BTC/USDT", START + timedelta(hours=2), close=109),
            _market_candle("ETH/USDT", START, close=200),
            _market_candle("ETH/USDT", START + timedelta(hours=1), close=198),
            _market_candle("ETH/USDT", START + timedelta(hours=2), close=197),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    before = _record_snapshot(db_path)
    result = evaluate_candidate_screen(
        db_path,
        "regime_gated_cross_asset_momentum",
        symbols=["BTC/USDT", "ETH/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
        min_history_bars=3,
    )

    assert result.readiness == "candidate"
    assert result.blocked_reasons == ()
    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.screen_id == "regime_gated_cross_asset_momentum"
    assert signal.symbol == "BTC/USDT"
    assert signal.direction == "long"
    assert signal.score > 0
    assert signal.evidence_record_count == 3
    assert signal.uses_real_capital is False
    assert signal.live_order_routing is False
    assert _record_snapshot(db_path) == before


def test_candidate_screen_results_are_deeply_read_only(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            _market_candle("BTC/USDT", START + timedelta(hours=1), close=104),
            _market_candle("BTC/USDT", START + timedelta(hours=2), close=108),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "short_horizon_momentum_volatility_filter",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
        min_history_bars=3,
    )

    with pytest.raises(TypeError):
        result.record_counts["market_candle"] = 999
    with pytest.raises(TypeError):
        result.signals[0].inputs["gross_return"] = 999.0


def test_candidate_screen_ignores_unqualified_market_sources(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100, source="unqualified_source"),
            _market_candle(
                "BTC/USDT",
                START + timedelta(hours=1),
                close=104,
                source="unqualified_source",
            ),
            _market_candle(
                "BTC/USDT",
                START + timedelta(hours=2),
                close=108,
                source="unqualified_source",
            ),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "short_horizon_momentum_volatility_filter",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
        min_history_bars=3,
    )

    assert result.readiness == "blocked"
    assert result.record_counts["market_candle"] == 0
    assert "missing_required_records" in result.blocked_reasons
    assert result.signals == ()


def test_candidate_screen_generated_at_does_not_use_unrelated_future_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("ETH/USDT", START + timedelta(days=10), close=200),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "short_horizon_momentum_volatility_filter",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
    )

    assert result.generated_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert result.readiness == "blocked"


def test_derivative_context_requires_records_on_same_symbol(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            _market_candle("ETH/USDT", START, close=100),
            SourceRecord(
                record_id="binance_usdm:BTCUSDT:premium",
                source="binance_usdm",
                record_type="premium_index_kline",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "symbol": "BTCUSDT",
                    "timestamp": START.isoformat(),
                    "interval": "1h",
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.001,
                },
            ),
            SourceRecord(
                record_id="binance_usdm:ETHUSDT:basis",
                source="binance_usdm",
                record_type="basis",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "pair": "ETHUSDT",
                    "contract_type": "PERPETUAL",
                    "period": "1h",
                    "timestamp": START.isoformat(),
                    "index_price": 100.0,
                    "futures_price": 100.1,
                    "basis": 0.1,
                    "basis_rate": 0.001,
                },
            ),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "perp_spot_basis_funding_deviation",
        symbols=["BTC/USDT", "ETH/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=1),
        min_history_bars=1,
    )

    assert result.readiness == "blocked"
    assert "missing_required_records" in result.blocked_reasons
    assert result.signals == ()


def test_basis_funding_screen_requires_funding_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            SourceRecord(
                record_id="binance_usdm:BTCUSDT:premium",
                source="binance_usdm",
                record_type="premium_index_kline",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "symbol": "BTCUSDT",
                    "timestamp": START.isoformat(),
                    "interval": "1h",
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.001,
                },
            ),
            SourceRecord(
                record_id="binance_usdm:BTCUSDT:basis",
                source="binance_usdm",
                record_type="basis",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "pair": "BTCUSDT",
                    "contract_type": "PERPETUAL",
                    "period": "1h",
                    "timestamp": START.isoformat(),
                    "index_price": 100.0,
                    "futures_price": 100.1,
                    "basis": 0.1,
                    "basis_rate": 0.001,
                },
            ),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "perp_spot_basis_funding_deviation",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=1),
        min_history_bars=1,
    )

    assert result.record_counts["funding_rate"] == 0
    assert result.readiness == "blocked"
    assert "missing_required_records" in result.blocked_reasons
    assert result.signals == ()


def test_basis_funding_screen_uses_funding_records_for_signal(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            SourceRecord(
                record_id="binance_usdm:BTCUSDT:premium",
                source="binance_usdm",
                record_type="premium_index_kline",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "symbol": "BTCUSDT",
                    "timestamp": START.isoformat(),
                    "interval": "1h",
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.001,
                },
            ),
            SourceRecord(
                record_id="binance_usdm:BTCUSDT:basis",
                source="binance_usdm",
                record_type="basis",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "pair": "BTCUSDT",
                    "contract_type": "PERPETUAL",
                    "period": "1h",
                    "timestamp": START.isoformat(),
                    "index_price": 100.0,
                    "futures_price": 100.1,
                    "basis": 0.1,
                    "basis_rate": 0.001,
                },
            ),
            SourceRecord(
                record_id="ccxt:BTCUSDT:funding",
                source="ccxt",
                record_type="funding_rate",
                observed_at=START,
                payload={
                    "source": "ccxt",
                    "venue": "binance",
                    "symbol": "BTC/USDT",
                    "timestamp": START.isoformat(),
                    "funding_rate": 0.0005,
                },
            ),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "perp_spot_basis_funding_deviation",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=1),
        min_history_bars=1,
    )

    assert result.readiness == "candidate"
    assert result.record_counts["funding_rate"] == 1
    assert len(result.signals) == 1
    assert result.signals[0].inputs["funding_rate_records"] == 1


def test_basis_funding_screen_accepts_first_party_binance_usdm_funding(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            SourceRecord(
                record_id="binance_usdm:BTCUSDT:premium",
                source="binance_usdm",
                record_type="premium_index_kline",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "symbol": "BTCUSDT",
                    "timestamp": START.isoformat(),
                    "interval": "1h",
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.001,
                },
            ),
            SourceRecord(
                record_id="binance_usdm:BTCUSDT:basis",
                source="binance_usdm",
                record_type="basis",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "pair": "BTCUSDT",
                    "contract_type": "PERPETUAL",
                    "period": "1h",
                    "timestamp": START.isoformat(),
                    "index_price": 100.0,
                    "futures_price": 100.1,
                    "basis": 0.1,
                    "basis_rate": 0.001,
                },
            ),
            SourceRecord(
                record_id="binance_usdm:BTCUSDT:funding",
                source="binance_usdm",
                record_type="funding_rate",
                observed_at=START,
                payload={
                    "source": "binance_usdm",
                    "venue": "binance",
                    "symbol": "BTCUSDT",
                    "timestamp": START.isoformat(),
                    "funding_rate": 0.0005,
                },
            ),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "perp_spot_basis_funding_deviation",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=1),
        min_history_bars=1,
    )

    assert result.readiness == "candidate"
    assert result.record_counts["funding_rate"] == 1
    assert len(result.signals) == 1
    assert result.signals[0].inputs["funding_rate_records"] == 1


def test_reversal_screen_marks_downside_reversion_as_long(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            _market_candle("BTC/USDT", START + timedelta(hours=1), close=90),
            _market_candle("BTC/USDT", START + timedelta(hours=2), close=80),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "short_horizon_reversal_volatility_filter",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
        min_history_bars=3,
    )

    assert result.readiness == "candidate"
    assert result.signals[0].direction == "long"
    assert result.signals[0].inputs["gross_return"] == pytest.approx(-0.2)


def test_candidate_screen_dedupes_symbols_by_exchange_symbol(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100),
            _market_candle("BTC/USDT", START + timedelta(hours=1), close=104),
            _market_candle("BTC/USDT", START + timedelta(hours=2), close=108),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "short_horizon_momentum_volatility_filter",
        symbols=["BTC/USDT", "btcusdt"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=3),
        min_history_bars=3,
    )

    assert result.symbols == ("BTC/USDT",)
    assert result.readiness == "candidate"
    assert len(result.signals) == 1


def test_defi_dex_discovery_screen_is_watchlist_only(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _dex_pair("BTC", "USDT", START),
            _defi_yield("USDT", START),
        ]
    )

    from crypto_alpha_agent.pipeline.candidate_screens import evaluate_candidate_screen

    result = evaluate_candidate_screen(
        db_path,
        "defi_dex_regime_discovery",
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=1),
    )

    assert result.readiness == "blocked"
    assert "watchlist_only_source" in result.blocked_reasons
    assert result.record_counts["dex_pair"] == 1
    assert result.record_counts["defi_yield"] == 1
    assert len(result.signals) == 1
    assert result.signals[0].direction == "watchlist"


def _market_candle(
    symbol: str,
    timestamp: datetime,
    *,
    close: float,
    source: str = "binance_public",
) -> SourceRecord:
    return MarketCandle(
        source=source,
        venue="binance_usdm",
        symbol=symbol,
        timestamp=timestamp,
        timeframe="1h",
        open=close,
        high=close + 1,
        low=max(0, close - 1),
        close=close,
        volume=10,
        suitability=DataSuitability(),
    ).to_source_record()


def _dex_pair(base_token: str, quote_token: str, observed_at: datetime) -> SourceRecord:
    snapshot = DexPairSnapshot(
        source="dexscreener",
        chain="ethereum",
        dex="uniswap",
        pair_address=f"0x{base_token.lower()}",
        base_token=base_token,
        quote_token=quote_token,
        price_usd=100,
        liquidity_usd=1_000_000,
        volume_24h_usd=250_000,
        observed_at=observed_at,
    )
    return SourceRecord(
        record_id=f"dexscreener:{base_token}:{quote_token}:{observed_at.isoformat()}",
        source="dexscreener",
        record_type="dex_pair",
        observed_at=observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _defi_yield(symbol: str, observed_at: datetime) -> SourceRecord:
    snapshot = DefiYieldSnapshot(
        source="defillama",
        chain="Ethereum",
        project="Example",
        symbol=symbol,
        tvl_usd=1_000_000,
        apy=4.0,
        observed_at=observed_at,
    )
    return SourceRecord(
        record_id=f"defillama:yield:{symbol}:{observed_at.isoformat()}",
        source="defillama",
        record_type="defi_yield",
        observed_at=observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _record_snapshot(db_path) -> list[tuple[str, str, datetime]]:
    return [
        (record.record_id, record.record_type, record.observed_at)
        for record in ResearchDataStore(db_path).load_records()
    ]
