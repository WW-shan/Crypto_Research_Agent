# Real Historical Strategy Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real historical validation over persisted research data so candidate alpha can be accepted or rejected before any paper-trading proposal.

**Architecture:** Keep validation deterministic and conservative. Load normalized candles and funding records from SQLite, run simple low-capital validators with explicit fees/slippage/drawdown/trade-count metrics, and attach validation summaries to the research report without adding live trading or exchange order routing.

**Tech Stack:** Python 3.12, uv, pytest, ruff, Pydantic, SQLite stdlib, existing `ResearchDataStore`, existing `BacktestResult`/`run_vectorbt_backtest`, existing research-loop report and Markdown renderer.

---

## Constraints

- No live orders, wallet keys, private RPC, mempool, MEV, flash loans, bridge races, or sub-second arbitrage.
- Validation must be possible with stored public data and ordinary hardware.
- Passing validation does not authorize paper trading by itself; it only creates evidence for later gates.
- All validators must include fees/slippage assumptions or explicit blocked reasons.

## File Map

Create:

- `src/crypto_alpha_agent/validation/__init__.py`: public validation exports.
- `src/crypto_alpha_agent/validation/market_history.py`: load persisted candle bars from SQLite.
- `src/crypto_alpha_agent/validation/momentum.py`: conservative close-price momentum validation.
- `src/crypto_alpha_agent/validation/funding.py`: funding-rate extremity validation.
- `src/crypto_alpha_agent/validation/walk_forward.py`: deterministic train/test window generation.
- `tests/test_market_history_validation.py`
- `tests/test_momentum_validator.py`
- `tests/test_funding_validator.py`
- `tests/test_walk_forward.py`
- `tests/test_research_loop_validation_summary.py`

Modify:

- `src/crypto_alpha_agent/pipeline/research_loop.py`: optional validation summaries in `ResearchLoopReport`.
- `src/crypto_alpha_agent/pipeline/markdown.py`: validation section in Markdown report.
- `src/crypto_alpha_agent/cli.py`: optional `--include-validation` flag for `research-loop`.
- `docs/roadmap.md`: record Phase 2 progress after completion.

---

## Task 7: Stored Candle History Loader

**Files:**
- Create: `src/crypto_alpha_agent/validation/__init__.py`
- Create: `src/crypto_alpha_agent/validation/market_history.py`
- Test: `tests/test_market_history_validation.py`

- [ ] **Step 1: Write failing tests**

```python
from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation.market_history import load_candle_history


def _candle(symbol: str, hour: int, close: float, source: str = "binance_public") -> MarketCandle:
    return MarketCandle(
        source=source,
        venue="binance",
        symbol=symbol,
        timestamp=datetime(2026, 5, 16, hour, tzinfo=UTC),
        timeframe="1h",
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        volume=1000.0 + hour,
    )


def test_load_candle_history_filters_symbol_timeframe_and_sorts(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    records = [
        _candle("ETH/USDT", 1, 201.0).to_source_record(),
        _candle("BTC/USDT", 2, 102.0).to_source_record(),
        _candle("BTC/USDT", 0, 100.0).to_source_record(),
        _candle("BTC/USDT", 1, 101.0).to_source_record(),
    ]
    store.upsert_records(records)

    bars = load_candle_history(db_path, symbol="BTC/USDT", timeframe="1h")

    assert [bar.close for bar in bars] == [100.0, 101.0, 102.0]
    assert [bar.timestamp.hour for bar in bars] == [0, 1, 2]
    assert bars[0].source == "binance_public"


def test_load_candle_history_applies_date_range_source_and_recent_limit(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records(
        [
            _candle("BTC/USDT", 0, 100.0).to_source_record(),
            _candle("BTC/USDT", 1, 101.0, source="ccxt").to_source_record(),
            _candle("BTC/USDT", 2, 102.0).to_source_record(),
            _candle("BTC/USDT", 3, 103.0).to_source_record(),
        ]
    )

    bars = load_candle_history(
        db_path,
        symbol="BTC/USDT",
        timeframe="1h",
        source="binance_public",
        start=datetime(2026, 5, 16, 1, tzinfo=UTC),
        end=datetime(2026, 5, 16, 4, tzinfo=UTC),
        limit=2,
    )

    assert [bar.close for bar in bars] == [102.0, 103.0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_market_history_validation.py -q`

Expected: FAIL because `crypto_alpha_agent.validation` does not exist.

- [ ] **Step 3: Implement minimal loader**

Create `CandleBar` in `src/crypto_alpha_agent/validation/market_history.py`:

```python
class CandleBar(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

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
```

Implement:

```python
def load_candle_history(
    db_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    source: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = None,
) -> list[CandleBar]:
```

Behavior:

- Load `market_candle` records from `ResearchDataStore`.
- Validate payloads with `MarketCandle.model_validate`.
- Filter by exact symbol and timeframe.
- Optional `source`, `start <= timestamp`, and `timestamp < end`.
- Sort chronologically by `(timestamp, source, venue, symbol)`.
- If `limit` is set, require `limit > 0`, keep most recent `limit`, preserve chronological order.

- [ ] **Step 4: Run focused and related tests**

Run:

```bash
uv run pytest tests/test_market_history_validation.py tests/test_data_models_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/validation tests/test_market_history_validation.py
git commit -m "feat: load stored candle history"
```

**Exit criteria:** Persisted candle records can be loaded as chronological typed bars for validation.

---

## Task 8: Conservative Momentum Validator

**Files:**
- Create: `src/crypto_alpha_agent/validation/momentum.py`
- Test: `tests/test_momentum_validator.py`

- [ ] **Step 1: Write failing tests**

```python
from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.validation.market_history import CandleBar
from crypto_alpha_agent.validation.momentum import validate_close_momentum


def _bars(closes: list[float]) -> list[CandleBar]:
    start = datetime(2026, 5, 16, tzinfo=UTC)
    return [
        CandleBar(
            source="binance_public",
            venue="binance",
            symbol="BTC/USDT",
            timestamp=start + timedelta(hours=index),
            timeframe="1h",
            open=close,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=1000.0,
        )
        for index, close in enumerate(closes)
    ]


def test_momentum_validator_returns_fee_and_slippage_adjusted_metrics():
    result = validate_close_momentum(
        _bars([100, 103, 106, 104, 108, 112, 109, 113]),
        lookback_bars=1,
        hold_bars=1,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=2,
    )

    assert result.strategy_family == "close_momentum"
    assert result.symbol == "BTC/USDT"
    assert result.timeframe == "1h"
    assert result.bar_count == 8
    assert result.trade_count >= 2
    assert result.net_return != 0.0
    assert result.fee_adjusted_expectancy < result.gross_expectancy
    assert result.slippage_adjusted_expectancy < result.gross_expectancy
    assert result.approved is True
    assert result.blocked_reasons == []


def test_momentum_validator_blocks_when_trade_count_is_too_low():
    result = validate_close_momentum(
        _bars([100, 99, 98, 97]),
        lookback_bars=1,
        hold_bars=1,
        min_trades=1,
    )

    assert result.trade_count == 0
    assert result.approved is False
    assert "insufficient_trades" in result.blocked_reasons


@pytest.mark.parametrize("lookback_bars, hold_bars", [(0, 1), (1, 0)])
def test_momentum_validator_rejects_invalid_windows(lookback_bars, hold_bars):
    with pytest.raises(ValueError):
        validate_close_momentum(_bars([100, 101, 102]), lookback_bars=lookback_bars, hold_bars=hold_bars)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_momentum_validator.py -q`

Expected: FAIL because `validation.momentum` is missing.

- [ ] **Step 3: Implement validator**

Create `MomentumValidationResult` with strict Pydantic config and fields:

```python
strategy_family: str
symbol: str
timeframe: str
bar_count: int
trade_count: int
gross_expectancy: float
net_return: float
max_drawdown: float
fee_adjusted_expectancy: float
slippage_adjusted_expectancy: float
approved: bool
blocked_reasons: list[str]
```

Implement `validate_close_momentum(bars, *, lookback_bars=3, hold_bars=1, fee_rate=0.001, slippage_rate=0.0005, min_trades=3)`.

Behavior:

- Require non-empty bars with one symbol and one timeframe.
- Require `lookback_bars > 0`, `hold_bars > 0`, non-negative fees/slippage.
- Sort by timestamp.
- Generate non-overlapping long-only entries when `close[index] > close[index - lookback_bars]`; exit after `hold_bars`.
- Use `run_vectorbt_backtest(prices, entries, exits, fee_rate, slippage_rate)`.
- Compute `gross_expectancy` as average raw close-to-close trade return before fees/slippage.
- `approved` is true only when `trade_count >= min_trades`, fee-adjusted expectancy is positive, and net return is positive.
- Add blocked reasons: `insufficient_bars`, `insufficient_trades`, `non_positive_expectancy`, `non_positive_net_return`.

- [ ] **Step 4: Run focused and related tests**

Run:

```bash
uv run pytest tests/test_momentum_validator.py tests/test_backtest_results.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/validation/momentum.py tests/test_momentum_validator.py
git commit -m "feat: validate close momentum on stored history"
```

**Exit criteria:** Stored candle bars can be evaluated by a conservative long-only validation strategy.

---

## Task 9: Funding Extremity Validator

**Files:**
- Create: `src/crypto_alpha_agent/validation/funding.py`
- Test: `tests/test_funding_validator.py`

- [ ] **Step 1: Write failing tests**

```python
from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.data.models import FundingRateRecord, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation.funding import validate_funding_extremes


def _funding(symbol: str, hour: int, rate: float) -> SourceRecord:
    record = FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol=symbol,
        timestamp=datetime(2026, 5, 16, hour, tzinfo=UTC),
        funding_rate=rate,
    )
    return SourceRecord(
        record_id=f"ccxt:{symbol}:{hour}",
        source="ccxt",
        record_type="funding_rate",
        observed_at=record.timestamp,
        payload=record.model_dump(mode="json"),
    )


def test_funding_validator_detects_positive_and_negative_extremes(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _funding("BTC/USDT:USDT", 0, 0.0001),
            _funding("BTC/USDT:USDT", 8, 0.0007),
            _funding("BTC/USDT:USDT", 16, -0.0008),
        ]
    )

    result = validate_funding_extremes(
        db_path,
        symbol="BTC/USDT:USDT",
        threshold_abs=0.0005,
        min_samples=3,
        min_extremes=2,
    )

    assert result.strategy_family == "funding_extremity"
    assert result.sample_count == 3
    assert result.extreme_count == 2
    assert result.positive_extreme_count == 1
    assert result.negative_extreme_count == 1
    assert result.max_abs_funding_rate == 0.0008
    assert result.approved is True
    assert result.blocked_reasons == []


def test_funding_validator_blocks_insufficient_samples_and_missing_extremes(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records([_funding("ETH/USDT:USDT", 0, 0.0001)])

    result = validate_funding_extremes(
        db_path,
        symbol="ETH/USDT:USDT",
        threshold_abs=0.0005,
        min_samples=3,
        min_extremes=1,
    )

    assert result.approved is False
    assert "insufficient_samples" in result.blocked_reasons
    assert "no_extreme_funding" in result.blocked_reasons
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_funding_validator.py -q`

Expected: FAIL because `validation.funding` is missing.

- [ ] **Step 3: Implement funding validator**

Create `FundingExtremityResult` with strict Pydantic config and fields:

```python
strategy_family: str
symbol: str | None
venue: str | None
sample_count: int
extreme_count: int
positive_extreme_count: int
negative_extreme_count: int
mean_funding_rate: float
max_abs_funding_rate: float
threshold_abs: float
approved: bool
blocked_reasons: list[str]
```

Implement `validate_funding_extremes(db_path, *, symbol=None, venue=None, source=None, threshold_abs=0.0005, min_samples=10, min_extremes=2)`.

Behavior:

- Require `threshold_abs > 0`, `min_samples > 0`, `min_extremes > 0`.
- Load `funding_rate` records from `ResearchDataStore`, optionally filtering source.
- Validate payloads with `FundingRateRecord.model_validate`.
- Filter exact symbol and venue when provided.
- Count positive and negative extremes where `abs(funding_rate) >= threshold_abs`.
- Approve only when sample count and extreme count requirements pass.
- Block reasons: `insufficient_samples`, `no_extreme_funding`, `insufficient_extremes`.

- [ ] **Step 4: Run focused and bridge tests**

Run:

```bash
uv run pytest tests/test_funding_validator.py tests/test_scanner_bridge_low_capital.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/validation/funding.py tests/test_funding_validator.py
git commit -m "feat: validate funding rate extremes"
```

**Exit criteria:** Funding data can be summarized and blocked/approved based on repeatable historical extremes.

---

## Task 10: Walk-Forward Split Utility

**Files:**
- Create: `src/crypto_alpha_agent/validation/walk_forward.py`
- Test: `tests/test_walk_forward.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest

from crypto_alpha_agent.validation.walk_forward import generate_walk_forward_windows, split_sequence


def test_generate_walk_forward_windows_uses_exclusive_indexes():
    windows = generate_walk_forward_windows(total_bars=12, train_size=5, test_size=3, step_size=3)

    assert [window.model_dump() for window in windows] == [
        {
            "window_id": "wf-000",
            "train_start": 0,
            "train_end": 5,
            "test_start": 5,
            "test_end": 8,
        },
        {
            "window_id": "wf-001",
            "train_start": 3,
            "train_end": 8,
            "test_start": 8,
            "test_end": 11,
        },
    ]


def test_split_sequence_returns_train_test_slices():
    data = list(range(12))
    windows = generate_walk_forward_windows(total_bars=len(data), train_size=5, test_size=3, step_size=3)

    splits = split_sequence(data, windows)

    assert splits[0].train == [0, 1, 2, 3, 4]
    assert splits[0].test == [5, 6, 7]
    assert splits[1].train == [3, 4, 5, 6, 7]
    assert splits[1].test == [8, 9, 10]


@pytest.mark.parametrize("total_bars, train_size, test_size", [(7, 5, 3), (10, 0, 3), (10, 5, 0)])
def test_walk_forward_rejects_invalid_or_short_inputs(total_bars, train_size, test_size):
    with pytest.raises(ValueError):
        generate_walk_forward_windows(total_bars=total_bars, train_size=train_size, test_size=test_size)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_walk_forward.py -q`

Expected: FAIL because `validation.walk_forward` is missing.

- [ ] **Step 3: Implement utility**

Create strict Pydantic models:

```python
class WalkForwardWindow(BaseModel):
    window_id: str
    train_start: int
    train_end: int
    test_start: int
    test_end: int

class WalkForwardSplit(BaseModel):
    window: WalkForwardWindow
    train: list[Any]
    test: list[Any]
```

Implement:

```python
def generate_walk_forward_windows(total_bars: int, *, train_size: int, test_size: int, step_size: int | None = None) -> list[WalkForwardWindow]
def split_sequence(sequence: Sequence[Any], windows: Sequence[WalkForwardWindow]) -> list[WalkForwardSplit]
```

Behavior:

- Use exclusive end indexes.
- Default `step_size` to `test_size`.
- Require positive sizes and `total_bars >= train_size + test_size`.
- Generate windows while `test_end <= total_bars`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_walk_forward.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/validation/walk_forward.py tests/test_walk_forward.py
git commit -m "feat: add walk forward validation windows"
```

**Exit criteria:** Validation can be split into deterministic train/test windows.

---

## Task 11: Research Report Validation Summary

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_research_loop_validation_summary.py`

- [ ] **Step 1: Write failing tests**

```python
from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def test_research_loop_can_include_historical_validation_summary(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [_candle(index, close).to_source_record() for index, close in enumerate([100, 103, 106, 104, 108, 112, 109, 113])]
    )

    report = run_stored_research_loop(db_path, include_validation=True)

    assert len(report.validation_summaries) == 1
    summary = report.validation_summaries[0]
    assert summary.strategy_family == "close_momentum"
    assert summary.asset == "BTC/USDT"
    assert summary.timeframe == "1h"
    assert summary.trade_count >= 2
    assert summary.fee_adjusted_expectancy is not None


def test_research_loop_cli_markdown_includes_validation_section(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "report.md"
    ResearchDataStore(db_path).upsert_records(
        [_candle(index, close).to_source_record() for index, close in enumerate([100, 103, 106, 104, 108, 112, 109, 113])]
    )

    exit_code = main(["research-loop", "--db", str(db_path), "--include-validation", "--report-out", str(report_path)])

    payload = __import__("json").loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["report"]["validation_summaries"][0]["strategy_family"] == "close_momentum"
    text = report_path.read_text(encoding="utf-8")
    assert "## Historical Validation" in text
    assert "close_momentum" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_research_loop_validation_summary.py -q`

Expected: FAIL because `include_validation` and `validation_summaries` do not exist.

- [ ] **Step 3: Implement validation summaries**

Add `ValidationSummary` to `research_loop.py`:

```python
class ValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str
    asset: str
    timeframe: str
    status: Literal["passed", "blocked"]
    trade_count: int
    net_return: float | None = None
    max_drawdown: float | None = None
    fee_adjusted_expectancy: float | None = None
    slippage_adjusted_expectancy: float | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
```

Modify `ResearchLoopReport`:

```python
validation_summaries: list[ValidationSummary] = Field(default_factory=list)
```

Modify `run_stored_research_loop(..., include_validation: bool = False)`:

- When false, preserve existing behavior.
- When true, group loaded `market_candle` records by `(symbol, timeframe)`.
- For each group with at least two bars, load typed bars with `load_candle_history`.
- Run `validate_close_momentum` with conservative defaults.
- Convert result to `ValidationSummary`.
- Do not approve paper or live actions.

Modify CLI:

- Add `--include-validation` flag.
- Pass it into `run_stored_research_loop`.

Modify Markdown:

- Add `## Historical Validation`.
- If summaries are empty, say `No historical validation summaries generated.`
- Otherwise include a table with strategy, asset, timeframe, status, trade count, net return, max drawdown, fee-adjusted expectancy, and blocked reasons.

- [ ] **Step 4: Run focused and related tests**

Run:

```bash
uv run pytest tests/test_research_loop_validation_summary.py tests/test_research_loop_pipeline.py tests/test_cli_research_loop.py -q
```

Expected: PASS.

- [ ] **Step 5: Run full validation**

Run:

```bash
uv run pytest -q
uv run ruff check .
git diff --check
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crypto_alpha_agent/pipeline/research_loop.py src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/cli.py tests/test_research_loop_validation_summary.py
git commit -m "feat: include historical validation summaries"
```

**Exit criteria:** Research-loop reports can include conservative validation evidence from persisted historical candles.

---

## Phase 2 Completion Documentation

After Tasks 7-11 pass:

- Update `docs/roadmap.md` to mark Phase 2 partly complete.
- Note that validation still uses simple strategy families and is not sufficient for paper trading without later evidence gates.
- Run:

```bash
uv run pytest -q
uv run ruff check .
git diff --check
```

- Commit with:

```bash
git add docs/roadmap.md
git commit -m "docs: record historical validation progress"
```

## Definition Of Done

Phase 2 is complete when:

1. Persisted candles can be loaded as typed chronological bars.
2. A conservative momentum validator returns fee/slippage-adjusted metrics.
3. Funding-rate records can be summarized for extremity validation.
4. Walk-forward windows are available for future out-of-sample checks.
5. Research-loop reports can include historical validation summaries.
6. No code path submits orders, reads wallet keys, or touches real capital.
