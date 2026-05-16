# Paper Evidence Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next low-capital money-focused slice: a deterministic evidence factory that turns stored public data into validated strategy candidates, repeated paper-simulation outcomes, paper evidence packages, reports, and memory feedback without live trading.

**Architecture:** Keep the existing research kernel and add a narrow evidence-production lane. SQLite remains the local durable store; validators are deterministic; paper outcomes are simulated from stored public data; LLMs may consume evidence later but do not create execution authority. The first strategy family is funding extremity plus price confirmation because it fits a few-hundred-dollar account and ordinary public APIs better than speed arbitrage.

**Tech Stack:** Python 3.12, uv, pytest, ruff, Pydantic, SQLite stdlib, existing Binance Public Data and CCXT collectors, existing validation, paper, memory, CLI, and Markdown modules.

---

## Governing Constraints

The project charter in `docs/project-charter.md` is binding:

- Profit-first, low-capital research for an owner with only a few hundred USD.
- Ordinary public APIs/RPC only; no speed edge, premium RPC, MEV, mempool, flash-loan races, bridge races, or high-capital balance-sheet strategies.
- Research and paper validation first; no live order routing, no wallet keys, and no real capital.
- The system must preserve failed evidence and avoid retesting already rejected assumptions.

## Current Gap This Plan Closes

The project already has:

- Real-data storage, scanner bridge, research-loop reports, and Binance Public Data ingestion.
- CCXT OHLCV/funding collectors, but not a CLI/service that writes those records to SQLite.
- Simple momentum and funding validators, but no combined funding-plus-price validator and no hard walk-forward gate.
- Paper account and evidence aggregation, but no sustained paper-simulation loop or paper outcome ledger.
- Memory persistence for research hypotheses, but not for paper evidence and rejection outcomes.

This plan deliberately does **not** add live trading or a broader agent framework. It creates evidence production.

## File Map

Create:

- `src/crypto_alpha_agent/evidence/models.py`: strict strategy candidate, experiment, validation evidence, and paper simulation outcome models.
- `src/crypto_alpha_agent/evidence/ledger.py`: SQLite paper outcome ledger.
- `src/crypto_alpha_agent/validation/funding_price.py`: deterministic funding extremity plus price confirmation validator.
- `src/crypto_alpha_agent/validation/gates.py`: reusable walk-forward evidence gate helpers.
- `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`: stored-data paper simulation loop and report model.
- `tests/test_evidence_models.py`
- `tests/test_ccxt_ingestion_service.py`
- `tests/test_funding_price_validator.py`
- `tests/test_walk_forward_gate.py`
- `tests/test_paper_outcome_ledger.py`
- `tests/test_paper_sim_loop.py`
- `tests/test_research_loop_paper_evidence.py`
- `tests/test_paper_memory.py`

Modify:

- `src/crypto_alpha_agent/data/ingestion.py`: add CCXT OHLCV and funding history ingestion services.
- `src/crypto_alpha_agent/cli.py`: wire `ingest --source ccxt` and add `paper-sim-loop`.
- `src/crypto_alpha_agent/evidence/__init__.py`: export new evidence models and ledger.
- `src/crypto_alpha_agent/validation/__init__.py`: export funding-price validator and walk-forward gate.
- `src/crypto_alpha_agent/pipeline/research_loop.py`: optionally attach paper evidence packages to reports.
- `src/crypto_alpha_agent/pipeline/markdown.py`: render paper evidence section.
- `src/crypto_alpha_agent/pipeline/memory.py`: persist paper evidence and paper failures into long-term memory.
- `docs/roadmap.md`: mark the new evidence-factory slice and remaining gaps after implementation.
- `README.md` or `docs/runbook.md`: document the safe paper evidence workflow.

---

## Task 1: Evidence Domain Models

**Files:**
- Create: `src/crypto_alpha_agent/evidence/models.py`
- Modify: `src/crypto_alpha_agent/evidence/__init__.py`
- Test: `tests/test_evidence_models.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.evidence.models import (
    ExperimentRun,
    PaperSimulationOutcome,
    StrategyCandidate,
    ValidationEvidence,
)


def test_strategy_candidate_preserves_low_capital_constraints():
    candidate = StrategyCandidate(
        candidate_id="cand-funding-btc-001",
        strategy_family="funding_extremity_price_confirmation",
        symbol="BTC/USDT",
        venue="binance",
        timeframe="1h",
        parameters={"funding_threshold_abs": 0.0005, "hold_bars": 3},
        current_capital_usd=300.0,
        min_capital_usd=25.0,
        data_sources=["ccxt", "binance_public"],
        created_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert candidate.execution_mode == "research_and_paper_only"
    assert candidate.requires_speed_edge is False
    assert candidate.requires_premium_rpc is False
    assert candidate.live_order_routing is False


def test_strategy_candidate_rejects_unsuitable_execution_requirements():
    with pytest.raises(ValidationError):
        StrategyCandidate(
            candidate_id="cand-bad",
            strategy_family="subsecond_arbitrage",
            symbol="ETH/USDT",
            venue="binance",
            timeframe="1m",
            parameters={},
            current_capital_usd=300.0,
            min_capital_usd=5000.0,
            data_sources=["private_rpc"],
            created_at=datetime(2026, 5, 17, tzinfo=UTC),
            requires_speed_edge=True,
        )


def test_validation_evidence_blocks_when_walk_forward_is_missing():
    evidence = ValidationEvidence(
        strategy_family="funding_extremity_price_confirmation",
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price",
        trade_count=12,
        net_return=0.04,
        gross_expectancy=0.004,
        fee_adjusted_expectancy=0.003,
        slippage_adjusted_expectancy=0.002,
        max_drawdown=0.03,
        walk_forward_split_count=0,
        walk_forward_pass_rate=0.0,
        approved=False,
        blocked_reasons=["insufficient_walk_forward_splits"],
    )

    assert evidence.approved is False
    assert "insufficient_walk_forward_splits" in evidence.blocked_reasons


def test_paper_simulation_outcome_cannot_touch_live_capital():
    with pytest.raises(ValidationError):
        PaperSimulationOutcome(
            outcome_id="paper-001",
            run_id="run-001",
            candidate_id="cand-001",
            strategy_family="funding_extremity_price_confirmation",
            symbol="BTC/USDT",
            observed_at=datetime(2026, 5, 17, tzinfo=UTC),
            status="closed",
            signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
            entry_price=100.0,
            exit_price=101.0,
            quantity=0.1,
            notional_usd=10.0,
            gross_pnl_usd=0.1,
            fees_usd=0.02,
            slippage_usd=0.01,
            net_pnl_usd=0.07,
            max_drawdown_usd=0.02,
            touched_real_capital=True,
        )


def test_experiment_run_links_candidate_validation_and_paper_outcomes():
    run = ExperimentRun(
        run_id="exp-001",
        candidate_id="cand-001",
        strategy_family="funding_extremity_price_confirmation",
        started_at=datetime(2026, 5, 17, tzinfo=UTC),
        data_sources=["ccxt", "binance_public"],
        status="paper_simulated",
        validation_evidence_ids=["validation-001"],
        paper_outcome_ids=["paper-001", "paper-002"],
        notes=["research_only"],
    )

    assert run.live_order_routing is False
    assert run.status == "paper_simulated"
```

- [ ] **Step 2: Run the tests and verify red**

Run: `uv run --extra dev pytest tests/test_evidence_models.py -q`

Expected: FAIL because `crypto_alpha_agent.evidence.models` does not exist.

- [ ] **Step 3: Implement the models**

Create strict Pydantic models with these behaviors:

- `StrategyCandidate`
  - Fields: `candidate_id`, `strategy_family`, `symbol`, `venue`, `timeframe`, `parameters`, `current_capital_usd`, `min_capital_usd`, `data_sources`, `created_at`, `execution_mode`, `requires_speed_edge`, `requires_premium_rpc`, `live_order_routing`, `blocked_reasons`.
  - Defaults: `execution_mode="research_and_paper_only"`, `requires_speed_edge=False`, `requires_premium_rpc=False`, `live_order_routing=False`.
  - Validation: reject `requires_speed_edge=True`, `requires_premium_rpc=True`, `live_order_routing=True`, or `min_capital_usd > current_capital_usd`.
- `ValidationEvidence`
  - Fields: `evidence_id`, `strategy_family`, `symbol`, `timeframe`, `validator_name`, `trade_count`, `net_return`, `gross_expectancy`, `fee_adjusted_expectancy`, `slippage_adjusted_expectancy`, `max_drawdown`, `walk_forward_split_count`, `walk_forward_pass_rate`, `approved`, `blocked_reasons`.
  - Auto-generate stable `evidence_id` when omitted from the main fields.
- `PaperSimulationOutcome`
  - Fields: `outcome_id`, `run_id`, `candidate_id`, `strategy_family`, `symbol`, `observed_at`, `status`, `signal_timestamp`, `entry_price`, `exit_price`, `quantity`, `notional_usd`, `gross_pnl_usd`, `fees_usd`, `slippage_usd`, `net_pnl_usd`, `max_drawdown_usd`, `failure_reasons`, `touched_real_capital`, `live_order_routing`.
  - Defaults: `touched_real_capital=False`, `live_order_routing=False`.
  - Validation: reject live capital or live order routing.
- `ExperimentRun`
  - Fields: `run_id`, `candidate_id`, `strategy_family`, `started_at`, `data_sources`, `status`, `validation_evidence_ids`, `paper_outcome_ids`, `notes`, `live_order_routing`.
  - Validation: reject live order routing.

- [ ] **Step 4: Run focused tests**

Run: `uv run --extra dev pytest tests/test_evidence_models.py -q`

Expected: PASS.

- [ ] **Step 5: Run related tests**

Run: `uv run --extra dev pytest tests/test_paper_evidence.py tests/test_live_readiness.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crypto_alpha_agent/evidence tests/test_evidence_models.py
git commit -m "feat: add evidence factory domain models"
```

**Exit criteria:** The project has explicit, strict, low-capital-safe models for strategy candidates, validation evidence, experiments, and paper simulation outcomes.

---

## Task 2: CCXT OHLCV And Funding Ingestion Services

**Files:**
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_ccxt_ingestion_service.py`

- [ ] **Step 1: Write the failing service and CLI tests**

```python
from datetime import UTC, datetime
import json

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.ingestion import (
    ingest_ccxt_funding_rate_history,
    ingest_ccxt_ohlcv,
)
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore


class FakeCcxtCollector:
    def __init__(self):
        self.ohlcv_calls = []
        self.funding_calls = []

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params=None):
        self.ohlcv_calls.append((symbol, timeframe, since, limit, params))
        return [
            MarketCandle(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                timeframe=timeframe,
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1000.0,
            )
        ]

    def fetch_funding_rate_history(self, symbol, since=None, limit=None, params=None):
        self.funding_calls.append((symbol, since, limit, params))
        return [
            FundingRateRecord(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                funding_rate=0.0007,
            )
        ]


def test_ingest_ccxt_ohlcv_writes_market_candles(tmp_path):
    db_path = tmp_path / "research.sqlite"
    collector = FakeCcxtCollector()

    summary = ingest_ccxt_ohlcv(
        db_path,
        symbol="BTC/USDT",
        timeframe="1h",
        limit=1,
        allow_network=True,
        collector=collector,
    )

    records = ResearchDataStore(db_path).load_records(record_type="market_candle", source="ccxt")
    assert summary.source == "ccxt"
    assert summary.feed == "ohlcv"
    assert summary.records_written == 1
    assert records[0].payload["symbol"] == "BTC/USDT"
    assert collector.ohlcv_calls == [("BTC/USDT", "1h", None, 1, None)]


def test_ingest_ccxt_funding_writes_funding_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    collector = FakeCcxtCollector()

    summary = ingest_ccxt_funding_rate_history(
        db_path,
        symbol="BTC/USDT:USDT",
        limit=1,
        allow_network=True,
        collector=collector,
    )

    records = ResearchDataStore(db_path).load_records(record_type="funding_rate", source="ccxt")
    assert summary.feed == "funding_rate_history"
    assert summary.records_written == 1
    assert records[0].payload["funding_rate"] == 0.0007


def test_ccxt_ingestion_requires_explicit_network_gate(tmp_path):
    collector = FakeCcxtCollector()

    try:
        ingest_ccxt_ohlcv(tmp_path / "research.sqlite", symbol="BTC/USDT", timeframe="1h", collector=collector)
    except ValueError as exc:
        assert "allow_network" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_ingest_cli_runs_ccxt_ohlcv_with_network_gate(capsys, tmp_path, monkeypatch):
    db_path = tmp_path / "research.sqlite"

    class PatchedCollector(FakeCcxtCollector):
        pass

    monkeypatch.setattr("crypto_alpha_agent.data.ingestion.CcxtResearchCollector", lambda exchange_id="binance": PatchedCollector())

    exit_code = main(
        [
            "ingest",
            "--db",
            str(db_path),
            "--source",
            "ccxt",
            "--allow-network",
            "--ccxt-feed",
            "ohlcv",
            "--symbol",
            "ETH/USDT",
            "--timeframe",
            "1h",
            "--limit",
            "1",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "ingest"
    assert payload["ingestion"]["feed"] == "ohlcv"
    assert payload["uses_real_capital"] is False
    assert ResearchDataStore(db_path).load_records(record_type="market_candle", source="ccxt")
```

- [ ] **Step 2: Run the tests and verify red**

Run: `uv run --extra dev pytest tests/test_ccxt_ingestion_service.py -q`

Expected: FAIL because CCXT ingestion services and CLI flags are missing.

- [ ] **Step 3: Implement the ingestion services**

Add `CcxtIngestionSummary` and two functions:

```python
def ingest_ccxt_ohlcv(
    db_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    since: int | None = None,
    limit: int | None = None,
    allow_network: bool = False,
    exchange_id: str = "binance",
    collector=None,
) -> CcxtIngestionSummary:
    ...


def ingest_ccxt_funding_rate_history(
    db_path: str | Path,
    *,
    symbol: str,
    since: int | None = None,
    limit: int | None = None,
    allow_network: bool = False,
    exchange_id: str = "binance",
    collector=None,
) -> CcxtIngestionSummary:
    ...
```

Behavior:

- Require `allow_network=True`.
- Use injected `collector` in tests or `CcxtResearchCollector(exchange_id=exchange_id)` in production.
- Convert results to `SourceRecord` with existing model methods or stable record IDs.
- Upsert into `ResearchDataStore`.
- Return `source="ccxt"`, `feed`, `symbols`, `records_fetched`, `records_written`, `network_allowed=True`, `uses_real_capital=False`, and `live_order_routing=False`.

- [ ] **Step 4: Wire CLI**

Extend `ingest` with:

- `--ccxt-feed`, choices `ohlcv` and `funding-rate-history`.
- `--exchange`, default `binance`.
- `--symbol`, required when `--source ccxt`.
- `--timeframe`, required for `ohlcv`.
- `--since`, optional integer timestamp in milliseconds.
- `--limit`, optional positive integer.

For `--source ccxt`, call the correct ingestion service and include `ingestion` in the JSON payload. Preserve safe flags: no real capital, no live routing.

- [ ] **Step 5: Run focused and related tests**

Run:

```bash
uv run --extra dev pytest tests/test_ccxt_ingestion_service.py tests/test_ccxt_collector.py tests/test_cli_ingest.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crypto_alpha_agent/data/ingestion.py src/crypto_alpha_agent/cli.py tests/test_ccxt_ingestion_service.py
git commit -m "feat: ingest ccxt research data into sqlite"
```

**Exit criteria:** Ordinary CCXT OHLCV and funding history data can be written to SQLite through safe, explicit network-gated services and CLI.

---

## Task 3: Funding Extremity Plus Price Confirmation Validator

**Files:**
- Create: `src/crypto_alpha_agent/validation/funding_price.py`
- Modify: `src/crypto_alpha_agent/validation/__init__.py`
- Test: `tests/test_funding_price_validator.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation.funding_price import validate_funding_price_confirmation


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def _funding(hour: int, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        funding_rate=rate,
    )


def test_funding_price_validator_measures_extreme_reversion_edge(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candles = [_candle(i, close) for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100, 98, 101])]
    fundings = [_funding(1, 0.0008), _funding(4, -0.0009), _funding(6, 0.0007)]
    store.upsert_records([item.to_source_record() for item in candles])
    store.upsert_records([item.to_source_record() for item in fundings])

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=2,
        require_walk_forward=False,
    )

    assert result.strategy_family == "funding_extremity_price_confirmation"
    assert result.trade_count == 3
    assert result.extreme_count == 3
    assert result.fee_adjusted_expectancy != result.gross_expectancy
    assert result.slippage_adjusted_expectancy != result.gross_expectancy
    assert result.approved is True
    assert result.blocked_reasons == []


def test_funding_price_validator_blocks_without_enough_trades(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records([_candle(i, 100.0 + i).to_source_record() for i in range(4)])
    store.upsert_records([_funding(1, 0.0008).to_source_record()])

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        min_trades=2,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert "insufficient_trades" in result.blocked_reasons


def test_funding_price_validator_blocks_missing_price_or_funding_data(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        require_walk_forward=False,
    )

    assert result.trade_count == 0
    assert "insufficient_price_bars" in result.blocked_reasons
    assert "insufficient_funding_samples" in result.blocked_reasons
```

- [ ] **Step 2: Run the tests and verify red**

Run: `uv run --extra dev pytest tests/test_funding_price_validator.py -q`

Expected: FAIL because `validation.funding_price` is missing.

- [ ] **Step 3: Implement the validator**

Create `FundingPriceValidationResult` with:

- `strategy_family`
- `symbol`
- `funding_symbol`
- `timeframe`
- `bar_count`
- `funding_sample_count`
- `extreme_count`
- `trade_count`
- `gross_expectancy`
- `net_return`
- `max_drawdown`
- `fee_adjusted_expectancy`
- `slippage_adjusted_expectancy`
- `walk_forward_split_count`
- `walk_forward_pass_rate`
- `approved`
- `blocked_reasons`

Implement `validate_funding_price_confirmation(...)`:

- Load candles from `load_candle_history`.
- Load `funding_rate` records from `ResearchDataStore`.
- Sort all data chronologically.
- Select funding prints where `abs(funding_rate) >= threshold_abs`.
- For each extreme print, find the first candle at or after the funding timestamp and an exit candle `hold_bars` later.
- Use mean-reversion direction by default:
  - Positive funding means crowded longs; directional return is `-(exit / entry - 1)`.
  - Negative funding means crowded shorts; directional return is `exit / entry - 1`.
- Subtract round-trip fee and slippage assumptions for adjusted expectancy.
- Compute cumulative net return and max drawdown over trade returns.
- Add blocked reasons: `insufficient_price_bars`, `insufficient_funding_samples`, `no_extreme_funding`, `insufficient_trades`, `non_positive_expectancy`, `non_positive_net_return`.
- Approve only when there are enough trades, positive adjusted expectancy, positive net return, and no blocked reasons.
- Leave walk-forward strictness off here when `require_walk_forward=False`; Task 4 turns it on and tests the hard gate.

- [ ] **Step 4: Run focused and related tests**

Run:

```bash
uv run --extra dev pytest tests/test_funding_price_validator.py tests/test_funding_validator.py tests/test_market_history_validation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/validation tests/test_funding_price_validator.py
git commit -m "feat: validate funding price confirmation"
```

**Exit criteria:** The project can evaluate a low-frequency funding-plus-price strategy family against stored public data with fee/slippage and rejection reasons.

---

## Task 4: Walk-Forward Gate As A Hard Validator Requirement

**Files:**
- Create: `src/crypto_alpha_agent/validation/gates.py`
- Modify: `src/crypto_alpha_agent/validation/funding_price.py`
- Test: `tests/test_walk_forward_gate.py`

- [ ] **Step 1: Write the failing tests**

```python
from crypto_alpha_agent.validation.gates import WalkForwardGateResult, evaluate_walk_forward_gate


def test_walk_forward_gate_blocks_missing_splits():
    result = evaluate_walk_forward_gate([], min_splits=3, min_pass_rate=0.67)

    assert result.passed is False
    assert result.split_count == 0
    assert result.pass_rate == 0.0
    assert result.blocked_reasons == ["insufficient_walk_forward_splits"]


def test_walk_forward_gate_blocks_low_pass_rate_and_unstable_expectancy():
    result = evaluate_walk_forward_gate([0.01, -0.02, 0.03], min_splits=3, min_pass_rate=0.67)

    assert result.passed is False
    assert result.split_count == 3
    assert result.pass_rate == 2 / 3
    assert "unstable_walk_forward_performance" in result.blocked_reasons


def test_walk_forward_gate_passes_consistent_positive_splits():
    result = evaluate_walk_forward_gate([0.01, 0.02, 0.03], min_splits=3, min_pass_rate=0.67)

    assert isinstance(result, WalkForwardGateResult)
    assert result.passed is True
    assert result.blocked_reasons == []
```

- [ ] **Step 2: Run the tests and verify red**

Run: `uv run --extra dev pytest tests/test_walk_forward_gate.py -q`

Expected: FAIL because `validation.gates` is missing.

- [ ] **Step 3: Implement the gate**

Implement:

```python
class WalkForwardGateResult(BaseModel):
    split_count: int
    pass_count: int
    pass_rate: float
    min_splits: int
    min_pass_rate: float
    passed: bool
    blocked_reasons: list[str]


def evaluate_walk_forward_gate(
    split_expectancies: Sequence[float],
    *,
    min_splits: int = 3,
    min_pass_rate: float = 1.0,
    expectancy_floor: float = 0.0,
) -> WalkForwardGateResult:
    ...
```

Behavior:

- Require positive `min_splits`.
- Require `0 < min_pass_rate <= 1`.
- Treat a split as passing only if expectancy is strictly greater than `expectancy_floor`.
- Add `insufficient_walk_forward_splits` when split count is below minimum.
- Add `unstable_walk_forward_performance` when any split is at or below floor or pass rate is below threshold.

- [ ] **Step 4: Wire funding-price validator to the hard gate**

Update `validate_funding_price_confirmation`:

- Default `require_walk_forward=True`.
- When required, generate walk-forward windows over available candles.
- For each test split, evaluate only trades whose entry and exit candles are inside that test split.
- Pass the split adjusted expectancy list into `evaluate_walk_forward_gate`.
- Copy `walk_forward_split_count`, `walk_forward_pass_rate`, and blocked reasons into `FundingPriceValidationResult`.
- Keep `require_walk_forward=False` for small unit tests and backward-compatible exploratory runs.

- [ ] **Step 5: Add a validator-specific test**

Append to `tests/test_walk_forward_gate.py` a test that calls `validate_funding_price_confirmation` with too few bars and default `require_walk_forward=True`, then asserts:

```python
assert result.approved is False
assert "insufficient_walk_forward_splits" in result.blocked_reasons
```

- [ ] **Step 6: Run focused and related tests**

Run:

```bash
uv run --extra dev pytest tests/test_walk_forward_gate.py tests/test_funding_price_validator.py tests/test_walk_forward.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/crypto_alpha_agent/validation tests/test_walk_forward_gate.py tests/test_funding_price_validator.py
git commit -m "feat: require walk forward evidence for validators"
```

**Exit criteria:** New validators fail closed unless walk-forward evidence is present and stable.

---

## Task 5: Paper Outcome Ledger

**Files:**
- Create: `src/crypto_alpha_agent/evidence/ledger.py`
- Modify: `src/crypto_alpha_agent/evidence/__init__.py`
- Test: `tests/test_paper_outcome_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import UTC, datetime

from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome


def _outcome(outcome_id: str, pnl: float, strategy_family: str = "funding_extremity_price_confirmation"):
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id="paper-run-001",
        candidate_id="cand-001",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=datetime(2026, 5, 17, tzinfo=UTC),
        status="closed",
        signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
        entry_price=100.0,
        exit_price=101.0,
        quantity=0.1,
        notional_usd=10.0,
        gross_pnl_usd=pnl + 0.03,
        fees_usd=0.02,
        slippage_usd=0.01,
        net_pnl_usd=pnl,
        max_drawdown_usd=max(0.0, -pnl),
    )


def test_paper_outcome_ledger_round_trips_outcomes(tmp_path):
    ledger = PaperOutcomeLedger(tmp_path / "research.sqlite")

    written = ledger.upsert_outcomes([_outcome("paper-001", 0.12), _outcome("paper-002", -0.05)])
    loaded = ledger.load_outcomes(strategy_family="funding_extremity_price_confirmation")

    assert written == 2
    assert [item.outcome_id for item in loaded] == ["paper-001", "paper-002"]
    assert loaded[1].net_pnl_usd == -0.05


def test_paper_outcome_ledger_upsert_is_idempotent(tmp_path):
    ledger = PaperOutcomeLedger(tmp_path / "research.sqlite")

    ledger.upsert_outcomes([_outcome("paper-001", 0.12)])
    ledger.upsert_outcomes([_outcome("paper-001", 0.20)])

    loaded = ledger.load_outcomes()
    assert len(loaded) == 1
    assert loaded[0].net_pnl_usd == 0.20
```

- [ ] **Step 2: Run the tests and verify red**

Run: `uv run --extra dev pytest tests/test_paper_outcome_ledger.py -q`

Expected: FAIL because `evidence.ledger` is missing.

- [ ] **Step 3: Implement the ledger**

Create `PaperOutcomeLedger`:

- Constructor accepts `db_path` and creates table `paper_outcomes`.
- Columns: `outcome_id TEXT PRIMARY KEY`, `run_id`, `candidate_id`, `strategy_family`, `symbol`, `observed_at`, `status`, `payload_json`, `inserted_at`.
- `upsert_outcomes(outcomes)` writes sorted JSON with `INSERT OR REPLACE` and returns row count.
- `load_outcomes(strategy_family=None, symbol=None, run_id=None)` returns `PaperSimulationOutcome` ordered by `(observed_at, outcome_id)`.

- [ ] **Step 4: Run focused and related tests**

Run:

```bash
uv run --extra dev pytest tests/test_paper_outcome_ledger.py tests/test_evidence_models.py tests/test_paper_evidence.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/evidence tests/test_paper_outcome_ledger.py
git commit -m "feat: persist paper simulation outcomes"
```

**Exit criteria:** Paper simulation outcomes are durable, idempotent, queryable evidence rather than transient CLI output.

---

## Task 6: Paper Simulation Loop And CLI

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_paper_sim_loop.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import UTC, datetime
import json

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def _funding(hour: int, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        funding_rate=rate,
    )


def _seed_store(db_path):
    store = ResearchDataStore(db_path)
    closes = [100, 103, 101, 99, 102, 104, 101, 100, 98, 101]
    store.upsert_records([_candle(i, close).to_source_record() for i, close in enumerate(closes)])
    store.upsert_records([_funding(1, 0.0008).to_source_record(), _funding(4, -0.0009).to_source_record()])


def test_paper_sim_loop_writes_outcomes_without_live_capital(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_store(db_path)

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-run-001",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=300.0,
        notional_usd=25.0,
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-run-001")
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert report.outcome_count == len(loaded)
    assert report.paper_evidence_packages[0].sample_size == len(loaded)
    assert loaded[0].notional_usd <= 25.0


def test_paper_sim_loop_records_blocked_outcome_when_no_signal(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-run-empty",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        require_walk_forward=False,
    )

    assert report.outcome_count == 1
    assert report.outcomes[0].status == "blocked"
    assert "no_signal" in report.outcomes[0].failure_reasons


def test_paper_sim_loop_cli_outputs_json_and_persists_ledger(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_store(db_path)

    exit_code = main(
        [
            "paper-sim-loop",
            "--db",
            str(db_path),
            "--run-id",
            "cli-paper-run",
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
            "--notional-usd",
            "25",
            "--no-require-walk-forward",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "paper-sim-loop"
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert PaperOutcomeLedger(db_path).load_outcomes(run_id="cli-paper-run")
```

- [ ] **Step 2: Run the tests and verify red**

Run: `uv run --extra dev pytest tests/test_paper_sim_loop.py -q`

Expected: FAIL because `pipeline.paper_sim_loop` and CLI command are missing.

- [ ] **Step 3: Implement the loop**

Create `PaperSimLoopReport` with:

- `run_id`
- `db_path`
- `strategy_family`
- `price_symbol`
- `funding_symbol`
- `timeframe`
- `current_capital_usd`
- `notional_usd`
- `validation`
- `outcome_count`
- `outcomes`
- `paper_evidence_packages`
- `uses_real_capital=False`
- `live_order_routing=False`
- `notes`

Implement `run_paper_sim_loop(...)`:

- Only support `funding_extremity_price_confirmation` for this plan.
- Call `validate_funding_price_confirmation`.
- Generate deterministic paper outcomes from the same stored funding extremes and price exits used by the validator.
- If no outcomes can be generated, write one `blocked` outcome with `failure_reasons=["no_signal", ...blocked_reasons]`.
- Cap `notional_usd` at `min(notional_usd, current_capital_usd, 25.0)`.
- Use round-trip costs from `fee_rate` and `slippage_rate`.
- Write all outcomes to `PaperOutcomeLedger`.
- Aggregate evidence with `aggregate_paper_evidence`.

- [ ] **Step 4: Wire CLI**

Add command `paper-sim-loop`:

- Required: `--db`, `--strategy-family`, `--price-symbol`, `--funding-symbol`, `--timeframe`.
- Optional: `--run-id`, `--current-capital-usd`, `--notional-usd`, `--threshold-abs`, `--hold-bars`, `--fee-rate`, `--slippage-rate`, `--min-trades`, `--require-walk-forward` / `--no-require-walk-forward`, `--report-out`.
- Output JSON with `command`, `mode="paper_simulation_only"`, `uses_real_capital=False`, `live_order_routing=False`, and `report`.

- [ ] **Step 5: Run focused and related tests**

Run:

```bash
uv run --extra dev pytest tests/test_paper_sim_loop.py tests/test_paper_outcome_ledger.py tests/test_funding_price_validator.py tests/test_cli_smoke.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crypto_alpha_agent/pipeline/paper_sim_loop.py src/crypto_alpha_agent/cli.py tests/test_paper_sim_loop.py
git commit -m "feat: add paper simulation loop"
```

**Exit criteria:** A safe CLI can repeatedly turn stored public data into durable paper outcomes and evidence packages.

---

## Task 7: Paper Evidence In Research Reports

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_research_loop_paper_evidence.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import UTC, datetime

from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.pipeline.markdown import render_research_loop_markdown
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


def test_research_loop_can_attach_paper_evidence_packages(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            PaperSimulationOutcome(
                outcome_id="paper-001",
                run_id="paper-run",
                candidate_id="cand-001",
                strategy_family="funding_extremity_price_confirmation",
                symbol="BTC/USDT",
                observed_at=datetime(2026, 5, 17, tzinfo=UTC),
                status="closed",
                signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                entry_price=100.0,
                exit_price=101.0,
                quantity=0.1,
                notional_usd=10.0,
                gross_pnl_usd=0.1,
                fees_usd=0.02,
                slippage_usd=0.01,
                net_pnl_usd=0.07,
                max_drawdown_usd=0.01,
            )
        ]
    )

    report = run_stored_research_loop(db_path, include_paper_evidence=True)

    assert report.paper_evidence_packages[0].strategy_family == "funding_extremity_price_confirmation"
    assert report.paper_evidence_packages[0].sample_size == 1


def test_markdown_report_renders_paper_evidence_section(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            PaperSimulationOutcome(
                outcome_id="paper-001",
                run_id="paper-run",
                candidate_id="cand-001",
                strategy_family="funding_extremity_price_confirmation",
                symbol="BTC/USDT",
                observed_at=datetime(2026, 5, 17, tzinfo=UTC),
                status="blocked",
                signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                entry_price=100.0,
                exit_price=100.0,
                quantity=0.0,
                notional_usd=0.0,
                gross_pnl_usd=0.0,
                fees_usd=0.0,
                slippage_usd=0.0,
                net_pnl_usd=0.0,
                max_drawdown_usd=0.0,
                failure_reasons=["no_signal"],
            )
        ]
    )

    report = run_stored_research_loop(db_path, include_paper_evidence=True)
    markdown = render_research_loop_markdown(report)

    assert "## Paper Evidence" in markdown
    assert "funding_extremity_price_confirmation" in markdown
    assert "no_signal" in markdown
```

- [ ] **Step 2: Run the tests and verify red**

Run: `uv run --extra dev pytest tests/test_research_loop_paper_evidence.py -q`

Expected: FAIL because research reports do not include paper evidence packages.

- [ ] **Step 3: Attach paper evidence to the research report**

Modify `ResearchLoopReport`:

- Add `paper_evidence_packages: list[PaperEvidencePackage] = Field(default_factory=list)`.

Modify `run_stored_research_loop`:

- Add `include_paper_evidence: bool = False`.
- When true, load outcomes from `PaperOutcomeLedger(db_path)`, aggregate with `aggregate_paper_evidence`, and attach packages.

Modify CLI `research-loop`:

- Add `--include-paper-evidence`.
- Pass it into `run_stored_research_loop`.

- [ ] **Step 4: Render Markdown**

Add a `## Paper Evidence` section to `render_research_loop_markdown`:

- If no packages: say `No paper evidence packages attached.`
- For each package: render strategy family, sample size, closed count, failed count, net PnL, hit rate, max drawdown, and failure reasons.

- [ ] **Step 5: Run focused and related tests**

Run:

```bash
uv run --extra dev pytest tests/test_research_loop_paper_evidence.py tests/test_research_loop_pipeline.py tests/test_cli_research_loop.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crypto_alpha_agent/pipeline src/crypto_alpha_agent/cli.py tests/test_research_loop_paper_evidence.py
git commit -m "feat: include paper evidence in research reports"
```

**Exit criteria:** Daily research reports can show accumulated paper evidence and failure reasons, not just fresh hypotheses.

---

## Task 8: Paper Evidence Memory Feedback And Documentation

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/memory.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `docs/roadmap.md`
- Modify: `docs/runbook.md`
- Test: `tests/test_paper_memory.py`

- [ ] **Step 1: Write the failing memory tests**

```python
from datetime import UTC, datetime

from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.memory import persist_paper_outcome_memory


def test_paper_outcomes_are_persisted_to_memory_with_failure_reasons(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    outcome = PaperSimulationOutcome(
        outcome_id="paper-001",
        run_id="paper-run",
        candidate_id="cand-001",
        strategy_family="funding_extremity_price_confirmation",
        symbol="BTC/USDT",
        observed_at=datetime(2026, 5, 17, tzinfo=UTC),
        status="blocked",
        signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
        entry_price=100.0,
        exit_price=100.0,
        quantity=0.0,
        notional_usd=0.0,
        gross_pnl_usd=0.0,
        fees_usd=0.0,
        slippage_usd=0.0,
        net_pnl_usd=0.0,
        max_drawdown_usd=0.0,
        failure_reasons=["no_signal", "insufficient_walk_forward_splits"],
    )

    stored = persist_paper_outcome_memory([outcome], memory_path)
    records = MemoryStore(memory_path).load_all()

    assert len(stored) == 1
    assert records[0].opportunity["strategy_family"] == "funding_extremity_price_confirmation"
    assert "no_signal" in records[0].rejected_reasons
    assert "paper-evidence" in records[0].tags
```

- [ ] **Step 2: Run the tests and verify red**

Run: `uv run --extra dev pytest tests/test_paper_memory.py -q`

Expected: FAIL because paper memory persistence is missing.

- [ ] **Step 3: Implement memory persistence**

Add `persist_paper_outcome_memory(outcomes, memory_path)`:

- Use `MemoryStore`.
- Store one record per paper outcome.
- Record ID format: `paper-outcome:<run_id>:<outcome_id>`.
- `opportunity` includes strategy family, symbol, run ID, candidate ID, status, notional, and safe flags.
- `hypothesis` includes paper status, net PnL, fees, slippage, max drawdown, and failure reasons.
- `score` includes numeric paper outcome metrics.
- `rejected_reasons` equals failure reasons for blocked/failed outcomes and `[]` for clean closed outcomes.
- Tags include `paper-evidence`, strategy family, symbol slug, status, and run ID.

- [ ] **Step 4: Wire optional CLI memory output**

Add `--memory` to `paper-sim-loop`.

- If provided, call `persist_paper_outcome_memory(report.outcomes, args.memory)`.
- Include `memory_records_written` and `memory_path` in JSON payload.

- [ ] **Step 5: Update docs**

Update `docs/roadmap.md`:

- Record that the active slice now includes paper simulation loop, paper outcome ledger, paper evidence reports, and memory feedback.
- Keep remaining gaps explicit: broader strategy families, production daily scheduler, longer live paper collection, optional additional data sources, and no live trading.

Update `docs/runbook.md`:

- Add safe workflow:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source ccxt --allow-network --ccxt-feed funding-rate-history --symbol BTC/USDT:USDT --limit 100
uv run --extra dev crypto-alpha-agent research-loop --db var/research.sqlite --include-validation --include-paper-evidence --report-out var/reports/daily.md
uv run --extra dev crypto-alpha-agent paper-sim-loop --db var/research.sqlite --strategy-family funding_extremity_price_confirmation --price-symbol BTC/USDT --funding-symbol BTC/USDT:USDT --timeframe 1h --memory var/memory.jsonl
```

- State that these commands do not touch wallets, live order routing, or real capital.

- [ ] **Step 6: Run focused and related tests**

Run:

```bash
uv run --extra dev pytest tests/test_paper_memory.py tests/test_memory_persistence.py tests/test_paper_sim_loop.py -q
```

Expected: PASS.

- [ ] **Step 7: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
```

Expected:

- All tests pass.
- Ruff passes.
- `git diff --check` reports no whitespace errors.

- [ ] **Step 8: Commit**

```bash
git add src/crypto_alpha_agent/pipeline/memory.py src/crypto_alpha_agent/cli.py docs/roadmap.md docs/runbook.md tests/test_paper_memory.py
git commit -m "feat: feed paper evidence into memory"
```

**Exit criteria:** Paper evidence and rejected paper assumptions become durable memory for the next research iteration, and the operator has documented safe commands.

---

## Final Integration Criteria

After all tasks:

1. `uv run --extra dev pytest -q` passes.
2. `uv run --extra dev ruff check .` passes.
3. `git diff --check` passes.
4. The branch contains no live order routing, wallet-key access, exchange order submission, or real-capital path.
5. The new CLI path can run locally in safe mode:

```bash
uv run --extra dev crypto-alpha-agent research-loop \
  --db var/research.sqlite \
  --current-capital-usd 300 \
  --include-validation \
  --include-paper-evidence \
  --report-out var/reports/daily.md
```

6. The roadmap still names Phase 4 paper evidence accumulation as the active practical target.

## Future Work Not In This Plan

- Production daily runner that actually executes a schedule.
- Additional strategy families beyond funding extremity plus price confirmation.
- Open interest and liquidation data providers such as Coinalyze.
- DefiLlama/Dune/TheGraph slow fundamental validators.
- Tiny-live execution adapters. This plan intentionally keeps tiny live as review artifacts only.
