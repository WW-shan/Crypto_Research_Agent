from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from types import MappingProxyType
from typing import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crypto_alpha_agent.data.models import RecordType, SourceRecord

CandidateScreenId = Literal[
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
]
CandidateScreenReadiness = Literal["candidate", "blocked"]
CandidateScreenDirection = Literal["long", "short", "watchlist", "regime"]
CandidateExecutionRole = Literal["research_only", "watchlist_or_regime_only"]
CandidateLookaheadRisk = Literal["low", "medium", "high", "watchlist_only"]
CandidateBlockedReason = Literal[
    "missing_required_records",
    "insufficient_history_window",
    "lookahead_risk",
    "watchlist_only_source",
    "cost_model_required",
    "no_candidate_signal",
]
_QUALIFIED_SOURCES_BY_RECORD_TYPE: dict[RecordType, frozenset[str]] = {
    "market_candle": frozenset({"binance_public", "ccxt"}),
    "premium_index_kline": frozenset({"binance_usdm"}),
    "basis": frozenset({"binance_usdm"}),
    "long_short_account_ratio": frozenset({"binance_usdm"}),
    "taker_buy_sell_volume": frozenset({"binance_usdm"}),
    "dex_pair": frozenset({"dexscreener"}),
    "defi_yield": frozenset({"defillama"}),
    "funding_rate": frozenset({"ccxt", "binance_usdm"}),
    "open_interest": frozenset({"ccxt", "binance_usdm"}),
    "research_snapshot": frozenset({"local_research"}),
    "source_health": frozenset({"source_probe"}),
}


class _StrictScreenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        frozen=True,
    )


class CandidateScreenDefinition(_StrictScreenModel):
    screen_id: CandidateScreenId
    required_record_types: tuple[RecordType, ...]
    min_history_bars: int = Field(ge=0)
    cost_model_required: bool
    lookahead_risk_level: CandidateLookaheadRisk
    execution_role: CandidateExecutionRole
    blocked_reasons: tuple[CandidateBlockedReason, ...]
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class CandidateScreenSignal(_StrictScreenModel):
    screen_id: CandidateScreenId
    symbol: str
    observed_at: datetime
    score: float
    direction: CandidateScreenDirection
    evidence_record_count: int = Field(ge=1)
    inputs: Mapping[str, int | float | str] = Field(default_factory=dict)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @model_validator(mode="after")
    def _freeze_inputs(self) -> CandidateScreenSignal:
        if not isinstance(self.inputs, MappingProxyType):
            object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        return self


class CandidateScreenResult(_StrictScreenModel):
    screen_id: CandidateScreenId
    generated_at: datetime
    symbols: tuple[str, ...]
    timeframe: str
    readiness: CandidateScreenReadiness
    required_record_types: tuple[RecordType, ...]
    record_counts: Mapping[RecordType, int]
    signals: tuple[CandidateScreenSignal, ...] = Field(default_factory=tuple)
    blocked_reasons: tuple[CandidateBlockedReason, ...] = Field(default_factory=tuple)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @model_validator(mode="after")
    def _freeze_record_counts(self) -> CandidateScreenResult:
        if not isinstance(self.record_counts, MappingProxyType):
            object.__setattr__(
                self,
                "record_counts",
                MappingProxyType(dict(self.record_counts)),
            )
        return self


@dataclass(frozen=True)
class _MarketRow:
    symbol: str
    timestamp: datetime
    close: float


def candidate_screen_catalog() -> Mapping[CandidateScreenId, CandidateScreenDefinition]:
    catalog = {
        definition.screen_id: definition
        for definition in (
            CandidateScreenDefinition(
                screen_id="short_horizon_momentum_volatility_filter",
                required_record_types=("market_candle",),
                min_history_bars=24,
                cost_model_required=True,
                lookahead_risk_level="low",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="short_horizon_reversal_volatility_filter",
                required_record_types=("market_candle",),
                min_history_bars=24,
                cost_model_required=True,
                lookahead_risk_level="low",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="perp_spot_basis_funding_deviation",
                required_record_types=(
                    "market_candle",
                    "premium_index_kline",
                    "basis",
                    "funding_rate",
                ),
                min_history_bars=24,
                cost_model_required=True,
                lookahead_risk_level="medium",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="derivatives_crowding_price_action",
                required_record_types=(
                    "market_candle",
                    "long_short_account_ratio",
                    "taker_buy_sell_volume",
                ),
                min_history_bars=24,
                cost_model_required=True,
                lookahead_risk_level="medium",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="defi_dex_regime_discovery",
                required_record_types=("dex_pair", "defi_yield"),
                min_history_bars=0,
                cost_model_required=False,
                lookahead_risk_level="watchlist_only",
                execution_role="watchlist_or_regime_only",
                blocked_reasons=(
                    "missing_required_records",
                    "lookahead_risk",
                    "watchlist_only_source",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="cross_asset_ranking_turnover_cap",
                required_record_types=("market_candle",),
                min_history_bars=72,
                cost_model_required=True,
                lookahead_risk_level="low",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="regime_gated_cross_asset_momentum",
                required_record_types=("market_candle",),
                min_history_bars=72,
                cost_model_required=True,
                lookahead_risk_level="low",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="regime_gated_cross_asset_reversal",
                required_record_types=("market_candle",),
                min_history_bars=72,
                cost_model_required=True,
                lookahead_risk_level="low",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="funding_basis_convergence_liquidity_filter",
                required_record_types=(
                    "market_candle",
                    "premium_index_kline",
                    "basis",
                    "funding_rate",
                ),
                min_history_bars=24,
                cost_model_required=True,
                lookahead_risk_level="medium",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="derivatives_crowding_recent_window_price_action",
                required_record_types=(
                    "market_candle",
                    "long_short_account_ratio",
                    "taker_buy_sell_volume",
                ),
                min_history_bars=24,
                cost_model_required=True,
                lookahead_risk_level="medium",
                execution_role="research_only",
                blocked_reasons=(
                    "missing_required_records",
                    "insufficient_history_window",
                    "lookahead_risk",
                    "cost_model_required",
                    "no_candidate_signal",
                ),
            ),
            CandidateScreenDefinition(
                screen_id="defi_dex_liquidity_regime_watchlist",
                required_record_types=("dex_pair", "defi_yield"),
                min_history_bars=0,
                cost_model_required=False,
                lookahead_risk_level="watchlist_only",
                execution_role="watchlist_or_regime_only",
                blocked_reasons=(
                    "missing_required_records",
                    "lookahead_risk",
                    "watchlist_only_source",
                    "no_candidate_signal",
                ),
            ),
        )
    }
    return MappingProxyType(catalog)


def default_candidate_screen_catalog() -> Mapping[CandidateScreenId, CandidateScreenDefinition]:
    return candidate_screen_catalog()


def list_candidate_screen_definitions() -> tuple[CandidateScreenDefinition, ...]:
    return tuple(candidate_screen_catalog().values())


def evaluate_candidate_screen(
    db_path: str | Path,
    screen_id: CandidateScreenId,
    *,
    symbols: list[str],
    timeframe: str,
    evaluation_start: datetime | None = None,
    evaluation_end: datetime | None = None,
    min_history_bars: int | None = None,
) -> CandidateScreenResult:
    catalog = candidate_screen_catalog()
    if screen_id not in catalog:
        raise KeyError(f"unknown candidate screen: {screen_id}")

    definition = catalog[screen_id]
    normalized_symbols = tuple(_dedupe_symbols_by_exchange_symbol(symbols))
    records = _load_records_read_only(db_path)
    relevant_records = [
        record
        for record in records
        if _record_matches_request(
            record,
            normalized_symbols,
            timeframe,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )
    ]
    record_counts = {
        record_type: sum(1 for record in relevant_records if record.record_type == record_type)
        for record_type in definition.required_record_types
    }

    blocked_reasons: list[CandidateBlockedReason] = []
    if any(record_counts[record_type] == 0 for record_type in definition.required_record_types):
        blocked_reasons.append("missing_required_records")

    effective_min_history = (
        definition.min_history_bars if min_history_bars is None else min_history_bars
    )
    market_by_symbol = _market_rows_by_symbol(relevant_records, normalized_symbols, timeframe)
    if "market_candle" in definition.required_record_types and any(
        len(rows) < effective_min_history for rows in market_by_symbol.values()
    ):
        blocked_reasons.append("insufficient_history_window")
    if _requires_per_symbol_record_completeness(definition) and not _has_complete_symbol_records(
        definition,
        relevant_records,
        normalized_symbols,
    ):
        blocked_reasons.append("missing_required_records")

    signals: list[CandidateScreenSignal] = []
    if not blocked_reasons:
        signals = list(
            _screen_signals(
                definition,
                relevant_records,
                market_by_symbol,
                normalized_symbols,
            )
        )
        if not signals:
            blocked_reasons.append("no_candidate_signal")

    if definition.execution_role == "watchlist_or_regime_only" and signals:
        blocked_reasons.append("watchlist_only_source")

    blocked_reasons = _dedupe_preserving_order(blocked_reasons)
    return CandidateScreenResult(
        screen_id=screen_id,
        generated_at=_latest_observed_at(relevant_records),
        symbols=normalized_symbols,
        timeframe=timeframe,
        readiness="blocked" if blocked_reasons else "candidate",
        required_record_types=definition.required_record_types,
        record_counts=record_counts,
        signals=tuple(signals),
        blocked_reasons=tuple(blocked_reasons),
        uses_real_capital=False,
        live_order_routing=False,
    )


def evaluate_candidate_screens(
    db_path: str | Path,
    *,
    symbols: list[str],
    timeframe: str,
    evaluation_start: datetime | None = None,
    evaluation_end: datetime | None = None,
) -> tuple[CandidateScreenResult, ...]:
    return tuple(
        evaluate_candidate_screen(
            db_path,
            screen_id,
            symbols=symbols,
            timeframe=timeframe,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )
        for screen_id in candidate_screen_catalog()
    )


def _screen_signals(
    definition: CandidateScreenDefinition,
    records: list[SourceRecord],
    market_by_symbol: dict[str, list[_MarketRow]],
    symbols: tuple[str, ...],
) -> tuple[CandidateScreenSignal, ...]:
    if definition.screen_id in {
        "short_horizon_momentum_volatility_filter",
        "regime_gated_cross_asset_momentum",
    }:
        return _market_return_signals(definition, market_by_symbol, direction_mode="momentum")
    if definition.screen_id in {
        "short_horizon_reversal_volatility_filter",
        "regime_gated_cross_asset_reversal",
    }:
        return _market_return_signals(definition, market_by_symbol, direction_mode="reversal")
    if definition.screen_id == "cross_asset_ranking_turnover_cap":
        return _cross_asset_ranking_signals(definition, market_by_symbol)
    if definition.screen_id in {
        "defi_dex_regime_discovery",
        "defi_dex_liquidity_regime_watchlist",
    }:
        return _watchlist_signals(definition, records, symbols)
    if definition.screen_id in {
        "perp_spot_basis_funding_deviation",
        "funding_basis_convergence_liquidity_filter",
    }:
        return _derivatives_context_signals(
            definition,
            records,
            symbols,
            ("premium_index_kline", "basis", "funding_rate"),
        )
    if definition.screen_id in {
        "derivatives_crowding_price_action",
        "derivatives_crowding_recent_window_price_action",
    }:
        return _derivatives_context_signals(
            definition,
            records,
            symbols,
            ("long_short_account_ratio", "taker_buy_sell_volume"),
        )
    return tuple()


def _market_return_signals(
    definition: CandidateScreenDefinition,
    market_by_symbol: dict[str, list[_MarketRow]],
    *,
    direction_mode: Literal["momentum", "reversal"],
) -> tuple[CandidateScreenSignal, ...]:
    signals: list[CandidateScreenSignal] = []
    for symbol, rows in market_by_symbol.items():
        if len(rows) < 2 or rows[0].close == 0:
            continue
        gross_return = (rows[-1].close - rows[0].close) / rows[0].close
        if direction_mode == "momentum" and gross_return <= 0:
            continue
        if direction_mode == "reversal" and gross_return >= 0:
            continue
        direction: CandidateScreenDirection = "long"
        signals.append(
            CandidateScreenSignal(
                screen_id=definition.screen_id,
                symbol=symbol,
                observed_at=rows[-1].timestamp,
                score=abs(float(gross_return)),
                direction=direction,
                evidence_record_count=len(rows),
                inputs={
                    "first_close": rows[0].close,
                    "latest_close": rows[-1].close,
                    "gross_return": float(gross_return),
                },
            )
        )
    return tuple(sorted(signals, key=lambda signal: (-signal.score, signal.symbol)))


def _cross_asset_ranking_signals(
    definition: CandidateScreenDefinition,
    market_by_symbol: dict[str, list[_MarketRow]],
) -> tuple[CandidateScreenSignal, ...]:
    ranked = _market_return_signals(definition, market_by_symbol, direction_mode="momentum")
    if not ranked:
        return tuple()
    return ranked[: max(1, min(3, len(ranked)))]


def _watchlist_signals(
    definition: CandidateScreenDefinition,
    records: list[SourceRecord],
    symbols: tuple[str, ...],
) -> tuple[CandidateScreenSignal, ...]:
    pair_symbols = _requested_symbol_pairs(symbols)
    dex_records = [
        record
        for record in records
        if record.record_type == "dex_pair"
        and (
            str(record.payload.get("base_token", "")).upper(),
            str(record.payload.get("quote_token", "")).upper(),
        )
        in pair_symbols
    ]
    if not dex_records:
        return tuple()
    latest = max(dex_records, key=lambda record: record.observed_at)
    symbol = f"{latest.payload.get('base_token', '')}/{latest.payload.get('quote_token', '')}".upper()
    score = float(latest.payload.get("liquidity_usd") or 0) + float(
        latest.payload.get("volume_24h_usd") or 0
    )
    return (
        CandidateScreenSignal(
            screen_id=definition.screen_id,
            symbol=symbol,
            observed_at=latest.observed_at,
            score=score,
            direction="watchlist",
            evidence_record_count=len(dex_records),
            inputs={
                "dex_pair_records": len(dex_records),
                "liquidity_usd": float(latest.payload.get("liquidity_usd") or 0),
                "volume_24h_usd": float(latest.payload.get("volume_24h_usd") or 0),
            },
        ),
    )


def _derivatives_context_signals(
    definition: CandidateScreenDefinition,
    records: list[SourceRecord],
    symbols: tuple[str, ...],
    record_types: tuple[RecordType, ...],
) -> tuple[CandidateScreenSignal, ...]:
    normalized_symbols = {_exchange_symbol(symbol): symbol for symbol in symbols}
    signals: list[CandidateScreenSignal] = []
    for exchange_symbol, symbol in normalized_symbols.items():
        matched = [
            record
            for record in records
            if record.record_type in record_types and _record_exchange_symbol(record) == exchange_symbol
        ]
        if {record.record_type for record in matched} != set(record_types):
            continue
        if not matched:
            continue
        latest = max(matched, key=lambda record: record.observed_at)
        inputs: dict[str, int | float | str] = {"derivatives_records": len(matched)}
        for record_type in record_types:
            inputs[f"{record_type}_records"] = sum(
                1 for record in matched if record.record_type == record_type
            )
        signals.append(
            CandidateScreenSignal(
                screen_id=definition.screen_id,
                symbol=symbol,
                observed_at=latest.observed_at,
                score=_derivatives_record_score(matched),
                direction="regime",
                evidence_record_count=len(matched),
                inputs=inputs,
            )
        )
    return tuple(sorted(signals, key=lambda signal: (-signal.score, signal.symbol)))


def _derivatives_record_score(records: list[SourceRecord]) -> float:
    score = 0.0
    for record in records:
        if record.record_type == "premium_index_kline":
            score += abs(float(record.payload.get("close") or 0))
        elif record.record_type == "basis":
            score += abs(float(record.payload.get("basis_rate") or 0))
        elif record.record_type == "funding_rate":
            score += abs(float(record.payload.get("funding_rate") or 0))
        elif record.record_type == "long_short_account_ratio":
            score += abs(float(record.payload.get("long_short_ratio") or 1) - 1)
        elif record.record_type == "taker_buy_sell_volume":
            score += abs(float(record.payload.get("buy_sell_ratio") or 1) - 1)
    return score


def _requires_per_symbol_record_completeness(
    definition: CandidateScreenDefinition,
) -> bool:
    return any(
        record_type
        in {
            "premium_index_kline",
            "basis",
            "funding_rate",
            "long_short_account_ratio",
            "taker_buy_sell_volume",
        }
        for record_type in definition.required_record_types
    )


def _has_complete_symbol_records(
    definition: CandidateScreenDefinition,
    records: list[SourceRecord],
    symbols: tuple[str, ...],
) -> bool:
    required_types = set(definition.required_record_types)
    required_types.discard("market_candle")
    for symbol in symbols:
        exchange_symbol = _exchange_symbol(symbol)
        symbol_record_types = {
            record.record_type
            for record in records
            if _record_exchange_symbol(record) == exchange_symbol
        }
        if required_types.issubset(symbol_record_types):
            return True
    return False


def _market_rows_by_symbol(
    records: list[SourceRecord],
    symbols: tuple[str, ...],
    timeframe: str,
) -> dict[str, list[_MarketRow]]:
    by_symbol: dict[str, list[_MarketRow]] = {symbol: [] for symbol in symbols}
    exchange_symbol_to_symbol = {_exchange_symbol(symbol): symbol for symbol in symbols}
    for record in records:
        if record.record_type != "market_candle":
            continue
        if record.payload.get("timeframe") != timeframe:
            continue
        symbol = exchange_symbol_to_symbol.get(_exchange_symbol(str(record.payload.get("symbol", ""))))
        if symbol is None:
            continue
        by_symbol[symbol].append(
            _MarketRow(
                symbol=symbol,
                timestamp=_aware(record.observed_at),
                close=float(record.payload.get("close")),
            )
        )
    for symbol in symbols:
        by_symbol[symbol] = sorted(by_symbol[symbol], key=lambda row: row.timestamp)
    return by_symbol


def _record_matches_request(
    record: SourceRecord,
    symbols: tuple[str, ...],
    timeframe: str,
    *,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
) -> bool:
    if not _in_window(record.observed_at, evaluation_start, evaluation_end):
        return False
    if record.source not in _QUALIFIED_SOURCES_BY_RECORD_TYPE.get(record.record_type, frozenset()):
        return False
    requested_symbols = {_exchange_symbol(symbol) for symbol in symbols}
    requested_pairs = _requested_symbol_pairs(symbols)
    if record.record_type == "market_candle":
        return (
            record.payload.get("timeframe") == timeframe
            and _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
        )
    if record.record_type == "premium_index_kline":
        return (
            record.payload.get("interval") == timeframe
            and _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
        )
    if record.record_type == "basis":
        return (
            record.payload.get("period") == timeframe
            and _exchange_symbol(str(record.payload.get("pair", ""))) in requested_symbols
        )
    if record.record_type in {"long_short_account_ratio", "taker_buy_sell_volume"}:
        return (
            record.payload.get("period") == timeframe
            and _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
        )
    if record.record_type == "funding_rate":
        return _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
    if record.record_type == "dex_pair":
        return (
            str(record.payload.get("base_token", "")).upper(),
            str(record.payload.get("quote_token", "")).upper(),
        ) in requested_pairs
    if record.record_type == "defi_yield":
        token = str(record.payload.get("symbol", "")).upper().replace("/", "")
        requested_tokens = {
            token_part
            for symbol in symbols
            for token_part in symbol.upper().split(":", maxsplit=1)[0].split("/")
        }
        return token in requested_tokens
    return False


def _record_exchange_symbol(record: SourceRecord) -> str | None:
    if record.record_type == "basis":
        return _exchange_symbol(str(record.payload.get("pair", "")))
    if record.record_type in {
        "market_candle",
        "funding_rate",
        "premium_index_kline",
        "long_short_account_ratio",
        "taker_buy_sell_volume",
    }:
        return _exchange_symbol(str(record.payload.get("symbol", "")))
    return None


def _in_window(
    timestamp: datetime,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
) -> bool:
    observed_at = _aware(timestamp)
    if evaluation_start is not None and observed_at < _aware(evaluation_start):
        return False
    if evaluation_end is not None and observed_at >= _aware(evaluation_end):
        return False
    return True


def _load_records_read_only(db_path: str | Path) -> list[SourceRecord]:
    path = Path(db_path)
    if not path.exists():
        return []
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute(
                """
                SELECT record_id, source, record_type, observed_at, payload_json
                FROM source_records
                ORDER BY observed_at, record_id
                """
            ).fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"cannot read candidate screen records from {path}: {exc}") from exc
    return [
        SourceRecord(
            record_id=record_id,
            source=source,
            record_type=record_type,
            observed_at=datetime.fromisoformat(observed_at),
            payload=json.loads(payload_json),
        )
        for record_id, source, record_type, observed_at, payload_json in rows
    ]


def _exchange_symbol(symbol: str) -> str:
    return symbol.strip().upper().split(":", maxsplit=1)[0].replace("/", "")


def _requested_symbol_pairs(symbols: tuple[str, ...]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for symbol in symbols:
        base_quote = symbol.strip().upper().split(":", maxsplit=1)[0]
        if "/" not in base_quote:
            continue
        base, quote = base_quote.split("/", maxsplit=1)
        if base and quote:
            pairs.add((base, quote))
    return pairs


def _latest_observed_at(records: list[SourceRecord]) -> datetime:
    if not records:
        return datetime(1970, 1, 1, tzinfo=UTC)
    return max(_aware(record.observed_at) for record in records)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _dedupe_preserving_order(values) -> list:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_symbols_by_exchange_symbol(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for symbol in symbols:
        exchange_symbol = _exchange_symbol(symbol)
        if exchange_symbol in seen:
            continue
        seen.add(exchange_symbol)
        result.append(symbol)
    return result
