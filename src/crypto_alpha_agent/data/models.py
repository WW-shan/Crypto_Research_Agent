from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.state import DependencyLevel

ExecutionRole = Literal["research_only", "research_and_paper", "paper_candidate"]
RecordType = Literal[
    "market_candle",
    "funding_rate",
    "dex_pair",
    "defi_yield",
    "research_snapshot",
    "source_health",
]


class DataSuitability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    min_capital_usd: float = Field(default=25.0, ge=0)
    latency_dependency: DependencyLevel = "low"
    rpc_dependency: DependencyLevel = "none"
    execution_role: ExecutionRole = "research_and_paper"
    unsuitable_reasons: list[str] = Field(default_factory=list)


class MarketCandle(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    venue: str
    symbol: str
    timestamp: datetime
    timeframe: str
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    volume: float = Field(ge=0)
    suitability: DataSuitability = Field(default_factory=DataSuitability)
    raw: dict[str, Any] = Field(default_factory=dict)

    def to_source_record(self) -> SourceRecord:
        timestamp = self.timestamp.isoformat()
        safe_symbol = self.symbol.replace("/", "")
        return SourceRecord(
            record_id=f"{self.source}:{safe_symbol}:{self.timeframe}:{timestamp}",
            source=self.source,
            record_type="market_candle",
            observed_at=self.timestamp,
            payload=self.model_dump(mode="json"),
        )


class FundingRateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    venue: str
    symbol: str
    timestamp: datetime
    funding_rate: float
    next_funding_at: datetime | None = None
    suitability: DataSuitability = Field(default_factory=DataSuitability)
    raw: dict[str, Any] = Field(default_factory=dict)


class DexPairSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    chain: str
    dex: str
    pair_address: str
    base_token: str
    quote_token: str
    price_usd: float = Field(ge=0)
    liquidity_usd: float = Field(default=0.0, ge=0)
    volume_24h_usd: float = Field(default=0.0, ge=0)
    observed_at: datetime
    suitability: DataSuitability = Field(default_factory=DataSuitability)
    raw: dict[str, Any] = Field(default_factory=dict)


class DefiYieldSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    chain: str
    project: str
    symbol: str
    tvl_usd: float = Field(default=0.0, ge=0)
    apy: float
    observed_at: datetime
    suitability: DataSuitability = Field(default_factory=DataSuitability)
    raw: dict[str, Any] = Field(default_factory=dict)


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    record_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    record_type: RecordType
    observed_at: datetime
    payload: dict[str, Any]
