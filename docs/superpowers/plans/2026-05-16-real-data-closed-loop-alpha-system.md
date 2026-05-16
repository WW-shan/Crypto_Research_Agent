# Real Data Closed-Loop Alpha System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current low-capital crypto research kernel into a reproducible real-data loop that can discover, filter, validate, remember, and report candidate alpha without requiring speed, premium RPC, or live capital.

**Architecture:** Keep execution authority out of the first system: real sources feed durable SQLite records, stored records become scanner signals, signals become anomalies and hypotheses, and every candidate is filtered through the charter before any paper proposal is considered. The system should progress in narrow batches: first a local real-data research loop, then historical validation, then LLM-assisted hypothesis work, then paper evidence, and only then a tiny-live readiness artifact.

**Tech Stack:** Python 3.12, uv, pytest, ruff, Pydantic, SQLite stdlib, requests, ccxt, existing scanner/anomaly/hypothesis/risk/memory modules, LangGraph for later orchestration integration.

---

## Governing Constraints

The project charter in `docs/project-charter.md` is the source of truth.

- Primary objective: make money through reproducible crypto alpha research.
- Owner profile: a few hundred USD, ordinary public APIs, ordinary RPC, no latency edge.
- Default mode: research-only; paper simulation only after historical evidence.
- Explicitly excluded: MEV, mempool, sub-second CEX-DEX arbitrage, flash-loan races, bridge races, private order flow, premium RPC, and strategies requiring large balance sheets.
- Preferred first opportunities: funding/basis/OI patterns, historical price/volume/funding effects, DeFi fundamentals, DEX discovery signals used for watchlists, and cross-source confirmation.

## Gap Audit

Implemented now:

- Project charter and roadmap persist the low-capital, money-first direction.
- LangGraph skeleton has loops, checkpoints, branch routing, and deterministic tests.
- Scanner, anomaly detector, hypothesis generator, feasibility scorer, risk guardian, rollout gates, memory store, paper execution, and observability modules exist.
- Real-data libraries exist for Binance Public Data, CCXT, DexScreener, DefiLlama, SQLite storage, and conversion into `ScannerSignal`.
- CLI has safe smoke commands and an `ingest` command that initializes storage and enforces `--allow-network` before source declarations.

Missing relative to the charter's first complete research-loop milestone:

- No command actually pulls real Binance Public Data into SQLite.
- No pipeline loads stored records, scans them, ranks anomalies, generates hypotheses, and emits one durable research report.
- No daily report artifact focused on weak signals, blocked opportunities, capital fit, and next validation steps.
- Backtests are still toy/synthetic, not run against stored market history.
- No funding-specific historical validator using persisted funding data.
- No memory persistence for real-data hypotheses and rejected assumptions.
- No scheduler or daily automation.
- No LLM agent prompt layer that reads the charter and constrains generated research.
- No paper-evidence accumulation workflow for a strategy family.
- No tiny-live readiness artifact; this remains intentionally blocked until evidence exists.

## Implementation Strategy

Implement in sequential batches. Do not dispatch multiple implementation workers at the same time. For each task:

1. A fresh implementation subagent writes the failing test, verifies red, implements, verifies green, runs relevant quality checks, commits, and self-reviews.
2. A fresh spec-review subagent checks the implementation against the task only.
3. A fresh code-quality review subagent checks maintainability, safety, and regression risk.
4. The controller marks the task complete only after both reviews pass.

The first batch produces a usable Phase 1 MVP. Later batches should be executed only after the previous batch is green and the roadmap is updated.

## File Map

Create:

- `src/crypto_alpha_agent/pipeline/__init__.py`: public pipeline exports.
- `src/crypto_alpha_agent/pipeline/research_loop.py`: offline stored-data research loop.
- `src/crypto_alpha_agent/pipeline/markdown.py`: markdown rendering for research-loop reports.
- `src/crypto_alpha_agent/data/ingestion.py`: narrow network ingestion services with explicit gates.
- `tests/test_research_loop_pipeline.py`: stored-data loop tests.
- `tests/test_cli_research_loop.py`: CLI loop and report artifact tests.
- `tests/test_binance_public_pipeline_ingestion.py`: gated Binance Public Data ingestion service tests.

Modify:

- `src/crypto_alpha_agent/cli.py`: add `research-loop` command and wire actual gated Binance Public Data ingestion.
- `docs/roadmap.md`: record each completed batch and next smallest useful slice.
- `README.md`: document the one-command Phase 1 workflow.

Later batches will also create:

- `src/crypto_alpha_agent/validation/market_history.py`
- `src/crypto_alpha_agent/validation/funding.py`
- `src/crypto_alpha_agent/validation/walk_forward.py`
- `src/crypto_alpha_agent/prompts/*.md`
- `src/crypto_alpha_agent/scheduler.py`
- `docs/evidence/*.md`

---

## Batch 1: Real Data Closed-Loop MVP

### Task 1: Stored-Data Research Loop

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/__init__.py`
- Create: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Test: `tests/test_research_loop_pipeline.py`

- [ ] **Step 1: Write the failing pipeline tests**

```python
from datetime import UTC, datetime

from crypto_alpha_agent.data.models import DataSuitability, FundingRateRecord, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


def test_stored_research_loop_generates_hypotheses_from_sqlite_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candle = MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=112.0,
        low=99.0,
        close=110.0,
        volume=2500.0,
        suitability=DataSuitability(min_capital_usd=25.0, latency_dependency="low", rpc_dependency="none"),
        raw={"fixture": "candle"},
    )
    funding = FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 16, 8, tzinfo=UTC),
        funding_rate=0.0006,
        suitability=DataSuitability(min_capital_usd=50.0, latency_dependency="low", rpc_dependency="none"),
        raw={"fixture": "funding"},
    )
    store.upsert_records(
        [
            candle.to_source_record(),
            SourceRecord(
                record_id="ccxt:BTCUSDT:funding:2026-05-16T08:00:00+00:00",
                source="ccxt",
                record_type="funding_rate",
                observed_at=funding.timestamp,
                payload=funding.model_dump(mode="json"),
            ),
        ]
    )

    report = run_stored_research_loop(db_path, current_capital_usd=300.0, run_id="unit-loop")

    assert report.run_id == "unit-loop"
    assert report.loaded_records == 2
    assert report.signal_count == 2
    assert report.anomaly_count == 2
    assert report.hypothesis_count == 2
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert report.hypotheses[0].action_mode == "research_only"


def test_stored_research_loop_reports_empty_store_without_error(tmp_path):
    db_path = tmp_path / "empty.sqlite"
    ResearchDataStore(db_path)

    report = run_stored_research_loop(db_path, current_capital_usd=300.0)

    assert report.loaded_records == 0
    assert report.signal_count == 0
    assert report.hypothesis_count == 0
    assert "no_stored_records" in report.notes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research_loop_pipeline.py -q`

Expected: FAIL because `crypto_alpha_agent.pipeline` does not exist.

- [ ] **Step 3: Implement the minimal pipeline**

Create `ResearchLoopReport` in `src/crypto_alpha_agent/pipeline/research_loop.py` with these fields:

```python
run_id: str
db_path: str
source_filter: str | None
record_type_filter: str | None
current_capital_usd: float
loaded_records: int
signal_count: int
anomaly_count: int
hypothesis_count: int
weak_signal_count: int
blocked_hypothesis_count: int
uses_real_capital: bool
live_order_routing: bool
records: list[SourceRecord]
signals: list[ScannerSignal]
anomalies: list[RankedAnomaly]
hypotheses: list[AlphaHypothesis]
notes: list[str]
```

Implement `run_stored_research_loop(db_path, *, current_capital_usd=300.0, source=None, record_type=None, limit=None, run_id=None)`.

Behavior:

- Open `ResearchDataStore(db_path)`.
- Load records by optional source and record type.
- If `limit` is set, keep the most recent `limit` records while preserving chronological order.
- Convert records with `records_to_scanner_signals`.
- Rank with `AnomalyDetector().rank`.
- Generate with `HypothesisGenerator().generate`.
- Set `uses_real_capital=False` and `live_order_routing=False`.
- Add `no_stored_records` to notes if no records load.
- Add `no_scanner_signals` to notes if records do not convert to scanner signals.
- Add `weak_signals_present` when at least one signal is weak.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_research_loop_pipeline.py -q`

Expected: PASS.

- [ ] **Step 5: Run related regression tests**

Run: `uv run pytest tests/test_scanner_bridge_low_capital.py tests/test_hypothesis_generation.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crypto_alpha_agent/pipeline tests/test_research_loop_pipeline.py
git commit -m "feat: add stored data research loop"
```

**Exit criteria:** SQLite records can produce signals, ranked anomalies, research-only hypotheses, and a serializable report without touching live capital.

### Task 2: Offline `research-loop` CLI Command

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_cli_research_loop.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
import json
from datetime import UTC, datetime

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore


def test_research_loop_cli_reads_existing_sqlite_records(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candle = MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="ETH/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1500.0,
    )
    store.upsert_records([candle.to_source_record()])

    exit_code = main(["research-loop", "--db", str(db_path), "--current-capital-usd", "300", "--run-id", "cli-loop"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "research-loop"
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["report"]["run_id"] == "cli-loop"
    assert payload["report"]["loaded_records"] == 1
    assert payload["report"]["hypothesis_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_research_loop.py -q`

Expected: FAIL because the command is missing.

- [ ] **Step 3: Add parser and handler**

Add a `research-loop` subcommand with:

- `--db` required `Path`
- `--current-capital-usd` default `300.0`
- `--source` optional string
- `--record-type` choices `market_candle`, `funding_rate`, `dex_pair`, `defi_yield`, `source_health`
- `--limit` optional positive int
- `--run-id` optional string

Handler behavior:

- Call `run_stored_research_loop`.
- Return JSON with `command`, `mode="research_only"`, `uses_real_capital=False`, `live_order_routing=False`, and `report`.
- Do not add any network behavior in this task.

- [ ] **Step 4: Run CLI tests**

Run: `uv run pytest tests/test_cli_research_loop.py tests/test_cli_ingest.py tests/test_cli_smoke.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/cli.py tests/test_cli_research_loop.py
git commit -m "feat: add offline research loop cli"
```

**Exit criteria:** One safe local command can run the stored-data loop and return machine-readable JSON.

### Task 3: Gated Binance Public Data Ingestion Service

**Files:**
- Create: `src/crypto_alpha_agent/data/ingestion.py`
- Test: `tests/test_binance_public_pipeline_ingestion.py`

- [ ] **Step 1: Write failing ingestion service tests**

```python
from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.ingestion import ingest_binance_public_month
from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore


class FakeBinanceClient:
    def download_monthly_spot_klines(self, symbol: str, interval: str, year: int, month: int):
        assert (symbol, interval, year, month) == ("BTCUSDT", "1h", 2026, 5)
        return [
            MarketCandle(
                source="binance_public",
                venue="binance",
                symbol="BTC/USDT",
                timestamp=datetime(2026, 5, 1, tzinfo=UTC),
                timeframe="1h",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
            ),
            MarketCandle(
                source="binance_public",
                venue="binance",
                symbol="BTC/USDT",
                timestamp=datetime(2026, 5, 1, 1, tzinfo=UTC),
                timeframe="1h",
                open=100.5,
                high=102.0,
                low=100.0,
                close=101.5,
                volume=1100.0,
            ),
        ]


def test_binance_ingestion_requires_network_gate(tmp_path):
    with pytest.raises(ValueError, match="allow_network"):
        ingest_binance_public_month(
            db_path=tmp_path / "research.sqlite",
            symbol="BTCUSDT",
            interval="1h",
            year=2026,
            month=5,
            allow_network=False,
            client=FakeBinanceClient(),
        )


def test_binance_ingestion_persists_candles_with_fake_client(tmp_path):
    db_path = tmp_path / "research.sqlite"

    summary = ingest_binance_public_month(
        db_path=db_path,
        symbol="BTCUSDT",
        interval="1h",
        year=2026,
        month=5,
        allow_network=True,
        client=FakeBinanceClient(),
    )

    records = ResearchDataStore(db_path).load_records(record_type="market_candle", source="binance_public")
    assert summary.source == "binance_public"
    assert summary.records_fetched == 2
    assert summary.records_written == 2
    assert summary.uses_real_capital is False
    assert summary.live_order_routing is False
    assert [record.payload["symbol"] for record in records] == ["BTC/USDT", "BTC/USDT"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_binance_public_pipeline_ingestion.py -q`

Expected: FAIL because `crypto_alpha_agent.data.ingestion` is missing.

- [ ] **Step 3: Implement ingestion service**

Create `IngestionSummary` with:

```python
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
```

Implement `ingest_binance_public_month(...)`:

- Raise `ValueError("--allow-network is required for Binance Public Data ingestion")` if `allow_network` is false.
- Default `client` to `BinancePublicDataClient()` only after the network gate passes.
- Download candles.
- Upsert `candle.to_source_record()` records into `ResearchDataStore`.
- Return `IngestionSummary` with `uses_real_capital=False`, `live_order_routing=False`, and a note that data is for research and paper validation only.

- [ ] **Step 4: Run ingestion tests**

Run: `uv run pytest tests/test_binance_public_pipeline_ingestion.py tests/test_binance_public_ingestion.py tests/test_data_models_store.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/data/ingestion.py tests/test_binance_public_pipeline_ingestion.py
git commit -m "feat: add gated binance public data ingestion"
```

**Exit criteria:** The code can persist real Binance Public Data candles, but tests use a fake client and the network gate is mandatory.

### Task 4: One-Command Network-Gated Research Loop

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_cli_research_loop.py`

- [ ] **Step 1: Add failing CLI test for gated pre-ingestion**

Append this test:

```python
from crypto_alpha_agent.data.ingestion import IngestionSummary


def test_research_loop_cli_can_ingest_binance_before_loop(monkeypatch, capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"

    def fake_ingest(**kwargs):
        assert kwargs["allow_network"] is True
        store = ResearchDataStore(kwargs["db_path"])
        candle = MarketCandle(
            source="binance_public",
            venue="binance",
            symbol="BTC/USDT",
            timestamp=datetime(2026, 5, 1, tzinfo=UTC),
            timeframe="1h",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0,
        )
        store.upsert_records([candle.to_source_record()])
        return IngestionSummary(
            source="binance_public",
            db_path=str(kwargs["db_path"]),
            symbols=[kwargs["symbol"]],
            timeframe=kwargs["interval"],
            year=kwargs["year"],
            month=kwargs["month"],
            records_fetched=1,
            records_written=1,
            network_allowed=True,
            uses_real_capital=False,
            live_order_routing=False,
            notes=["fake ingestion"],
        )

    monkeypatch.setattr("crypto_alpha_agent.cli.ingest_binance_public_month", fake_ingest)

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--source",
            "binance-public",
            "--symbol",
            "BTCUSDT",
            "--timeframe",
            "1h",
            "--year",
            "2026",
            "--month",
            "5",
            "--allow-network",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ingestion"]["records_written"] == 1
    assert payload["report"]["loaded_records"] == 1
    assert payload["uses_real_capital"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_research_loop.py::test_research_loop_cli_can_ingest_binance_before_loop -q`

Expected: FAIL because `research-loop` has no network-gated pre-ingestion options.

- [ ] **Step 3: Wire gated ingestion into `research-loop`**

Add these optional args to `research-loop`:

- `--source` choices `binance-public`
- `--allow-network`
- `--symbol`
- `--timeframe` default `1h`
- `--year`
- `--month`

Behavior:

- If `--source binance-public` is provided, require `--allow-network`, `--symbol`, `--year`, and `--month`.
- Call `ingest_binance_public_month`.
- Then run `run_stored_research_loop` on the same database.
- Include `ingestion` in the JSON payload when ingestion ran.
- Keep `uses_real_capital=False` and `live_order_routing=False`.

- [ ] **Step 4: Run CLI regression tests**

Run: `uv run pytest tests/test_cli_research_loop.py tests/test_cli_ingest.py tests/test_cli_smoke.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/cli.py tests/test_cli_research_loop.py
git commit -m "feat: run gated binance ingestion before research loop"
```

**Exit criteria:** The roadmap command shape works for Binance Public Data with explicit network permission.

### Task 5: Daily Markdown Report Artifact

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_cli_research_loop.py`

- [ ] **Step 1: Write failing report artifact test**

```python
def test_research_loop_cli_writes_markdown_report(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "daily-report.md"
    store = ResearchDataStore(db_path)
    candle = MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="SOL/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=107.0,
        low=99.0,
        close=106.0,
        volume=1200.0,
    )
    store.upsert_records([candle.to_source_record()])

    exit_code = main(["research-loop", "--db", str(db_path), "--report-out", str(report_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["report_artifact"] == str(report_path)
    text = report_path.read_text()
    assert "# Crypto Alpha Research Loop" in text
    assert "SOL/USDT" in text
    assert "Live order routing: false" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_research_loop.py::test_research_loop_cli_writes_markdown_report -q`

Expected: FAIL because `--report-out` is missing.

- [ ] **Step 3: Implement markdown renderer and CLI write**

Implement `render_research_loop_markdown(report: ResearchLoopReport) -> str`.

Required sections:

- Title `# Crypto Alpha Research Loop`
- Safety lines for current capital, real capital, and live order routing.
- Counts: records, signals, anomalies, hypotheses, weak signals, blocked hypotheses.
- Top anomalies table with asset, metric, value, classification, score, executable.
- Hypotheses section with asset, what changed, why it might be edge, actionability, disconfirmation tests.
- Notes section.

Add `--report-out Path` to `research-loop`. When present, write markdown to that path and include `report_artifact`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_cli_research_loop.py tests/test_research_loop_pipeline.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/cli.py tests/test_cli_research_loop.py
git commit -m "feat: write research loop markdown reports"
```

**Exit criteria:** The operator gets a human-readable report suitable for daily review and later memory ingestion.

### Task 6: Documentation And Roadmap Update For Phase 1

**Files:**
- Modify: `README.md`
- Modify: `docs/roadmap.md`
- Test: no code test; run formatting and full regression.

- [ ] **Step 1: Update README workflow**

Add a Phase 1 command example:

```bash
uv run crypto-alpha-agent research-loop \
  --db var/research.sqlite \
  --source binance-public \
  --symbol BTCUSDT \
  --timeframe 1h \
  --year 2026 \
  --month 5 \
  --current-capital-usd 300 \
  --allow-network \
  --report-out var/reports/daily.md
```

State that this pulls public historical data only, writes local SQLite records, generates research-only hypotheses, and submits no orders.

- [ ] **Step 2: Update roadmap**

Move Phase 1 from active-only to partially complete or complete depending on tests. Record:

- Real Binance Public Data ingestion is wired.
- Stored records can be scanned, ranked, and turned into hypotheses.
- Markdown report artifacts exist.
- Remaining next slice is historical validation over persisted data.

- [ ] **Step 3: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
git diff --check
```

Expected: tests pass, ruff passes, no whitespace errors.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/roadmap.md
git commit -m "docs: document real data research loop"
```

**Exit criteria:** A new operator can run and understand the Phase 1 MVP.

---

## Batch 2: Real Historical Strategy Validation

### Task 7: Stored Candle History Loader

**Files:**
- Create: `src/crypto_alpha_agent/validation/market_history.py`
- Test: `tests/test_market_history_validation.py`

- [ ] **Step 1:** Write a test that stores three `MarketCandle` records and asserts `load_candle_history(db_path, symbol="BTC/USDT", timeframe="1h")` returns chronologically sorted rows with timestamp, open, high, low, close, volume.
- [ ] **Step 2:** Run `uv run pytest tests/test_market_history_validation.py -q` and confirm import failure.
- [ ] **Step 3:** Implement `CandleBar` Pydantic model and `load_candle_history`.
- [ ] **Step 4:** Run the focused test and scanner bridge tests.
- [ ] **Step 5:** Commit `feat: load stored candle history for validation`.

### Task 8: Simple Real-Data Momentum Validator

**Files:**
- Create: `src/crypto_alpha_agent/validation/momentum.py`
- Test: `tests/test_momentum_validator.py`

- [ ] **Step 1:** Write a test with deterministic prices `[100, 102, 101, 105, 107, 104]` asserting the validator returns trade count, gross return, fee-adjusted return, max drawdown, and rejects when trades are fewer than two.
- [ ] **Step 2:** Verify red with `uv run pytest tests/test_momentum_validator.py -q`.
- [ ] **Step 3:** Implement a conservative long-only close-to-close momentum validator with fee and slippage inputs.
- [ ] **Step 4:** Verify green and run `uv run pytest tests/test_backtest_results.py tests/test_momentum_validator.py -q`.
- [ ] **Step 5:** Commit `feat: validate momentum on stored market history`.

### Task 9: Funding Extremity Validator

**Files:**
- Create: `src/crypto_alpha_agent/validation/funding.py`
- Test: `tests/test_funding_validator.py`

- [ ] **Step 1:** Write tests for positive and negative funding extremes using stored `FundingRateRecord` payloads.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement `FundingExtremityResult` and `validate_funding_extremes` with thresholds, sample count, mean, max absolute funding, and blocked reasons.
- [ ] **Step 4:** Verify green with `uv run pytest tests/test_funding_validator.py tests/test_scanner_bridge_low_capital.py -q`.
- [ ] **Step 5:** Commit `feat: validate funding rate extremes`.

### Task 10: Walk-Forward Split Utility

**Files:**
- Create: `src/crypto_alpha_agent/validation/walk_forward.py`
- Test: `tests/test_walk_forward.py`

- [ ] **Step 1:** Write tests that split 100 bars into deterministic train/test windows and reject too-short histories.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement window generation with explicit minimum train and test sizes.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: add walk forward validation splits`.

### Task 11: Validation Summary In Research Report

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Test: `tests/test_research_loop_validation_summary.py`

- [ ] **Step 1:** Write a test that stores enough candles, runs the research loop with `include_validation=True`, and asserts the report includes validation status, fee-adjusted expectancy, trade count, and blocked reasons.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Wire conservative validators into the report without allowing paper/live actions.
- [ ] **Step 4:** Verify green and run full Batch 1 tests.
- [ ] **Step 5:** Commit `feat: include historical validation in research reports`.

---

## Batch 3: Charter-Constrained LLM Research Agents

### Task 12: Prompt Templates

**Files:**
- Create: `src/crypto_alpha_agent/prompts/supervisor.md`
- Create: `src/crypto_alpha_agent/prompts/scanner.md`
- Create: `src/crypto_alpha_agent/prompts/hypothesis_generator.md`
- Create: `src/crypto_alpha_agent/prompts/coder.md`
- Create: `src/crypto_alpha_agent/prompts/reflexion.md`
- Test: `tests/test_prompt_contracts.py`

- [ ] **Step 1:** Write tests asserting each prompt contains the charter constraints: few hundred USD, no premium RPC, no MEV, no sub-second arbitrage, research-only default, falsifiable evidence.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Write concise prompts that force JSON outputs, assumptions, disconfirmation tests, and explicit rejection of speed-dependent ideas.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: add charter constrained agent prompts`.

### Task 13: LLM Task Envelope Models

**Files:**
- Create: `src/crypto_alpha_agent/agents/llm_contracts.py`
- Test: `tests/test_llm_contracts.py`

- [ ] **Step 1:** Write tests for `ResearchTask`, `HypothesisProposal`, `ValidationRequest`, and `CritiqueResult`.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement strict Pydantic models that reject live-order instructions and private-key fields.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: define llm research contracts`.

### Task 14: Charter Guard For Generated Ideas

**Files:**
- Create: `src/crypto_alpha_agent/risk/charter_guard.py`
- Test: `tests/test_charter_guard.py`

- [ ] **Step 1:** Write tests that block MEV, premium RPC, bridge races, flash loans, and high-capital ideas while allowing funding/basis research.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement deterministic text and metadata checks returning reason codes.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: guard generated ideas with project charter`.

### Task 15: LLM Research Node Adapter

**Files:**
- Create: `src/crypto_alpha_agent/agents/llm_researcher.py`
- Test: `tests/test_llm_researcher_adapter.py`

- [ ] **Step 1:** Write tests using a fake LLM callable that returns valid and invalid JSON.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement adapter that builds prompt context from reports, parses strict JSON, runs `charter_guard`, and returns accepted or rejected proposals.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: add llm research adapter`.

### Task 16: LangGraph Integration For LLM Research Loop

**Files:**
- Modify: `src/crypto_alpha_agent/orchestrator.py`
- Test: `tests/test_llm_graph_routing.py`

- [ ] **Step 1:** Write tests that a fake LLM proposal flows through guard, validator request, critique, memory update, and human checkpoint when paper action is suggested.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Add opt-in graph nodes; keep existing deterministic loop unchanged.
- [ ] **Step 4:** Verify green and run all graph tests.
- [ ] **Step 5:** Commit `feat: integrate charter constrained llm research loop`.

---

## Batch 4: Memory, Scheduler, And Paper Evidence

### Task 17: Real-Data Hypothesis Memory Persistence

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/memory.py`
- Test: `tests/test_research_loop_memory.py`

- [ ] **Step 1:** Write tests that a research-loop report persists accepted and blocked hypotheses as `MemoryRecord` objects with tags and rejection reasons.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement `persist_research_loop_memory(report, memory_path)`.
- [ ] **Step 4:** Verify green and run memory tests.
- [ ] **Step 5:** Commit `feat: persist real data hypotheses to memory`.

### Task 18: Daily Scheduler Command

**Files:**
- Create: `src/crypto_alpha_agent/scheduler.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_scheduler_cli.py`

- [ ] **Step 1:** Write tests for a dry-run daily job plan that emits commands without sleeping.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement a local scheduler helper and CLI `schedule --dry-run`.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: add dry run daily scheduler`.

### Task 19: Paper Evidence Package

**Files:**
- Create: `src/crypto_alpha_agent/evidence/paper.py`
- Test: `tests/test_paper_evidence.py`

- [ ] **Step 1:** Write tests that aggregate paper fills by strategy family and compute sample size, net PnL, hit rate, max drawdown, and failure reasons.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement evidence aggregation over existing paper execution outputs.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: aggregate paper evidence packages`.

### Task 20: Paper Eligibility Gate

**Files:**
- Create: `src/crypto_alpha_agent/risk/paper_gate.py`
- Test: `tests/test_paper_gate.py`

- [ ] **Step 1:** Write tests that require minimum historical trades, positive fee-adjusted expectancy, bounded drawdown, and no charter violations before paper mode.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement deterministic gate returning allowed flag and reason codes.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: gate paper candidates on evidence`.

---

## Batch 5: Tiny-Live Readiness Artifacts Only

### Task 21: Tiny-Live Readiness Checklist Generator

**Files:**
- Create: `src/crypto_alpha_agent/evidence/live_readiness.py`
- Test: `tests/test_live_readiness.py`

- [ ] **Step 1:** Write tests proving no live order function is called and the output is a review artifact only.
- [ ] **Step 2:** Verify red.
- [ ] **Step 3:** Implement checklist generation from rollout gates, paper evidence, and human approval status.
- [ ] **Step 4:** Verify green.
- [ ] **Step 5:** Commit `feat: generate tiny live readiness artifacts`.

### Task 22: Kill Switch And Permission Scope Documentation

**Files:**
- Create: `docs/tiny-live-readiness.md`
- Modify: `docs/rollout-gates.md`
- Test: `git diff --check`

- [ ] **Step 1:** Document exact preconditions for future tiny live testing: human approval, max notional, max loss, venue permissions, read/paper/live key separation, kill switch, and rollback.
- [ ] **Step 2:** Confirm the docs state that no live path exists by default.
- [ ] **Step 3:** Run `git diff --check`.
- [ ] **Step 4:** Commit `docs: define tiny live readiness controls`.

### Task 23: Final Integration Verification

**Files:**
- Modify only if failures require fixes.

- [ ] **Step 1:** Run `uv run pytest -q`.
- [ ] **Step 2:** Run `uv run ruff check .`.
- [ ] **Step 3:** Run `git diff --check`.
- [ ] **Step 4:** Run a smoke workflow:

```bash
uv run crypto-alpha-agent research-loop \
  --db var/test-research.sqlite \
  --current-capital-usd 300 \
  --report-out var/test-report.md
```

- [ ] **Step 5:** Update `docs/roadmap.md` with the verified state and commit `docs: record closed loop implementation status`.

---

## Stop Conditions

Stop and report instead of forcing implementation if:

- A proposed task needs exchange keys, private keys, wallet signing, or live order routing.
- A real source now requires paid access and no free fallback exists.
- Tests reveal existing mainline behavior is broken before a task starts.
- The system starts optimizing for latency races instead of low-capital research.
- A strategy family only works by assuming fills, liquidity, or fees that the owner cannot plausibly get.

## Definition Of Done For This Plan

The plan is complete when the system can:

1. Pull limited real public data with explicit network permission.
2. Store normalized records durably.
3. Generate scanner signals, anomalies, hypotheses, and reports from stored records.
4. Validate at least one simple strategy family against stored history.
5. Persist accepted and rejected hypotheses to memory.
6. Produce daily research artifacts.
7. Gate paper candidates on evidence.
8. Produce tiny-live readiness artifacts without live trading code.

Live trading remains out of scope until a future human-approved charter revision and rollout gate package exist.
