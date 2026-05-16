from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from crypto_alpha_agent.agents.scanner import ScannerSignal
from crypto_alpha_agent.data.models import (
    DataSuitability,
    DefiYieldSnapshot,
    DexPairSnapshot,
    MarketCandle,
    SourceRecord,
)

LOW_DEX_LIQUIDITY_USD = 10_000.0


def records_to_scanner_signals(
    records: Iterable[
        MarketCandle | DexPairSnapshot | DefiYieldSnapshot | SourceRecord | dict[str, Any]
    ],
    current_capital_usd: float,
) -> list[ScannerSignal]:
    return [
        signal
        for record in records
        if (signal := _record_to_scanner_signal(record, current_capital_usd)) is not None
    ]


def _record_to_scanner_signal(
    record: MarketCandle | DexPairSnapshot | DefiYieldSnapshot | SourceRecord | dict[str, Any],
    current_capital_usd: float,
) -> ScannerSignal | None:
    if isinstance(record, SourceRecord):
        record = _validate_typed_payload(record.record_type, record.payload)
    if isinstance(record, dict):
        record = _validate_dict_record(record)

    if isinstance(record, MarketCandle):
        return _candle_to_signal(record, current_capital_usd)
    if isinstance(record, DexPairSnapshot):
        return _dex_pair_to_signal(record, current_capital_usd)
    if isinstance(record, DefiYieldSnapshot):
        return _defi_yield_to_signal(record, current_capital_usd)
    return None


def _validate_dict_record(
    record: dict[str, Any],
) -> MarketCandle | DexPairSnapshot | DefiYieldSnapshot | dict[str, Any]:
    record_type = record.get("record_type")
    payload = record.get("payload")
    if record_type is not None and isinstance(payload, dict):
        return _validate_typed_payload(record_type, payload)

    inferred_record = _infer_payload_model(record)
    if inferred_record is not None:
        return inferred_record

    return record


def _validate_typed_payload(
    record_type: Any,
    payload: dict[str, Any],
) -> MarketCandle | DexPairSnapshot | DefiYieldSnapshot | dict[str, Any]:
    normalized_payload = _restore_json_datetimes(payload)
    if record_type == "market_candle":
        return MarketCandle.model_validate(normalized_payload)
    if record_type == "dex_pair":
        return DexPairSnapshot.model_validate(normalized_payload)
    if record_type == "defi_yield":
        return DefiYieldSnapshot.model_validate(normalized_payload)
    return payload


def _infer_payload_model(
    payload: dict[str, Any],
) -> MarketCandle | DexPairSnapshot | DefiYieldSnapshot | None:
    normalized_payload = _restore_json_datetimes(payload)
    if {"venue", "symbol", "timestamp", "timeframe", "close"}.issubset(normalized_payload):
        return MarketCandle.model_validate(normalized_payload)
    if {"chain", "dex", "pair_address", "base_token", "quote_token"}.issubset(
        normalized_payload
    ):
        return DexPairSnapshot.model_validate(normalized_payload)
    if {"chain", "project", "symbol", "tvl_usd", "apy"}.issubset(normalized_payload):
        return DefiYieldSnapshot.model_validate(normalized_payload)
    return None


def _restore_json_datetimes(payload: dict[str, Any]) -> dict[str, Any]:
    restored = dict(payload)
    for field_name in ("timestamp", "observed_at", "next_funding_at"):
        value = restored.get(field_name)
        if isinstance(value, str):
            restored[field_name] = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return restored


def _candle_to_signal(record: MarketCandle, current_capital_usd: float) -> ScannerSignal:
    return ScannerSignal(
        category="cex",
        source=record.source,
        asset=record.symbol,
        metric="close_return_or_price",
        value=record.close,
        evidence=_evidence(record.suitability),
        raw=record.raw,
        venue=record.venue,
        capital_required_usd=float(record.suitability.min_capital_usd),
        speed_dependency=record.suitability.latency_dependency,
        rpc_dependency=record.suitability.rpc_dependency,
        weak_signal=_is_weak(record.suitability, current_capital_usd),
    )


def _dex_pair_to_signal(record: DexPairSnapshot, current_capital_usd: float) -> ScannerSignal:
    evidence = _evidence(record.suitability)
    liquidity_too_low = record.liquidity_usd < LOW_DEX_LIQUIDITY_USD
    if liquidity_too_low and "liquidity_too_low" not in evidence:
        evidence.append("liquidity_too_low")

    return ScannerSignal(
        category="dex",
        source=record.source,
        asset=record.base_token,
        metric="liquidity_volume_price",
        value=record.liquidity_usd if record.liquidity_usd > 0 else record.price_usd,
        evidence=evidence,
        raw=record.raw,
        chain=record.chain,
        protocol=record.dex,
        liquidity_usd=record.liquidity_usd,
        capital_required_usd=float(record.suitability.min_capital_usd),
        speed_dependency=record.suitability.latency_dependency,
        rpc_dependency=record.suitability.rpc_dependency,
        weak_signal=_is_weak(record.suitability, current_capital_usd) or liquidity_too_low,
    )


def _defi_yield_to_signal(
    record: DefiYieldSnapshot, current_capital_usd: float
) -> ScannerSignal:
    return ScannerSignal(
        category="chain",
        source=record.source,
        asset=record.symbol,
        metric="defi_yield",
        value=record.apy,
        evidence=_evidence(record.suitability),
        raw=record.raw,
        chain=record.chain,
        protocol=record.project,
        liquidity_usd=record.tvl_usd,
        capital_required_usd=float(record.suitability.min_capital_usd),
        speed_dependency=record.suitability.latency_dependency,
        rpc_dependency=record.suitability.rpc_dependency,
        weak_signal=_is_weak(record.suitability, current_capital_usd),
    )


def _evidence(suitability: DataSuitability) -> list[str]:
    return list(suitability.unsuitable_reasons)


def _is_weak(suitability: DataSuitability, current_capital_usd: float) -> bool:
    return (
        suitability.min_capital_usd > current_capital_usd
        or suitability.execution_role == "research_only"
        or bool(suitability.unsuitable_reasons)
    )
