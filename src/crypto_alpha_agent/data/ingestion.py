from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.data.ccxt_collector import CcxtResearchCollector
from crypto_alpha_agent.data.binance_public import BinancePublicDataClient
from crypto_alpha_agent.data.defillama import DefiLlamaResearchClient
from crypto_alpha_agent.data.dexscreener import DexScreenerClient
from crypto_alpha_agent.data.models import (
    DefiYieldSnapshot,
    DexPairSnapshot,
    FundingRateRecord,
    MarketCandle,
    OpenInterestRecord,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore


class IngestionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    db_path: str
    symbols: list[str]
    timeframe: str
    year: int
    month: int
    records_fetched: int
    records_written: int
    network_allowed: bool
    uses_real_capital: bool
    live_order_routing: bool
    notes: list[str]


class CcxtIngestionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    db_path: str
    feed: Literal["ohlcv", "funding_rate_history", "open_interest_history"]
    symbols: list[str]
    records_fetched: int
    records_written: int
    network_allowed: bool
    uses_real_capital: bool
    live_order_routing: bool


class ResearchFeedIngestionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    db_path: str
    feed: Literal["pairs", "yield_pools"]
    records_fetched: int
    records_written: int
    network_allowed: bool
    uses_real_capital: bool
    live_order_routing: bool


def ingest_binance_public_month(
    db_path: str | Path,
    *,
    symbol: str,
    interval: str,
    year: int,
    month: int,
    allow_network: bool = False,
    client=None,
) -> IngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for Binance Public Data ingestion")

    binance_client = client or BinancePublicDataClient()
    store = ResearchDataStore(db_path)
    try:
        candles = binance_client.download_monthly_spot_klines(symbol, interval, year, month)
        records = [candle.to_source_record() for candle in candles]
        records_written = store.upsert_records(records)
    except Exception as exc:
        _write_source_health(
            store,
            source="binance_public",
            feed="ohlcv",
            success=False,
            attempts=1,
            failure=str(exc),
            records_fetched=0,
            records_written=0,
        )
        raise
    _write_source_health(
        store,
        source="binance_public",
        feed="ohlcv",
        success=True,
        attempts=1,
        failure=None,
        records_fetched=len(candles),
        records_written=records_written,
    )

    return IngestionSummary(
        source="binance_public",
        db_path=str(db_path),
        symbols=[symbol],
        timeframe=interval,
        year=year,
        month=month,
        records_fetched=len(candles),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
        notes=["research_and_paper_validation_only"],
    )


def ingest_dexscreener_pairs(
    db_path: str | Path,
    query: str | None = None,
    *,
    chain: str | None = None,
    token_addresses: list[str] | None = None,
    allow_network: bool = False,
    client=None,
) -> ResearchFeedIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for DexScreener ingestion")
    normalized_query = _optional_non_blank(query, "DexScreener query")
    normalized_chain = _optional_non_blank(chain, "DexScreener chain")
    normalized_token_addresses = _non_blank_list(token_addresses, "DexScreener token address")

    if normalized_query is None and (normalized_chain is None or not normalized_token_addresses):
        raise ValueError("DexScreener ingestion requires query or chain with token addresses")
    if normalized_query is not None and (normalized_chain is not None or normalized_token_addresses):
        raise ValueError("DexScreener ingestion accepts query or token lookup, not both")

    dex_client = client or DexScreenerClient()
    store = ResearchDataStore(db_path)
    try:
        if normalized_query is not None:
            pairs = dex_client.search_pairs(normalized_query)
        else:
            pairs = dex_client.pairs_by_token_addresses(normalized_chain, normalized_token_addresses)

        records = [_dex_pair_to_source_record(pair) for pair in pairs]
        records_written = store.upsert_records(records)
    except Exception as exc:
        _write_source_health(
            store,
            source="dexscreener",
            feed="pairs",
            success=False,
            attempts=1,
            failure=str(exc),
            records_fetched=0,
            records_written=0,
        )
        raise
    _write_source_health(
        store,
        source="dexscreener",
        feed="pairs",
        success=True,
        attempts=1,
        failure=None,
        records_fetched=len(pairs),
        records_written=records_written,
    )
    return ResearchFeedIngestionSummary(
        source="dexscreener",
        db_path=str(db_path),
        feed="pairs",
        records_fetched=len(pairs),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def ingest_defillama_yield_pools(
    db_path: str | Path,
    *,
    min_tvl_usd: float = 10000.0,
    allow_network: bool = False,
    client=None,
) -> ResearchFeedIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for DefiLlama ingestion")

    defillama_client = client or DefiLlamaResearchClient()
    store = ResearchDataStore(db_path)
    try:
        pools = defillama_client.yield_pools(min_tvl_usd=min_tvl_usd)
        records = [_defi_yield_to_source_record(pool) for pool in pools]
        records_written = store.upsert_records(records)
    except Exception as exc:
        _write_source_health(
            store,
            source="defillama",
            feed="yield_pools",
            success=False,
            attempts=1,
            failure=str(exc),
            records_fetched=0,
            records_written=0,
        )
        raise
    _write_source_health(
        store,
        source="defillama",
        feed="yield_pools",
        success=True,
        attempts=1,
        failure=None,
        records_fetched=len(pools),
        records_written=records_written,
    )
    return ResearchFeedIngestionSummary(
        source="defillama",
        db_path=str(db_path),
        feed="yield_pools",
        records_fetched=len(pools),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def ingest_ccxt_ohlcv(
    db_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    since: int | None = None,
    limit: int | None = None,
    allow_network: bool = False,
    exchange_id: str = "binance",
    collector: Any | None = None,
) -> CcxtIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for CCXT ingestion")

    ccxt_collector = collector or CcxtResearchCollector(exchange_id=exchange_id)
    store = ResearchDataStore(db_path)
    try:
        candles = ccxt_collector.fetch_ohlcv(
            symbol,
            timeframe,
            since=since,
            limit=limit,
            params=None,
        )
        records = [_ccxt_ohlcv_to_source_record(candle) for candle in candles]
        records_written = store.upsert_records(records)
    except Exception as exc:
        _write_source_health(
            store,
            source="ccxt",
            feed="ohlcv",
            success=False,
            attempts=1,
            failure=str(exc),
            records_fetched=0,
            records_written=0,
        )
        raise
    _write_source_health(
        store,
        source="ccxt",
        feed="ohlcv",
        success=True,
        attempts=1,
        failure=None,
        records_fetched=len(candles),
        records_written=records_written,
    )
    return CcxtIngestionSummary(
        source="ccxt",
        db_path=str(db_path),
        feed="ohlcv",
        symbols=[symbol],
        records_fetched=len(candles),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def ingest_ccxt_funding_rate_history(
    db_path: str | Path,
    *,
    symbol: str,
    since: int | None = None,
    limit: int | None = None,
    allow_network: bool = False,
    exchange_id: str = "binance",
    collector: Any | None = None,
) -> CcxtIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for CCXT ingestion")

    ccxt_collector = collector or CcxtResearchCollector(exchange_id=exchange_id)
    store = ResearchDataStore(db_path)
    try:
        funding_history = ccxt_collector.fetch_funding_rate_history(
            symbol,
            since=since,
            limit=limit,
            params=None,
        )
        records = [_funding_rate_to_source_record(record) for record in funding_history]
        records_written = store.upsert_records(records)
    except Exception as exc:
        _write_source_health(
            store,
            source="ccxt",
            feed="funding_rate_history",
            success=False,
            attempts=1,
            failure=str(exc),
            records_fetched=0,
            records_written=0,
        )
        raise
    _write_source_health(
        store,
        source="ccxt",
        feed="funding_rate_history",
        success=True,
        attempts=1,
        failure=None,
        records_fetched=len(funding_history),
        records_written=records_written,
    )
    return CcxtIngestionSummary(
        source="ccxt",
        db_path=str(db_path),
        feed="funding_rate_history",
        symbols=[symbol],
        records_fetched=len(funding_history),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def ingest_ccxt_open_interest_history(
    db_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    since: int | None = None,
    limit: int | None = None,
    allow_network: bool = False,
    exchange_id: str = "binance",
    collector: Any | None = None,
) -> CcxtIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for CCXT ingestion")

    ccxt_collector = collector or CcxtResearchCollector(exchange_id=exchange_id)
    store = ResearchDataStore(db_path)
    try:
        open_interest_history = ccxt_collector.fetch_open_interest_history(
            symbol,
            timeframe,
            since=since,
            limit=limit,
            params=None,
        )
        records = [_open_interest_to_source_record(record) for record in open_interest_history]
        records_written = store.upsert_records(records)
    except Exception as exc:
        _write_source_health(
            store,
            source="ccxt",
            feed="open_interest_history",
            success=False,
            attempts=1,
            failure=str(exc),
            records_fetched=0,
            records_written=0,
        )
        raise
    _write_source_health(
        store,
        source="ccxt",
        feed="open_interest_history",
        success=True,
        attempts=1,
        failure=None,
        records_fetched=len(open_interest_history),
        records_written=records_written,
    )
    return CcxtIngestionSummary(
        source="ccxt",
        db_path=str(db_path),
        feed="open_interest_history",
        symbols=[symbol],
        records_fetched=len(open_interest_history),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def _dex_pair_to_source_record(pair: DexPairSnapshot) -> SourceRecord:
    safe_chain = _research_safe_component(pair.chain)
    safe_dex = _research_safe_component(pair.dex)
    safe_pair = _research_safe_component(pair.pair_address)
    safe_base = _research_safe_component(pair.base_token)
    safe_quote = _research_safe_component(pair.quote_token)
    return SourceRecord(
        record_id=(
            f"{pair.source}:{safe_chain}:{safe_dex}:{safe_pair}:"
            f"{safe_base}-{safe_quote}:dex_pair:{pair.observed_at.isoformat()}"
        ),
        source=pair.source,
        record_type="dex_pair",
        observed_at=pair.observed_at,
        payload=pair.model_dump(mode="json"),
    )


def _defi_yield_to_source_record(pool: DefiYieldSnapshot) -> SourceRecord:
    safe_chain = _research_safe_component(pool.chain)
    safe_project = _research_safe_component(pool.project)
    safe_symbol = _research_safe_component(pool.symbol)
    safe_pool_identity = _defi_pool_identity(pool)
    return SourceRecord(
        record_id=(
            f"{pool.source}:{safe_chain}:{safe_project}:{safe_symbol}:{safe_pool_identity}:"
            f"defi_yield:{pool.observed_at.isoformat()}"
        ),
        source=pool.source,
        record_type="defi_yield",
        observed_at=pool.observed_at,
        payload=pool.model_dump(mode="json"),
    )


def _ccxt_ohlcv_to_source_record(candle: MarketCandle) -> SourceRecord:
    safe_venue = _ccxt_safe_component(candle.venue)
    safe_symbol = _ccxt_safe_symbol(candle.symbol)
    safe_timeframe = _ccxt_safe_component(candle.timeframe)
    return SourceRecord(
        record_id=(
            f"{candle.source}:{safe_venue}:{safe_symbol}:ohlcv:"
            f"{safe_timeframe}:{candle.timestamp.isoformat()}"
        ),
        source=candle.source,
        record_type="market_candle",
        observed_at=candle.timestamp,
        payload=candle.model_dump(mode="json"),
    )


def _funding_rate_to_source_record(record: FundingRateRecord) -> SourceRecord:
    safe_venue = _ccxt_safe_component(record.venue)
    safe_symbol = _ccxt_safe_symbol(record.symbol)
    return SourceRecord(
        record_id=f"{record.source}:{safe_venue}:{safe_symbol}:funding:{record.timestamp.isoformat()}",
        source=record.source,
        record_type="funding_rate",
        observed_at=record.timestamp,
        payload=record.model_dump(mode="json"),
    )


def _open_interest_to_source_record(record: OpenInterestRecord) -> SourceRecord:
    return record.to_source_record()


def _ccxt_safe_component(value: str) -> str:
    return value.strip().lower().replace("/", "-").replace(":", "-")


def _ccxt_safe_symbol(symbol: str) -> str:
    return symbol.strip().replace("/", "").replace(":", "-").upper()


def _research_safe_component(value: str) -> str:
    return value.strip().lower().replace("/", "-").replace(":", "-").replace(" ", "-")


def _optional_non_blank(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} cannot be blank")
    return normalized


def _non_blank_list(values: list[str] | None, label: str) -> list[str]:
    if values is None:
        return []
    normalized = [value.strip() for value in values]
    if any(not value for value in normalized):
        raise ValueError(f"{label} cannot be blank")
    return normalized


def _defi_pool_identity(pool: DefiYieldSnapshot) -> str:
    raw_pool_id = pool.raw.get("pool")
    if _has_identity_value(raw_pool_id):
        return f"pool-{_research_safe_component(str(raw_pool_id))}"

    stable_identity = {
        key: pool.raw[key]
        for key in ("poolMeta", "stablecoin", "underlyingTokens", "url")
        if key in pool.raw and _has_identity_value(pool.raw[key])
    }
    identity_payload = stable_identity or pool.raw
    digest = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:16]
    return f"pool-hash-{digest}"


def _has_identity_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | dict | tuple | set):
        return bool(value)
    return True


def _write_source_health(
    store: ResearchDataStore,
    *,
    source: str,
    feed: str,
    success: bool,
    attempts: int,
    failure: str | None,
    records_fetched: int,
    records_written: int,
) -> None:
    observed_at = datetime.now(tz=UTC)
    payload = {
        "source": source,
        "feed": feed,
        "success": success,
        "attempts": attempts,
        "failure": failure,
        "observed_at": observed_at.isoformat(),
        "records_fetched": records_fetched,
        "records_written": records_written,
    }
    safe_source = _research_safe_component(source)
    safe_feed = _research_safe_component(feed)
    store.upsert_records(
        [
            SourceRecord(
                record_id=f"{safe_source}:{safe_feed}:source_health:{observed_at.isoformat()}",
                source=source,
                record_type="source_health",
                observed_at=observed_at,
                payload=payload,
            )
        ]
    )
