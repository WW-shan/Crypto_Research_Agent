from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from crypto_alpha_agent.agents.scanner import ScannerSignal
from crypto_alpha_agent.data.models import (
    DataSuitability,
    DefiYieldSnapshot,
    DexPairSnapshot,
    MarketCandle,
)

LOW_DEX_LIQUIDITY_USD = 10_000.0


def records_to_scanner_signals(
    records: Iterable[MarketCandle | DexPairSnapshot | DefiYieldSnapshot | dict[str, Any]],
    current_capital_usd: float,
) -> list[ScannerSignal]:
    return [
        signal
        for record in records
        if (signal := _record_to_scanner_signal(record, current_capital_usd)) is not None
    ]


def _record_to_scanner_signal(
    record: MarketCandle | DexPairSnapshot | DefiYieldSnapshot | dict[str, Any],
    current_capital_usd: float,
) -> ScannerSignal | None:
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
    if record_type == "market_candle":
        return MarketCandle.model_validate(record)
    if record_type == "dex_pair":
        return DexPairSnapshot.model_validate(record)
    if record_type == "defi_yield":
        return DefiYieldSnapshot.model_validate(record)
    return record


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
