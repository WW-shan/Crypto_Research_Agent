# Low-Capital Real Data Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real data ingestion for a few-hundred-dollar crypto alpha research workflow that avoids low-latency/RPC-dependent opportunities and prioritizes paper-verifiable, low-capital signals.

**Architecture:** Keep discovery broad, but tag every source and signal with capital, latency, liquidity, and RPC suitability before it can enter the scanner. Use SQLite from the Python standard library for the first durable local research store, keep all network calls injectable for offline tests, and make the CLI default to dry-run/offline behavior unless a source is explicitly requested.

**Tech Stack:** Python 3.12, uv, pytest, ruff, Pydantic, requests, ccxt, SQLite stdlib, existing scanner/feasibility/risk modules.

---

## Source Selection For This Capital Profile

P0 sources are suitable for the first implementation because they are free or low-cost, useful for low-frequency to medium-frequency research, and do not require premium RPC or colocation:

- Binance Public Data: free bulk historical klines/trades from `data.binance.vision`; good for reproducible backtests. Source: https://github.com/binance/binance-public-data
- CCXT REST: unified OHLCV/ticker/funding-style access across exchanges; good for normalized research pulls, not low-latency execution. Source: https://github.com/ccxt/ccxt/wiki/manual
- DexScreener API: free DEX pair/token discovery, liquidity, price, and volume snapshots; useful for anomaly discovery, not execution pricing. Source: https://docs.dexscreener.com/api/reference
- DefiLlama API: protocol TVL, fees, stablecoins, yields, and basic DeFi fundamentals; useful for low-frequency alpha hypotheses. Source: https://defillama.com/docs/api

P1 sources stay in the design but are not required for this first patch:

- GeckoTerminal/CoinGecko Onchain DEX API for wider DEX OHLCV and pool metadata.
- OKX/Bybit public market data for exchange diversity.
- Coinalyze for open interest, funding, and liquidation data if a key is available.
- Dune/The Graph/Flipside for slower SQL/subgraph research evidence.

Explicitly out of scope for this patch:

- MEV/mempool feeds.
- CEX-DEX sub-second arbitrage execution.
- Premium historical L2 order book datasets such as Tardis/Crypto Lake/Kaiko.
- Live order routing or wallet/RPC transactions.

## File Map

- Create `src/crypto_alpha_agent/data/__init__.py`: package marker and public exports.
- Create `src/crypto_alpha_agent/data/models.py`: normalized durable records for candles, funding, DEX pairs, DeFi yields, ingestion batches, and source suitability.
- Create `src/crypto_alpha_agent/data/store.py`: SQLite schema, upsert helpers, and query helpers.
- Create `src/crypto_alpha_agent/data/binance_public.py`: Binance Public Data URL builder, ZIP CSV parser, and candle ingestion.
- Create `src/crypto_alpha_agent/data/ccxt_collector.py`: injected-CCXT collector for OHLCV, tickers, and funding history where supported.
- Create `src/crypto_alpha_agent/data/dexscreener.py`: injected-session client and pair normalization.
- Create `src/crypto_alpha_agent/data/defillama.py`: low-capital-focused DefiLlama yield/protocol snapshot client.
- Create `src/crypto_alpha_agent/data/scanner_bridge.py`: convert stored normalized records into `ScannerSignal` objects with low-capital suitability tags.
- Modify `src/crypto_alpha_agent/cli.py`: add a safe `ingest` command that can run offline fixture checks or explicitly selected source pulls.
- Modify `.env.example`: document optional source settings and default local database path.
- Modify `README.md` and `docs/runbook.md`: explain low-capital data workflow and excluded strategy classes.
- Test `tests/test_data_models_store.py`
- Test `tests/test_binance_public_ingestion.py`
- Test `tests/test_ccxt_collector.py`
- Test `tests/test_dex_defillama_collectors.py`
- Test `tests/test_scanner_bridge_low_capital.py`
- Test `tests/test_cli_ingest.py`

---

## Task 1: Normalized Data Models And SQLite Store

**Files:**
- Create: `src/crypto_alpha_agent/data/__init__.py`
- Create: `src/crypto_alpha_agent/data/models.py`
- Create: `src/crypto_alpha_agent/data/store.py`
- Test: `tests/test_data_models_store.py`

- [ ] **Step 1: Write the failing model and store tests**

```python
from datetime import UTC, datetime

from crypto_alpha_agent.data.models import (
    DataSuitability,
    MarketCandle,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore


def test_market_candle_preserves_low_capital_suitability():
    candle = MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=65000.0,
        high=65100.0,
        low=64900.0,
        close=65050.0,
        volume=123.4,
        suitability=DataSuitability(
            min_capital_usd=25.0,
            latency_dependency="low",
            rpc_dependency="none",
            execution_role="research_and_paper",
        ),
        raw={"source_line": "fixture"},
    )

    assert candle.suitability.execution_role == "research_and_paper"
    assert candle.suitability.latency_dependency == "low"


def test_store_round_trips_source_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    record = SourceRecord(
        record_id="binance_public:BTCUSDT:1h:2026-05-16T00:00:00+00:00",
        source="binance_public",
        record_type="market_candle",
        observed_at=datetime(2026, 5, 16, tzinfo=UTC),
        payload={
            "symbol": "BTC/USDT",
            "close": 65050.0,
            "suitability": {"latency_dependency": "low", "rpc_dependency": "none"},
        },
    )

    store.upsert_records([record])
    loaded = store.load_records(record_type="market_candle")

    assert [item.record_id for item in loaded] == [record.record_id]
    assert loaded[0].payload["symbol"] == "BTC/USDT"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_data_models_store.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'crypto_alpha_agent.data'`.

- [ ] **Step 3: Implement minimal models and SQLite store**

Create `src/crypto_alpha_agent/data/models.py` with:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.state import DependencyLevel

ExecutionRole = Literal["research_only", "research_and_paper", "paper_candidate"]
RecordType = Literal["market_candle", "funding_rate", "dex_pair", "defi_yield", "source_health"]


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

    def to_source_record(self) -> "SourceRecord":
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
```

Create `src/crypto_alpha_agent/data/store.py` with a `ResearchDataStore` class that:

- Creates a `source_records` table with `record_id TEXT PRIMARY KEY`, `source`, `record_type`, `observed_at`, `payload_json`, and `inserted_at`.
- Stores payloads as sorted JSON.
- Uses `INSERT OR REPLACE` for idempotent ingestion.
- Loads records as `SourceRecord` objects ordered by `observed_at`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_data_models_store.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/data tests/test_data_models_store.py
git commit -m "feat: add low capital research data store"
```

**Exit criteria:** The project has durable normalized data records that encode whether a source is suitable for the user's capital and infrastructure profile.

---

## Task 2: Binance Public Data Historical Candle Ingestion

**Files:**
- Create: `src/crypto_alpha_agent/data/binance_public.py`
- Test: `tests/test_binance_public_ingestion.py`

- [ ] **Step 1: Write failing ZIP CSV parser tests**

```python
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

from crypto_alpha_agent.data.binance_public import BinancePublicDataClient


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, content: bytes):
        self.content = content
        self.requested_urls = []

    def get(self, url, timeout):
        self.requested_urls.append(url)
        return FakeResponse(self.content)


def _zip_csv(name: str, text: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(name, text)
    return buffer.getvalue()


def test_downloads_monthly_klines_into_market_candles():
    csv_text = "1747353600000,65000,65100,64900,65050,123.4,1747357199999,0,0,0,0,0\n"
    session = FakeSession(_zip_csv("BTCUSDT-1h-2026-05.csv", csv_text))
    client = BinancePublicDataClient(session=session)

    candles = client.download_monthly_spot_klines("BTCUSDT", "1h", 2026, 5)

    assert session.requested_urls[0].endswith("/data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05.zip")
    assert candles[0].symbol == "BTC/USDT"
    assert candles[0].timestamp == datetime.fromtimestamp(1747353600, tz=UTC)
    assert candles[0].close == 65050.0
    assert candles[0].suitability.rpc_dependency == "none"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_binance_public_ingestion.py -q`

Expected: FAIL because the client does not exist.

- [ ] **Step 3: Implement the Binance Public Data client**

Implement:

- `build_monthly_spot_klines_url(symbol, interval, year, month)`.
- `download_monthly_spot_klines(symbol, interval, year, month)`.
- ZIP extraction using `zipfile.ZipFile`.
- CSV parsing using `csv.reader`.
- Millisecond timestamp conversion to UTC.
- Symbol normalization from `BTCUSDT` to `BTC/USDT` for USDT-quoted symbols.
- `DataSuitability(min_capital_usd=25, latency_dependency="low", rpc_dependency="none", execution_role="research_and_paper")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_binance_public_ingestion.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/data/binance_public.py tests/test_binance_public_ingestion.py
git commit -m "feat: ingest binance public historical candles"
```

**Exit criteria:** The agent can pull free historical candles suitable for low-frequency backtesting without API keys or premium infrastructure.

---

## Task 3: CCXT Research Collector For OHLCV And Funding

**Files:**
- Create: `src/crypto_alpha_agent/data/ccxt_collector.py`
- Test: `tests/test_ccxt_collector.py`

- [ ] **Step 1: Write failing injected-exchange tests**

```python
from datetime import UTC, datetime

from crypto_alpha_agent.data.ccxt_collector import CcxtResearchCollector


class FakeExchange:
    id = "binance"

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        return [[1747353600000, 65000.0, 65100.0, 64900.0, 65050.0, 123.4]]

    def fetch_funding_rate_history(self, symbol, since=None, limit=None):
        return [{"symbol": symbol, "timestamp": 1747353600000, "fundingRate": 0.0003}]


def test_collects_ohlcv_with_low_latency_suitability():
    collector = CcxtResearchCollector(exchange=FakeExchange())

    candles = collector.fetch_ohlcv("BTC/USDT", "1h", limit=1)

    assert candles[0].venue == "binance"
    assert candles[0].timestamp == datetime.fromtimestamp(1747353600, tz=UTC)
    assert candles[0].suitability.latency_dependency == "low"


def test_collects_funding_history_when_exchange_supports_it:
    collector = CcxtResearchCollector(exchange=FakeExchange())

    funding = collector.fetch_funding_rate_history("BTC/USDT", limit=1)

    assert funding[0].funding_rate == 0.0003
    assert funding[0].suitability.execution_role == "research_and_paper"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ccxt_collector.py -q`

Expected: FAIL because the collector does not exist.

- [ ] **Step 3: Implement injected CCXT collector**

Implement:

- Constructor accepting either an injected exchange or `exchange_id`.
- `fetch_ohlcv(symbol, timeframe, since=None, limit=None) -> list[MarketCandle]`.
- `fetch_funding_rate_history(symbol, since=None, limit=None) -> list[FundingRateRecord]`.
- Graceful `NotImplementedError` with a clear message if the exchange lacks `fetch_funding_rate_history`.
- Suitability defaults: low latency dependency, no RPC dependency, research-and-paper only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ccxt_collector.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/data/ccxt_collector.py tests/test_ccxt_collector.py
git commit -m "feat: collect ccxt research market data"
```

**Exit criteria:** The system can ingest exchange research data without pretending REST pulls are execution-grade low-latency data.

---

## Task 4: DEX And DeFi Discovery Collectors

**Files:**
- Create: `src/crypto_alpha_agent/data/dexscreener.py`
- Create: `src/crypto_alpha_agent/data/defillama.py`
- Test: `tests/test_dex_defillama_collectors.py`

- [ ] **Step 1: Write failing collector tests with fake sessions**

```python
from datetime import UTC, datetime

from crypto_alpha_agent.data.defillama import DefiLlamaResearchClient
from crypto_alpha_agent.data.dexscreener import DexScreenerClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        return FakeResponse(self.payload)


def test_dexscreener_pair_normalizes_liquidity_and_volume():
    payload = {
        "pairs": [
            {
                "chainId": "base",
                "dexId": "uniswap",
                "pairAddress": "0xabc",
                "baseToken": {"symbol": "ABC"},
                "quoteToken": {"symbol": "USDC"},
                "priceUsd": "1.23",
                "liquidity": {"usd": 120000},
                "volume": {"h24": 45000},
            }
        ]
    }
    client = DexScreenerClient(session=FakeSession(payload), now=lambda: datetime(2026, 5, 16, tzinfo=UTC))

    pairs = client.search_pairs("ABC")

    assert pairs[0].chain == "base"
    assert pairs[0].liquidity_usd == 120000
    assert pairs[0].suitability.latency_dependency == "medium"


def test_defillama_yields_filter_low_tvl_pools_as_research_only():
    payload = {
        "data": [
            {"chain": "Base", "project": "aave", "symbol": "USDC", "tvlUsd": 5000, "apy": 7.2},
            {"chain": "Ethereum", "project": "aave", "symbol": "USDC", "tvlUsd": 5000000, "apy": 4.1},
        ]
    }
    client = DefiLlamaResearchClient(session=FakeSession(payload), now=lambda: datetime(2026, 5, 16, tzinfo=UTC))

    pools = client.yield_pools(min_tvl_usd=10000)

    assert [pool.chain for pool in pools] == ["Ethereum"]
    assert pools[0].suitability.rpc_dependency == "none"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dex_defillama_collectors.py -q`

Expected: FAIL because the collectors do not exist.

- [ ] **Step 3: Implement DexScreener client**

Implement:

- `search_pairs(query)` using `/latest/dex/search`.
- `pairs_by_token_addresses(chain_id, token_addresses)` using `/tokens/v1/{chainId}/{tokenAddresses}` if needed by the tests or follow-up work.
- Normalize numeric strings safely.
- Set `latency_dependency="medium"` because these snapshots can be delayed and should not be used as direct execution quotes.
- Set `execution_role="research_and_paper"` only when liquidity is at least `10_000`; otherwise `research_only`.

- [ ] **Step 4: Implement DefiLlama research client**

Implement:

- `yield_pools(min_tvl_usd=10000)` using `/pools`.
- Normalize `chain`, `project`, `symbol`, `tvlUsd`, and `apy`.
- Filter out pools below `min_tvl_usd`.
- Set `latency_dependency="low"` and `rpc_dependency="none"` because this is slow research data, not execution data.

- [ ] **Step 5: Run tests to verify they pass and commit**

Run: `uv run pytest tests/test_dex_defillama_collectors.py -q`

Expected: PASS.

Commit:

```bash
git add src/crypto_alpha_agent/data/dexscreener.py src/crypto_alpha_agent/data/defillama.py tests/test_dex_defillama_collectors.py
git commit -m "feat: collect dex and defi discovery data"
```

**Exit criteria:** The agent can discover DEX and DeFi candidates while marking them as research signals, not instant executable arbitrage.

---

## Task 5: Scanner Bridge And Low-Capital Suitability Filter

**Files:**
- Create: `src/crypto_alpha_agent/data/scanner_bridge.py`
- Test: `tests/test_scanner_bridge_low_capital.py`

- [ ] **Step 1: Write failing scanner bridge tests**

```python
from datetime import UTC, datetime

from crypto_alpha_agent.data.models import DataSuitability, DexPairSnapshot, MarketCandle
from crypto_alpha_agent.data.scanner_bridge import records_to_scanner_signals


def test_candle_becomes_low_capital_scanner_signal():
    candle = MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
        suitability=DataSuitability(min_capital_usd=25, latency_dependency="low", rpc_dependency="none"),
    )

    signals = records_to_scanner_signals([candle], current_capital_usd=300)

    assert signals[0].category == "cex"
    assert signals[0].capital_required_usd == 25.0
    assert signals[0].speed_dependency == "low"


def test_high_capital_dex_pair_is_research_only_and_weak():
    pair = DexPairSnapshot(
        source="dexscreener",
        chain="base",
        dex="uniswap",
        pair_address="0xabc",
        base_token="ABC",
        quote_token="USDC",
        price_usd=1.0,
        liquidity_usd=1000.0,
        volume_24h_usd=100.0,
        observed_at=datetime(2026, 5, 16, tzinfo=UTC),
        suitability=DataSuitability(
            min_capital_usd=1000.0,
            latency_dependency="medium",
            rpc_dependency="none",
            execution_role="research_only",
            unsuitable_reasons=["liquidity_too_low"],
        ),
    )

    signals = records_to_scanner_signals([pair], current_capital_usd=300)

    assert signals[0].weak_signal is True
    assert "liquidity_too_low" in signals[0].evidence
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scanner_bridge_low_capital.py -q`

Expected: FAIL because the bridge does not exist.

- [ ] **Step 3: Implement record-to-signal conversion**

Implement:

- `records_to_scanner_signals(records, current_capital_usd)`.
- Market candles become `ScannerSignal(category="cex", metric="close_return_or_price")`.
- DEX pairs become `ScannerSignal(category="dex", metric="liquidity_volume_price")`.
- DeFi yields become `ScannerSignal(category="chain", metric="defi_yield")`.
- `weak_signal=True` when min capital exceeds current capital, liquidity is too low, execution role is research-only, or suitability has unsuitable reasons.
- Preserve raw payload and suitability evidence.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scanner_bridge_low_capital.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/data/scanner_bridge.py tests/test_scanner_bridge_low_capital.py
git commit -m "feat: bridge real data into low capital scanner signals"
```

**Exit criteria:** Real data can enter the existing scanner only with explicit suitability labels for the user's budget and infrastructure.

---

## Task 6: Safe Ingest CLI And Operator Docs

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Test: `tests/test_cli_ingest.py`

- [ ] **Step 1: Write failing CLI tests**

```python
import json

from crypto_alpha_agent.cli import main


def test_ingest_offline_check_reports_no_live_capital(capsys, tmp_path):
    exit_code = main(["ingest", "--offline-check", "--db", str(tmp_path / "research.sqlite")])

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["command"] == "ingest"
    assert captured["uses_real_capital"] is False
    assert captured["live_order_routing"] is False
    assert captured["capital_profile"]["current_capital_usd"] == 300.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_ingest.py -q`

Expected: FAIL because the command does not exist.

- [ ] **Step 3: Implement CLI ingest command**

Add:

- `crypto-alpha-agent ingest --offline-check --db <path>`: creates/opens the SQLite store and returns a JSON payload with no network calls.
- `--current-capital-usd`, default `300`.
- `--source`, optional repeated choice among `binance-public`, `ccxt`, `dexscreener`, `defillama`.
- Require `--allow-network` when `--source` is provided.
- Always return `uses_real_capital: false` and `live_order_routing: false`.

- [ ] **Step 4: Update docs**

Document:

- The supported P0 data sources.
- Why low-latency arbitrage/MEV are excluded for this capital profile.
- Example offline command.
- Example explicit network command.
- Warning that real network ingestion is for research and paper validation only.

- [ ] **Step 5: Run targeted and full tests, then commit**

Run:

```bash
uv run pytest tests/test_cli_ingest.py -q
uv run pytest -q
uv run ruff check .
```

Expected: all pass.

Commit:

```bash
git add src/crypto_alpha_agent/cli.py .env.example README.md docs/runbook.md tests/test_cli_ingest.py
git commit -m "feat: add safe real data ingest cli"
```

**Exit criteria:** A human operator can initialize the research data store safely and deliberately opt into real network pulls without enabling live trading.

---

## Execution Order

1. Implement normalized models and SQLite store.
2. Add free historical Binance candle ingestion.
3. Add CCXT OHLCV/funding research collector.
4. Add DexScreener and DefiLlama discovery collectors.
5. Bridge normalized data into existing scanner signals with low-capital suitability.
6. Add CLI/docs for safe operation.
7. Run full test and lint suite.

## Decision Rule

For this project and capital profile, a source is valuable only if it helps find opportunities that can be researched, paper-tested, and eventually executed with small capital and ordinary infrastructure. Any signal that depends on premium speed, private RPC, mempool access, or large balance sheet is allowed into memory as a rejected research sample but must not become a trade candidate.
