# Derivatives-Conditioned Feasibility Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `strategy-feasibility` lab mode that tests multiple Binance USD-M derivatives-conditioned candidates before any strategy registration or paper simulation.

**Architecture:** Reuse the existing feasibility command and SQLite data store. Add a separate strict lab report model and local-only report builder in `strategy_feasibility.py`, then wire it through the existing CLI with Markdown/JSON artifacts. Keep ingestion, strategy registry, and paper simulation unchanged unless a later design proves a feasible candidate.

**Tech Stack:** Python 3.12, Pydantic v2 strict models, argparse CLI, SQLite via `ResearchDataStore`, pytest, ruff, existing Binance USD-M ingestion models.

---

## Scope Check

This plan implements one subsystem: a read-only derivatives-conditioned
feasibility lab. It does not register a strategy family, does not write paper
outcomes, does not add live execution, and does not add new public-data clients.

The plan assumes this spec has been reviewed:

`docs/superpowers/specs/2026-06-08-derivatives-conditioned-feasibility-lab-design.md`

## File Structure

- Modify: `src/crypto_alpha_agent/pipeline/strategy_feasibility.py`
  - Add the lab report models.
  - Add symbol normalization helpers.
  - Add local record alignment for market candles and Binance USD-M derivatives records.
  - Add four read-only candidate evaluators.
  - Add Markdown rendering for the lab report.
- Modify: `src/crypto_alpha_agent/cli.py`
  - Extend `strategy-feasibility --mode` choices.
  - Add lab-only parser arguments.
  - Dispatch mode-specific report builders and renderers.
- Modify: `tests/test_strategy_feasibility.py`
  - Add RED tests for lab models, missing derivatives, blocked diagnostics, positive candidate behavior, duplicate timestamps, and CLI output.
  - Add deterministic fixture helpers for derivatives records.
- Modify: `docs/goals/project-completion-state.md`
  - Record the implementation result, real local feasibility result, verification, and remaining blocker or next gate.
- Modify: `docs/roadmap.md`
  - Update the active profit-evidence line with the lab result.
- Create: `docs/goals/phase-reports/2026-06-08-derivatives-conditioned-feasibility-lab-report.md`
  - Summarize search evidence, local feasibility, files changed, verification, and next decision.
- Modify: `docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md`
  - Check off steps as execution proceeds and append the actual lab result.

## Task 1: Add RED Tests For Lab Report Behavior

**Files:**
- Modify: `tests/test_strategy_feasibility.py`

- [x] **Step 1: Add derivatives model imports for test fixtures**

At the existing import line:

```python
from crypto_alpha_agent.data.models import MarketCandle, SourceRecord
```

change it to:

```python
from crypto_alpha_agent.data.models import (
    BasisRecord,
    LongShortRatioRecord,
    MarketCandle,
    PremiumIndexKlineRecord,
    SourceRecord,
    TakerBuySellVolumeRecord,
)
```

- [x] **Step 2: Add RED test for missing derivatives history**

Append this test after
`test_large_liquid_momentum_feasibility_keeps_metrics_when_expectancy_blocks`:

```python
def test_derivatives_conditioned_lab_blocks_missing_derivatives_history(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=120)

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.command == "strategy-feasibility"
    assert report.mode == "derivatives-conditioned-lab"
    assert report.readiness == "blocked"
    assert "insufficient_derivatives_history" in report.reason_codes
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert len(report.candidate_metrics) == 1
    metric = report.candidate_metrics[0]
    assert metric.candidate == "long_short_crowding_contrarian"
    assert metric.readiness == "blocked"
    assert "insufficient_derivatives_history" in metric.reason_codes
    assert metric.split_metrics == []
```

- [x] **Step 3: Run the missing-history RED test**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py::test_derivatives_conditioned_lab_blocks_missing_derivatives_history -q
```

Expected: FAIL with an import error for
`build_derivatives_conditioned_lab_report`.

- [x] **Step 4: Add RED test that blocked candidates preserve metrics**

Append this test after the missing-history test:

```python
def test_derivatives_conditioned_lab_keeps_metrics_when_expectancy_blocks(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_flat_market_candles(db_path, count=160)
    _seed_derivatives_context(db_path, count=160)

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.readiness == "blocked"
    assert "non_positive_cost_adjusted_expectancy" in report.reason_codes
    assert len(report.candidate_metrics) == 1
    metric = report.candidate_metrics[0]
    assert metric.readiness == "blocked"
    assert "non_positive_cost_adjusted_expectancy" in metric.reason_codes
    assert len(metric.split_metrics) >= 3
    assert all(split.cost_adjusted_return_mean <= 0 for split in metric.split_metrics)
```

- [x] **Step 5: Run the blocked-metrics RED test**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py::test_derivatives_conditioned_lab_keeps_metrics_when_expectancy_blocks -q
```

Expected: FAIL with an import error for
`build_derivatives_conditioned_lab_report`.

- [x] **Step 6: Add RED test for one passing candidate and one rejected candidate**

Append this test after the blocked-metrics test:

```python
def test_derivatives_conditioned_lab_reports_passing_and_rejected_candidates(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.65,
            "ETHUSDT": 1.35,
            "SOLUSDT": 1.25,
        },
        taker_ratios={
            "BTCUSDT": 1.35,
            "ETHUSDT": 1.30,
            "SOLUSDT": 1.25,
        },
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=[
            "long_short_crowding_contrarian",
            "taker_imbalance_reversal",
        ],
        min_split_count=3,
    )

    by_candidate = {metric.candidate: metric for metric in report.candidate_metrics}
    assert report.readiness == "feasible"
    assert report.reason_codes == []
    assert by_candidate["long_short_crowding_contrarian"].readiness == "feasible"
    assert all(
        split.cost_adjusted_return_mean > 0
        for split in by_candidate["long_short_crowding_contrarian"].split_metrics
    )
    assert by_candidate["taker_imbalance_reversal"].readiness == "blocked"
    assert "non_positive_cost_adjusted_expectancy" in by_candidate[
        "taker_imbalance_reversal"
    ].reason_codes
```

- [x] **Step 7: Run the mixed-candidate RED test**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py::test_derivatives_conditioned_lab_reports_passing_and_rejected_candidates -q
```

Expected: FAIL with an import error for
`build_derivatives_conditioned_lab_report`.

- [x] **Step 8: Add RED CLI test for lab Markdown and JSON output**

Append this test after `test_strategy_feasibility_cli_writes_markdown_and_json`:

```python
def test_strategy_feasibility_cli_writes_derivatives_lab_markdown_and_json(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "derivatives-lab.md"
    json_out = tmp_path / "derivatives-lab.json"
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.65,
            "ETHUSDT": 1.35,
            "SOLUSDT": 1.25,
        },
    )

    exit_code = main(
        [
            "strategy-feasibility",
            "--db",
            str(db_path),
            "--mode",
            "derivatives-conditioned-lab",
            "--symbol",
            "BTC/USDT",
            "--symbol",
            "ETH/USDT",
            "--symbol",
            "SOL/USDT",
            "--timeframe",
            "1h",
            "--derivatives-period",
            "1h",
            "--candidate",
            "long_short_crowding_contrarian",
            "--out",
            str(out_path),
            "--json-out",
            str(json_out),
            "--current-capital-usd",
            "300",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = out_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["command"] == "strategy-feasibility"
    assert payload["report"]["mode"] == "derivatives-conditioned-lab"
    assert payload["report"]["uses_real_capital"] is False
    assert payload["report"]["live_order_routing"] is False
    assert json_payload["report"]["candidate_metrics"][0]["candidate"] == "long_short_crowding_contrarian"
    assert "Derivatives-Conditioned Feasibility Lab" in markdown
    assert "long_short_crowding_contrarian" in markdown
```

- [x] **Step 9: Run the CLI RED test**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py::test_strategy_feasibility_cli_writes_derivatives_lab_markdown_and_json -q
```

Expected: FAIL because argparse rejects
`derivatives-conditioned-lab` as an invalid `--mode` choice.

- [x] **Step 10: Add deterministic derivatives fixture helpers**

Append these helpers before `_record_ids`:

```python
def _seed_directional_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                close = 100.0 + index * 0.5
            elif symbol == "ETH/USDT":
                close = 200.0 - index * 0.1
            else:
                close = 50.0 - index * 0.05
            records.append(_candle(symbol, index, close=close).to_source_record())
    ResearchDataStore(db_path).upsert_records(records)


def _seed_derivatives_context(
    db_path,
    *,
    count: int,
    long_short_ratios: dict[str, float] | None = None,
    taker_ratios: dict[str, float] | None = None,
    premium_values: dict[str, float] | None = None,
    basis_rates: dict[str, float] | None = None,
) -> None:
    long_short_ratios = long_short_ratios or {
        "BTCUSDT": 1.0,
        "ETHUSDT": 1.0,
        "SOLUSDT": 1.0,
    }
    taker_ratios = taker_ratios or {
        "BTCUSDT": 1.0,
        "ETHUSDT": 1.0,
        "SOLUSDT": 1.0,
    }
    premium_values = premium_values or {
        "BTCUSDT": 0.0,
        "ETHUSDT": 0.0,
        "SOLUSDT": 0.0,
    }
    basis_rates = basis_rates or {
        "BTCUSDT": 0.0,
        "ETHUSDT": 0.0,
        "SOLUSDT": 0.0,
    }
    records = []
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for index in range(count):
            timestamp = START + timedelta(hours=index)
            long_short_ratio = long_short_ratios[symbol]
            long_account = long_short_ratio / (1.0 + long_short_ratio)
            short_account = 1.0 - long_account
            taker_ratio = taker_ratios[symbol]
            records.extend(
                [
                    LongShortRatioRecord(
                        source="binance_usdm",
                        venue="binance",
                        symbol=symbol,
                        period="1h",
                        timestamp=timestamp,
                        long_short_ratio=long_short_ratio,
                        long_account=long_account,
                        short_account=short_account,
                        raw={"fixture": "long_short"},
                    ).to_source_record(),
                    TakerBuySellVolumeRecord(
                        source="binance_usdm",
                        venue="binance",
                        symbol=symbol,
                        period="1h",
                        timestamp=timestamp,
                        buy_sell_ratio=taker_ratio,
                        buy_volume=100.0 * taker_ratio,
                        sell_volume=100.0,
                        raw={"fixture": "taker"},
                    ).to_source_record(),
                    PremiumIndexKlineRecord(
                        source="binance_usdm",
                        venue="binance",
                        symbol=symbol,
                        timestamp=timestamp,
                        interval="1h",
                        open=premium_values[symbol],
                        high=premium_values[symbol],
                        low=premium_values[symbol],
                        close=premium_values[symbol],
                        raw={"fixture": "premium"},
                    ).to_source_record(),
                    BasisRecord(
                        source="binance_usdm",
                        venue="binance",
                        pair=symbol,
                        contract_type="PERPETUAL",
                        period="1h",
                        timestamp=timestamp,
                        index_price=100.0,
                        futures_price=100.0 * (1.0 + basis_rates[symbol]),
                        basis=100.0 * basis_rates[symbol],
                        basis_rate=basis_rates[symbol],
                        annualized_basis_rate=None,
                        raw={"fixture": "basis"},
                    ).to_source_record(),
                ]
            )
    ResearchDataStore(db_path).upsert_records(records)
```

- [x] **Step 11: Run the new test file after helpers are added**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py -q
```

Expected: FAIL. Existing large-liquid tests still pass; new lab tests fail
because the lab builder and CLI mode do not exist.

- [x] **Step 12: Commit RED tests**

Run:

```bash
git add tests/test_strategy_feasibility.py
git commit -m "test: specify derivatives feasibility lab"
```

Expected: commit succeeds with failing tests intentionally captured for the
implementation step.

## Task 2: Add Lab Models, Symbol Mapping, And Candidate Evaluation

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/strategy_feasibility.py`
- Test: `tests/test_strategy_feasibility.py`

- [x] **Step 1: Extend feasibility mode and add candidate literals**

In `strategy_feasibility.py`, replace:

```python
StrategyFeasibilityMode = Literal["large-liquid-momentum-regime"]
```

with:

```python
StrategyFeasibilityMode = Literal[
    "large-liquid-momentum-regime",
    "derivatives-conditioned-lab",
]
DerivativesLabCandidate = Literal[
    "long_short_crowding_contrarian",
    "taker_imbalance_reversal",
    "premium_basis_risk_filter",
    "momentum_derivatives_confirmation",
]
_ALL_DERIVATIVES_LAB_CANDIDATES: tuple[DerivativesLabCandidate, ...] = (
    "long_short_crowding_contrarian",
    "taker_imbalance_reversal",
    "premium_basis_risk_filter",
    "momentum_derivatives_confirmation",
)
```

- [x] **Step 2: Add strict lab report models**

After `StrategyFeasibilityReport`, add:

```python
class DerivativesCoverage(_StrictFeasibilityModel):
    symbol: str
    derivatives_symbol: str
    market_records: int = Field(ge=0)
    premium_index_kline_records: int = Field(ge=0)
    basis_records: int = Field(ge=0)
    long_short_account_ratio_records: int = Field(ge=0)
    taker_buy_sell_volume_records: int = Field(ge=0)
    aligned_records: int = Field(ge=0)
    duplicate_timestamps: int = Field(ge=0)
    blocked_reasons: list[str] = Field(default_factory=list)


class DerivativesCandidateMetric(_StrictFeasibilityModel):
    candidate: DerivativesLabCandidate
    readiness: StrategyFeasibilityReadiness
    reason_codes: list[str] = Field(default_factory=list)
    observations: int = Field(ge=0)
    selected_symbol_counts: dict[str, int] = Field(default_factory=dict)
    gross_return_mean: float | None = None
    cost_adjusted_return_mean: float | None = None
    win_rate: float | None = Field(default=None, ge=0, le=1)
    split_metrics: list[WalkForwardSplitMetric] = Field(default_factory=list)


class DerivativesConditionedLabReport(_StrictFeasibilityModel):
    command: Literal["strategy-feasibility"] = "strategy-feasibility"
    mode: Literal["derivatives-conditioned-lab"] = "derivatives-conditioned-lab"
    generated_at: datetime
    timeframe: str
    derivatives_period: str
    symbols: list[str]
    derivatives_symbols: dict[str, str]
    current_capital_usd: float = Field(ge=0)
    readiness: StrategyFeasibilityReadiness
    reason_codes: list[str] = Field(default_factory=list)
    coverage: list[DerivativesCoverage]
    candidate_metrics: list[DerivativesCandidateMetric]
    derivatives_record_counts: dict[str, int]
    cost_bps: float = Field(ge=0)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False
```

- [x] **Step 3: Add internal derivatives row and signal dataclasses**

After `_Observation`, add:

```python
@dataclass(frozen=True)
class _DerivativesRow:
    symbol: str
    derivatives_symbol: str
    timestamp: datetime
    long_short_ratio: float | None = None
    taker_buy_sell_ratio: float | None = None
    premium_close: float | None = None
    basis_rate: float | None = None


@dataclass(frozen=True)
class _CandidateSignal:
    symbol: str
    score: float
```

- [x] **Step 4: Add public symbol normalization helper**

Before `build_large_liquid_momentum_feasibility_report`, add:

```python
def normalize_binance_usdm_symbol(symbol: str) -> str:
    base = symbol.strip().upper()
    if ":" in base:
        base = base.split(":", maxsplit=1)[0]
    return base.replace("/", "")
```

- [x] **Step 5: Add the lab report builder**

After `build_large_liquid_momentum_feasibility_report`, add:

```python
def build_derivatives_conditioned_lab_report(
    db_path: str | Path,
    *,
    symbols: list[str],
    timeframe: str,
    current_capital_usd: float,
    derivatives_symbols: dict[str, str] | None = None,
    derivatives_period: str = "1h",
    candidates: list[DerivativesLabCandidate] | None = None,
    cost_bps: float = 10.0,
    min_split_count: int = 3,
) -> DerivativesConditionedLabReport:
    normalized_symbols = _dedupe_preserving_order(symbols)
    selected_candidates = _normalize_lab_candidates(candidates)
    symbol_map = {
        symbol: (derivatives_symbols or {}).get(symbol, normalize_binance_usdm_symbol(symbol))
        for symbol in normalized_symbols
    }
    records = ResearchDataStore(db_path).load_records()
    market_by_symbol = _market_rows_by_symbol(records, normalized_symbols, timeframe)
    derivatives_by_symbol = _derivatives_rows_by_symbol(
        records,
        symbols=normalized_symbols,
        symbol_map=symbol_map,
        derivatives_period=derivatives_period,
    )
    derivative_counts = _derivative_record_counts(records)
    coverage, duplicate_blocked = _derivatives_coverage(
        market_by_symbol,
        derivatives_by_symbol,
        normalized_symbols,
        symbol_map,
    )
    lab_reason_codes: list[str] = []
    if duplicate_blocked:
        lab_reason_codes.append("duplicate_timestamps")

    candidate_metrics = [
        _evaluate_derivatives_candidate(
            candidate,
            market_by_symbol=market_by_symbol,
            derivatives_by_symbol=derivatives_by_symbol,
            symbols=normalized_symbols,
            cost_bps=cost_bps,
            min_split_count=min_split_count,
        )
        for candidate in selected_candidates
    ]
    feasible_candidates = [
        metric for metric in candidate_metrics if metric.readiness == "feasible"
    ]
    if not feasible_candidates:
        for metric in candidate_metrics:
            lab_reason_codes.extend(metric.reason_codes)
    if duplicate_blocked:
        candidate_metrics = [
            metric.model_copy(
                update={
                    "readiness": "blocked",
                    "reason_codes": _dedupe_preserving_order(
                        [*metric.reason_codes, "duplicate_timestamps"]
                    ),
                }
            )
            for metric in candidate_metrics
        ]
        feasible_candidates = []

    lab_reason_codes = [] if feasible_candidates else _dedupe_preserving_order(lab_reason_codes)
    return DerivativesConditionedLabReport(
        generated_at=datetime.now(tz=UTC),
        timeframe=timeframe,
        derivatives_period=derivatives_period,
        symbols=normalized_symbols,
        derivatives_symbols=symbol_map,
        current_capital_usd=current_capital_usd,
        readiness="feasible" if feasible_candidates else "blocked",
        reason_codes=lab_reason_codes,
        coverage=coverage,
        candidate_metrics=candidate_metrics,
        derivatives_record_counts=derivative_counts,
        cost_bps=cost_bps,
        uses_real_capital=False,
        live_order_routing=False,
    )
```

- [x] **Step 6: Add candidate normalization**

After `_dedupe_preserving_order`, add:

```python
def _normalize_lab_candidates(
    candidates: list[DerivativesLabCandidate] | None,
) -> list[DerivativesLabCandidate]:
    if not candidates:
        return list(_ALL_DERIVATIVES_LAB_CANDIDATES)
    return _dedupe_preserving_order(candidates)
```

- [x] **Step 7: Add derivatives row loading**

Before `_derivative_record_counts`, add:

```python
def _derivatives_rows_by_symbol(
    records: list[SourceRecord],
    *,
    symbols: list[str],
    symbol_map: dict[str, str],
    derivatives_period: str,
) -> dict[str, dict[datetime, _DerivativesRow]]:
    requested = {symbol_map[symbol]: symbol for symbol in symbols}
    rows: dict[str, dict[datetime, _DerivativesRow]] = {
        symbol: {} for symbol in symbols
    }
    partial: dict[tuple[str, datetime], dict[str, float]] = defaultdict(dict)
    for record in records:
        payload = record.payload
        record_type = record.record_type
        if record_type == "long_short_account_ratio":
            derivatives_symbol = str(payload.get("symbol") or "")
            source_symbol = requested.get(derivatives_symbol)
            if source_symbol is None or payload.get("period") != derivatives_period:
                continue
            partial[(source_symbol, record.observed_at)]["long_short_ratio"] = float(
                payload["long_short_ratio"]
            )
        elif record_type == "taker_buy_sell_volume":
            derivatives_symbol = str(payload.get("symbol") or "")
            source_symbol = requested.get(derivatives_symbol)
            if source_symbol is None or payload.get("period") != derivatives_period:
                continue
            partial[(source_symbol, record.observed_at)]["taker_buy_sell_ratio"] = float(
                payload["buy_sell_ratio"]
            )
        elif record_type == "premium_index_kline":
            derivatives_symbol = str(payload.get("symbol") or "")
            source_symbol = requested.get(derivatives_symbol)
            if source_symbol is None or payload.get("interval") != derivatives_period:
                continue
            partial[(source_symbol, record.observed_at)]["premium_close"] = float(
                payload["close"]
            )
        elif record_type == "basis":
            derivatives_symbol = str(payload.get("pair") or "")
            source_symbol = requested.get(derivatives_symbol)
            if source_symbol is None or payload.get("period") != derivatives_period:
                continue
            partial[(source_symbol, record.observed_at)]["basis_rate"] = float(
                payload["basis_rate"]
            )

    for (symbol, timestamp), values in partial.items():
        rows[symbol][timestamp] = _DerivativesRow(
            symbol=symbol,
            derivatives_symbol=symbol_map[symbol],
            timestamp=timestamp,
            long_short_ratio=values.get("long_short_ratio"),
            taker_buy_sell_ratio=values.get("taker_buy_sell_ratio"),
            premium_close=values.get("premium_close"),
            basis_rate=values.get("basis_rate"),
        )
    return rows
```

- [x] **Step 8: Add coverage computation**

Before `_derivative_record_counts`, add:

```python
def _derivatives_coverage(
    market_by_symbol: dict[str, list[_MarketRow]],
    derivatives_by_symbol: dict[str, dict[datetime, _DerivativesRow]],
    symbols: list[str],
    symbol_map: dict[str, str],
) -> tuple[list[DerivativesCoverage], bool]:
    coverage = []
    duplicate_blocked = False
    for symbol in symbols:
        market_rows = market_by_symbol.get(symbol, [])
        timestamp_counts = Counter(row.timestamp for row in market_rows)
        duplicate_timestamps = sum(count - 1 for count in timestamp_counts.values() if count > 1)
        if duplicate_timestamps:
            duplicate_blocked = True
        derivative_rows = derivatives_by_symbol.get(symbol, {})
        blocked_reasons = []
        if not market_rows:
            blocked_reasons.append("missing_market_candles")
        if not derivative_rows:
            blocked_reasons.append("insufficient_derivatives_history")
        if duplicate_timestamps:
            blocked_reasons.append("duplicate_timestamps")
        aligned = set(row.timestamp for row in market_rows) & set(derivative_rows)
        premium_count = sum(1 for row in derivative_rows.values() if row.premium_close is not None)
        basis_count = sum(1 for row in derivative_rows.values() if row.basis_rate is not None)
        long_short_count = sum(1 for row in derivative_rows.values() if row.long_short_ratio is not None)
        taker_count = sum(1 for row in derivative_rows.values() if row.taker_buy_sell_ratio is not None)
        coverage.append(
            DerivativesCoverage(
                symbol=symbol,
                derivatives_symbol=symbol_map[symbol],
                market_records=len(market_rows),
                premium_index_kline_records=premium_count,
                basis_records=basis_count,
                long_short_account_ratio_records=long_short_count,
                taker_buy_sell_volume_records=taker_count,
                aligned_records=len(aligned),
                duplicate_timestamps=duplicate_timestamps,
                blocked_reasons=blocked_reasons,
            )
        )
    return coverage, duplicate_blocked
```

- [x] **Step 9: Add candidate evaluation**

Before `_derivative_record_counts`, add:

```python
def _evaluate_derivatives_candidate(
    candidate: DerivativesLabCandidate,
    *,
    market_by_symbol: dict[str, list[_MarketRow]],
    derivatives_by_symbol: dict[str, dict[datetime, _DerivativesRow]],
    symbols: list[str],
    cost_bps: float,
    min_split_count: int,
) -> DerivativesCandidateMetric:
    observations = _derivatives_candidate_observations(
        candidate,
        market_by_symbol=market_by_symbol,
        derivatives_by_symbol=derivatives_by_symbol,
        symbols=symbols,
        cost_bps=cost_bps,
    )
    reason_codes: list[str] = []
    if not observations:
        reason_codes.append("insufficient_derivatives_history")
        return DerivativesCandidateMetric(
            candidate=candidate,
            readiness="blocked",
            reason_codes=reason_codes,
            observations=0,
            selected_symbol_counts={},
            split_metrics=[],
        )
    if len(observations) < min_split_count * 2:
        reason_codes.append("insufficient_walk_forward_splits")
    split_metrics = _walk_forward_metrics(observations, split_count=min_split_count)
    if len(split_metrics) < min_split_count:
        reason_codes.append("insufficient_walk_forward_splits")
    elif any(metric.cost_adjusted_return_mean <= 0 for metric in split_metrics):
        reason_codes.append("non_positive_cost_adjusted_expectancy")
    cost_adjusted = [row.cost_adjusted_return for row in observations]
    gross = [row.gross_return for row in observations]
    selected_counts = dict(Counter(row.selected_symbol for row in observations))
    return DerivativesCandidateMetric(
        candidate=candidate,
        readiness="blocked" if reason_codes else "feasible",
        reason_codes=_dedupe_preserving_order(reason_codes),
        observations=len(observations),
        selected_symbol_counts=selected_counts,
        gross_return_mean=sum(gross) / len(gross),
        cost_adjusted_return_mean=sum(cost_adjusted) / len(cost_adjusted),
        win_rate=sum(1 for value in cost_adjusted if value > 0) / len(cost_adjusted),
        split_metrics=split_metrics,
    )
```

- [x] **Step 10: Add observation construction and signal formulas**

Before `_derivative_record_counts`, add:

```python
def _derivatives_candidate_observations(
    candidate: DerivativesLabCandidate,
    *,
    market_by_symbol: dict[str, list[_MarketRow]],
    derivatives_by_symbol: dict[str, dict[datetime, _DerivativesRow]],
    symbols: list[str],
    cost_bps: float,
) -> list[_Observation]:
    by_symbol_time = {
        symbol: {row.timestamp: row for row in market_by_symbol.get(symbol, [])}
        for symbol in symbols
    }
    aligned_timestamps = _aligned_timestamps(market_by_symbol, symbols)
    observations: list[_Observation] = []
    round_trip_cost = cost_bps / 10_000
    for index in range(24, len(aligned_timestamps) - 1):
        timestamp = aligned_timestamps[index]
        next_timestamp = aligned_timestamps[index + 1]
        signals = [
            signal
            for symbol in symbols
            if (
                signal := _candidate_signal(
                    candidate,
                    symbol=symbol,
                    timestamp=timestamp,
                    index=index,
                    aligned_timestamps=aligned_timestamps,
                    market_rows=by_symbol_time[symbol],
                    derivative_rows=derivatives_by_symbol.get(symbol, {}),
                )
            )
            is not None
        ]
        if not signals:
            continue
        selected = max(signals, key=lambda item: abs(item.score))
        if selected.score == 0:
            continue
        direction = 1.0 if selected.score > 0 else -1.0
        selected_row = by_symbol_time[selected.symbol][timestamp]
        next_row = by_symbol_time[selected.symbol][next_timestamp]
        gross_return = direction * (next_row.close / selected_row.close - 1)
        observations.append(
            _Observation(
                timestamp=timestamp,
                selected_symbol=selected.symbol,
                gross_return=gross_return,
                cost_adjusted_return=gross_return - round_trip_cost,
            )
        )
    return observations


def _candidate_signal(
    candidate: DerivativesLabCandidate,
    *,
    symbol: str,
    timestamp: datetime,
    index: int,
    aligned_timestamps: list[datetime],
    market_rows: dict[datetime, _MarketRow],
    derivative_rows: dict[datetime, _DerivativesRow],
) -> _CandidateSignal | None:
    derivative = derivative_rows.get(timestamp)
    if derivative is None:
        return None
    if candidate == "long_short_crowding_contrarian":
        if derivative.long_short_ratio is None:
            return None
        return _CandidateSignal(symbol=symbol, score=1.0 - derivative.long_short_ratio)
    if candidate == "taker_imbalance_reversal":
        if derivative.taker_buy_sell_ratio is None:
            return None
        return _CandidateSignal(symbol=symbol, score=1.0 - derivative.taker_buy_sell_ratio)
    if candidate == "premium_basis_risk_filter":
        if derivative.premium_close is None or derivative.basis_rate is None:
            return None
        if abs(derivative.premium_close) > 0.001 or abs(derivative.basis_rate) > 0.002:
            return _CandidateSignal(symbol=symbol, score=0.0)
        previous = market_rows[aligned_timestamps[index - 24]]
        current = market_rows[timestamp]
        return _CandidateSignal(symbol=symbol, score=current.close / previous.close - 1)
    if derivative.taker_buy_sell_ratio is None or derivative.long_short_ratio is None:
        return None
    previous = market_rows[aligned_timestamps[index - 24]]
    current = market_rows[timestamp]
    momentum = current.close / previous.close - 1
    taker_confirmation = derivative.taker_buy_sell_ratio - 1.0
    if momentum == 0 or momentum * taker_confirmation <= 0:
        return _CandidateSignal(symbol=symbol, score=0.0)
    if abs(derivative.long_short_ratio - 1.0) > 0.75:
        return _CandidateSignal(symbol=symbol, score=0.0)
    return _CandidateSignal(symbol=symbol, score=momentum)
```

- [x] **Step 11: Run focused tests after model implementation**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py::test_derivatives_conditioned_lab_blocks_missing_derivatives_history tests/test_strategy_feasibility.py::test_derivatives_conditioned_lab_keeps_metrics_when_expectancy_blocks tests/test_strategy_feasibility.py::test_derivatives_conditioned_lab_reports_passing_and_rejected_candidates -q
```

Expected: PASS for the three model-level lab tests. CLI test still fails until
Task 3.

- [x] **Step 12: Run ruff on touched implementation files**

Run:

```bash
uv run --extra dev ruff check src/crypto_alpha_agent/pipeline/strategy_feasibility.py tests/test_strategy_feasibility.py
```

Expected: `All checks passed!`

- [x] **Step 13: Commit model implementation**

Run:

```bash
git add src/crypto_alpha_agent/pipeline/strategy_feasibility.py tests/test_strategy_feasibility.py
git commit -m "feat: add derivatives feasibility lab model"
```

Expected: commit succeeds.

## Task 3: Add Markdown Rendering And CLI Wiring

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/strategy_feasibility.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_strategy_feasibility.py`

- [x] **Step 1: Add lab Markdown renderer**

In `strategy_feasibility.py`, add this function after
`render_strategy_feasibility_markdown`:

```python
def render_derivatives_conditioned_lab_markdown(
    report: DerivativesConditionedLabReport,
) -> str:
    lines = [
        "# Derivatives-Conditioned Feasibility Lab",
        "",
        "## Safety",
        f"Real capital: {str(report.uses_real_capital).lower()}",
        f"Live order routing: {str(report.live_order_routing).lower()}",
        "",
        "## Decision",
        f"Readiness: {report.readiness}",
        f"Reason codes: {', '.join(report.reason_codes) or 'none'}",
        "",
        "## Coverage",
        "| Symbol | Derivatives symbol | Market | Premium | Basis | Long/short | Taker buy/sell | Aligned | Blocked reasons |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.coverage:
        lines.append(
            "| "
            + " | ".join(
                [
                    item.symbol,
                    item.derivatives_symbol,
                    f"{item.market_records:g}",
                    f"{item.premium_index_kline_records:g}",
                    f"{item.basis_records:g}",
                    f"{item.long_short_account_ratio_records:g}",
                    f"{item.taker_buy_sell_volume_records:g}",
                    f"{item.aligned_records:g}",
                    ", ".join(item.blocked_reasons) or "none",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Candidates",
            "| Candidate | Readiness | Observations | Net mean | Win rate | Reasons |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for metric in report.candidate_metrics:
        net_mean = (
            "n/a"
            if metric.cost_adjusted_return_mean is None
            else f"{metric.cost_adjusted_return_mean:.8f}"
        )
        win_rate = "n/a" if metric.win_rate is None else f"{metric.win_rate:.4f}"
        lines.append(
            "| "
            + " | ".join(
                [
                    metric.candidate,
                    metric.readiness,
                    f"{metric.observations:g}",
                    net_mean,
                    win_rate,
                    ", ".join(metric.reason_codes) or "none",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Walk Forward",
            "| Candidate | Split | Train observations | Test observations | Test start | Test end | Net mean | Win rate |",
            "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |",
        ]
    )
    for metric in report.candidate_metrics:
        if not metric.split_metrics:
            lines.append(f"| {metric.candidate} | 0 | 0 | 0 | n/a | n/a | 0 | 0 |")
            continue
        for split in metric.split_metrics:
            lines.append(
                "| "
                + " | ".join(
                    [
                        metric.candidate,
                        f"{split.split_index:g}",
                        f"{split.train_observations:g}",
                        f"{split.test_observations:g}",
                        split.test_start.isoformat(),
                        split.test_end.isoformat(),
                        f"{split.cost_adjusted_return_mean:.8f}",
                        f"{split.win_rate:.4f}",
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"
```

- [x] **Step 2: Update CLI imports**

In `src/crypto_alpha_agent/cli.py`, replace:

```python
from crypto_alpha_agent.pipeline.strategy_feasibility import (
    build_large_liquid_momentum_feasibility_report,
    render_strategy_feasibility_markdown,
)
```

with:

```python
from crypto_alpha_agent.pipeline.strategy_feasibility import (
    build_derivatives_conditioned_lab_report,
    build_large_liquid_momentum_feasibility_report,
    render_derivatives_conditioned_lab_markdown,
    render_strategy_feasibility_markdown,
)
```

- [x] **Step 3: Extend `strategy-feasibility` parser choices and arguments**

In `build_parser`, replace the mode parser block:

```python
    strategy_feasibility_parser.add_argument(
        "--mode",
        required=True,
        choices=("large-liquid-momentum-regime",),
        help="Feasibility mode to evaluate.",
    )
```

with:

```python
    strategy_feasibility_parser.add_argument(
        "--mode",
        required=True,
        choices=("large-liquid-momentum-regime", "derivatives-conditioned-lab"),
        help="Feasibility mode to evaluate.",
    )
```

Then add these arguments after `--current-capital-usd`:

```python
    strategy_feasibility_parser.add_argument(
        "--derivatives-symbol",
        action="append",
        default=[],
        help="Optional SYMBOL=BINANCEUSDM mapping for derivatives lab mode. Repeat for multiple symbols.",
    )
    strategy_feasibility_parser.add_argument(
        "--derivatives-period",
        default="1h",
        help="Binance USD-M derivatives period or interval for lab mode.",
    )
    strategy_feasibility_parser.add_argument(
        "--candidate",
        action="append",
        choices=(
            "long_short_crowding_contrarian",
            "taker_imbalance_reversal",
            "premium_basis_risk_filter",
            "momentum_derivatives_confirmation",
        ),
        default=[],
        help="Derivatives lab candidate to evaluate. Repeat for multiple candidates.",
    )
    strategy_feasibility_parser.add_argument(
        "--min-split-count",
        type=_positive_int,
        default=3,
        help="Minimum walk-forward split count for feasibility mode.",
    )
    strategy_feasibility_parser.add_argument(
        "--cost-bps",
        type=_non_negative_finite_float,
        default=10.0,
        help="Round-trip cost assumption in basis points.",
    )
```

- [x] **Step 4: Add mapping parser helper**

Before `_handle_strategy_feasibility`, add:

```python
def _parse_derivatives_symbol_map(values: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--derivatives-symbol values must use SYMBOL=DERIVATIVES_SYMBOL")
        symbol, derivatives_symbol = value.split("=", maxsplit=1)
        symbol = symbol.strip()
        derivatives_symbol = derivatives_symbol.strip()
        if not symbol or not derivatives_symbol:
            raise ValueError("--derivatives-symbol values cannot contain blank sides")
        mapping[symbol] = derivatives_symbol
    return mapping
```

- [x] **Step 5: Dispatch the lab mode in `_handle_strategy_feasibility`**

Replace `_handle_strategy_feasibility` with:

```python
def _handle_strategy_feasibility(args: argparse.Namespace) -> dict[str, Any]:
    if args.mode == "derivatives-conditioned-lab":
        try:
            derivatives_symbols = _parse_derivatives_symbol_map(args.derivatives_symbol)
        except ValueError as exc:
            args.parser.error(str(exc))
            raise AssertionError("argparse parser.error should exit") from exc
        report = build_derivatives_conditioned_lab_report(
            args.db,
            symbols=args.symbol,
            timeframe=args.timeframe,
            current_capital_usd=args.current_capital_usd,
            derivatives_symbols=derivatives_symbols or None,
            derivatives_period=args.derivatives_period,
            candidates=args.candidate or None,
            cost_bps=args.cost_bps,
            min_split_count=args.min_split_count,
        )
        markdown = render_derivatives_conditioned_lab_markdown(report)
    else:
        report = build_large_liquid_momentum_feasibility_report(
            args.db,
            symbols=args.symbol,
            timeframe=args.timeframe,
            current_capital_usd=args.current_capital_usd,
            cost_bps=args.cost_bps,
            min_split_count=args.min_split_count,
        )
        markdown = render_strategy_feasibility_markdown(report)
    payload = {
        "command": "strategy-feasibility",
        "out": str(args.out),
        "json_out": str(args.json_out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    write_text_artifact(args.out, markdown)
    write_json_artifact(args.json_out, payload)
    return payload
```

- [x] **Step 6: Run CLI and full strategy feasibility tests**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py -q
```

Expected: all tests in `tests/test_strategy_feasibility.py` pass.

- [x] **Step 7: Run parser documentation contract tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: all documentation contract tests pass.

- [x] **Step 8: Run ruff on CLI and feasibility files**

Run:

```bash
uv run --extra dev ruff check src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/pipeline/strategy_feasibility.py tests/test_strategy_feasibility.py
```

Expected: `All checks passed!`

- [x] **Step 9: Commit CLI implementation**

Run:

```bash
git add src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/pipeline/strategy_feasibility.py tests/test_strategy_feasibility.py
git commit -m "feat: wire derivatives feasibility lab cli"
```

Expected: commit succeeds.

## Task 4: Collect Recent Derivatives Context And Run The Lab

**Files:**
- Runtime artifacts only under `var/`
- Modify later docs in Task 5 after results are known

- [x] **Step 1: Confirm current local data coverage**

Run:

```bash
sqlite3 var/research.sqlite "select record_type, json_extract(payload_json,'$.symbol') as symbol, json_extract(payload_json,'$.pair') as pair, count(*) as n, min(observed_at), max(observed_at) from source_records where record_type in ('market_candle','basis','long_short_account_ratio','premium_index_kline','taker_buy_sell_volume') group by record_type, symbol, pair order by record_type, symbol, pair;"
```

Expected: market candles show BTC/USDT, ETH/USDT, and SOL/USDT with 1000 rows
each. Existing Binance USD-M derivatives rows may show only BTCUSDT and 24
rows.

- [x] **Step 2: Ingest 500 recent long/short rows for BTCUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed global-long-short-account-ratio --symbol BTCUSDT --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 3: Ingest 500 recent long/short rows for ETHUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed global-long-short-account-ratio --symbol ETHUSDT --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 4: Ingest 500 recent long/short rows for SOLUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed global-long-short-account-ratio --symbol SOLUSDT --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 5: Ingest 500 recent taker buy/sell rows for BTCUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed taker-buy-sell-volume --symbol BTCUSDT --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 6: Ingest 500 recent taker buy/sell rows for ETHUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed taker-buy-sell-volume --symbol ETHUSDT --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 7: Ingest 500 recent taker buy/sell rows for SOLUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed taker-buy-sell-volume --symbol SOLUSDT --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 8: Ingest 500 recent premium-index klines for BTCUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed premium-index-klines --symbol BTCUSDT --interval 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 9: Ingest 500 recent premium-index klines for ETHUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed premium-index-klines --symbol ETHUSDT --interval 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 10: Ingest 500 recent premium-index klines for SOLUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed premium-index-klines --symbol SOLUSDT --interval 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 11: Ingest 500 recent basis rows for BTCUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed basis --pair BTCUSDT --contract-type PERPETUAL --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 12: Ingest 500 recent basis rows for ETHUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed basis --pair ETHUSDT --contract-type PERPETUAL --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 13: Ingest 500 recent basis rows for SOLUSDT**

Run:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source binance-usdm --binance-usdm-feed basis --pair SOLUSDT --contract-type PERPETUAL --period 1h --limit 500 --allow-network --current-capital-usd 300
```

Expected: command exits 0 and reports `written` greater than 0.

- [x] **Step 14: Re-check local derivatives coverage**

Run:

```bash
sqlite3 var/research.sqlite "select record_type, coalesce(json_extract(payload_json,'$.symbol'), json_extract(payload_json,'$.pair')) as derivative_symbol, count(*) as n, min(observed_at), max(observed_at) from source_records where record_type in ('basis','long_short_account_ratio','premium_index_kline','taker_buy_sell_volume') group by record_type, derivative_symbol order by record_type, derivative_symbol;"
```

Expected: BTCUSDT, ETHUSDT, and SOLUSDT have nonzero rows for all four
derivatives record types. If a provider returns fewer than 500 because of
availability, record the exact count in the phase report.

- [x] **Step 15: Run the derivatives-conditioned lab**

Run:

```bash
uv run --extra dev crypto-alpha-agent strategy-feasibility --db var/research.sqlite --mode derivatives-conditioned-lab --symbol BTC/USDT --symbol ETH/USDT --symbol SOL/USDT --timeframe 1h --derivatives-period 1h --out var/reports/strategy-feasibility/derivatives-conditioned-lab.md --json-out var/reports/strategy-feasibility/derivatives-conditioned-lab.json --current-capital-usd 300 --cost-bps 10 --min-split-count 3
```

Expected: command exits 0, writes Markdown and JSON, and reports either:

- `readiness=feasible` with at least one candidate feasible; or
- `readiness=blocked` with stable reason codes and split diagnostics.

- [x] **Step 16: Copy latest lab artifacts for operator convenience**

Run:

```bash
cp var/reports/strategy-feasibility/derivatives-conditioned-lab.md var/reports/strategy-feasibility/latest-derivatives-conditioned-lab.md
cp var/reports/strategy-feasibility/derivatives-conditioned-lab.json var/reports/strategy-feasibility/latest-derivatives-conditioned-lab.json
```

Expected: copied files exist under ignored `var/`. Do not stage them.

## Task 5: Update Project State, Roadmap, And Phase Report

**Files:**
- Modify: `docs/goals/project-completion-state.md`
- Modify: `docs/roadmap.md`
- Create: `docs/goals/phase-reports/2026-06-08-derivatives-conditioned-feasibility-lab-report.md`
- Modify: `docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md`

- [x] **Step 1: Update project completion state current round**

In `docs/goals/project-completion-state.md`, replace the current Round 20
status block with a Round 21 block that records:

```markdown
- Round: 21
- Status: Derivatives-Conditioned Feasibility Lab completed as a read-only
  feasibility slice. The lab tested Binance USD-M derivatives-conditioned
  candidates before strategy registration and preserved candidate diagnostics
  for every feasible or blocked hypothesis.
- Started: 2026-06-08
- Completed: 2026-06-08 after focused tests, full pytest, ruff, diff checks,
  staged diff review, and staged secret scan.
- Active slice: Derivatives-Conditioned Feasibility Lab
- Active design source:
  `docs/superpowers/specs/2026-06-08-derivatives-conditioned-feasibility-lab-design.md`
- Active plan source:
  `docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md`
- Phase report:
  `docs/goals/phase-reports/2026-06-08-derivatives-conditioned-feasibility-lab-report.md`
```

Then update `Completed This Round`, `Verification Evidence`, and `Known
Remaining Gaps` with the actual lab result from Task 4. If the lab is blocked,
include the candidate names and exact reason codes. If the lab is feasible,
state that the next work is a separate strategy-registration design and that no
strategy code was added in this round.

- [x] **Step 2: Add Round 21 to history**

Append this row to the Round History table, replacing the verification phrase
with the exact observed counts before committing:

```markdown
| 21 | 2026-06-08 | Derivatives-Conditioned Feasibility Lab | focused feasibility and CLI tests passed; full pytest passed; ruff passed; diff/staged checks passed; staged secret scan returned []; Binance USD-M derivatives lab produced candidate diagnostics before any strategy registration | Derivatives-Conditioned Feasibility Lab commit pushed to `main` | `https://github.com/WW-shan/Crypto_Research_Agent` |
```

- [x] **Step 3: Update roadmap active profit-evidence section**

In `docs/roadmap.md`, update the paragraph that starts with
`Profit evidence redesign update on 2026-06-08` by adding this follow-up
paragraph after it:

```markdown
Derivatives-conditioned feasibility lab update on 2026-06-08: the next
read-only slice extends `strategy-feasibility` to compare Binance USD-M
derivatives-conditioned candidates before any strategy family is registered.
The lab keeps strategy registration and paper simulation blocked unless a
candidate passes walk-forward cost-adjusted expectancy gates. The actual lab
result is recorded in the 2026-06-08 derivatives-conditioned feasibility lab
phase report.
```

After running Task 4, add one more sentence with the actual result, for example:

```markdown
The first local lab run remained blocked with `non_positive_cost_adjusted_expectancy`
for all candidates, so no strategy-registration plan was opened.
```

Use the exact candidate and reason-code values from the JSON report.

- [x] **Step 4: Write the phase report**

Create `docs/goals/phase-reports/2026-06-08-derivatives-conditioned-feasibility-lab-report.md`
with this structure:

```markdown
# Derivatives-Conditioned Feasibility Lab Report

- Date: 2026-06-08
- Status: Completed as a read-only feasibility slice
- Design:
  `docs/superpowers/specs/2026-06-08-derivatives-conditioned-feasibility-lab-design.md`
- Plan:
  `docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md`
- Lab artifact:
  `var/reports/strategy-feasibility/derivatives-conditioned-lab.json`

## Summary

Summarize the implementation result in two paragraphs. State explicitly that no
strategy registry entry, paper runner, wallet path, live order route, or live
capital path was added.

## Smart Search Evidence

List the evidence directory and fetched files:

- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/00-deep-plan.json`
- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/05-fetch-binance-long-short.md`
- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/06-fetch-binance-taker.md`
- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/07-fetch-defillama-faq.md`
- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/08-fetch-dexscreener-reference.md`

## Local Feasibility Findings

Record the exact local SQLite coverage counts from Task 4 Step 14.

## Candidate Results

Record one bullet per candidate with readiness, reason codes, observations, net
mean, win rate, and split net means from the JSON artifact.

## Files Changed

List code, test, and docs files changed.

## Verification

Record exact command results:

- focused feasibility tests
- documentation contract tests
- full pytest
- ruff
- diff checks
- staged secret scan

## Decision

State whether strategy registration remains blocked or whether a new
strategy-registration design is allowed next.
```

Replace the instructional text with actual results before staging. Keep the
headings exactly as above so future agents can scan the report consistently.

- [x] **Step 5: Mark this plan's completed checkboxes**

In this plan file, change each completed step's checkbox from `- [ ]` to
`- [x]` as execution proceeds. Append a short `## Actual Result` section at the
end with the lab readiness, candidate results, verification summary, commit,
and push status.

- [x] **Step 6: Run documentation contract tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: all tests pass.

- [x] **Step 7: Commit documentation updates**

Run:

```bash
git add docs/goals/project-completion-state.md docs/roadmap.md docs/goals/phase-reports/2026-06-08-derivatives-conditioned-feasibility-lab-report.md docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md
git commit -m "docs: record derivatives feasibility lab result"
```

Expected: commit succeeds.

## Task 6: Final Verification, Staged Review, Commit, And Push

**Files:**
- Verify all changed tracked files.

- [x] **Step 1: Run focused feasibility and CLI tests**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py tests/test_cli_ingest.py tests/test_documentation_contract.py -q
```

Expected: all selected tests pass.

- [x] **Step 2: Run full pytest**

Run:

```bash
uv run --extra dev pytest -q
```

Expected: full test suite passes.

- [x] **Step 3: Run ruff**

Run:

```bash
uv run --extra dev ruff check .
```

Expected: `All checks passed!`

- [x] **Step 4: Run unstaged diff check**

Run:

```bash
git diff --check
```

Expected: no output and exit 0.

- [x] **Step 5: Inspect working tree**

Run:

```bash
git status --short --branch
```

Expected: only intended files are modified or staged. `var/` artifacts must not
appear as staged files.

- [x] **Step 6: Stage any final tracked changes**

Run:

```bash
git add src/crypto_alpha_agent/pipeline/strategy_feasibility.py src/crypto_alpha_agent/cli.py tests/test_strategy_feasibility.py docs/goals/project-completion-state.md docs/roadmap.md docs/goals/phase-reports/2026-06-08-derivatives-conditioned-feasibility-lab-report.md docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md
```

Expected: only intended tracked files are staged.

- [x] **Step 7: Run staged diff checks**

Run:

```bash
git diff --cached --check
git diff --cached --name-only
git diff --cached --stat
```

Expected: whitespace check exits 0; name list and stat contain only intended
code, test, and docs files.

- [x] **Step 8: Run staged secret scan**

Run:

```bash
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

Expected: `[]`.

- [x] **Step 9: Inspect staged diff for forbidden paths**

Run:

```bash
git diff --cached --no-ext-diff --unified=0
```

Expected: no API keys, bearer tokens, private keys, seed phrases, `.env`
contents, SQLite dumps, generated `var/` artifacts, wallet loading, live order
routing, or `uses_real_capital=true`.

- [x] **Step 10: Commit final slice if there are staged changes**

Run:

```bash
git commit -m "feat: add derivatives-conditioned feasibility lab"
```

Expected: commit succeeds if final changes remain after earlier task commits.
If all implementation and docs changes were already committed in earlier tasks,
this command should not be run.

- [x] **Step 11: Push main**

Run:

```bash
git push origin main
```

Expected: push succeeds.

- [x] **Step 12: Confirm clean synchronized worktree**

Run:

```bash
git status --short --branch
git log -1 --oneline
```

Expected: branch shows `main...origin/main` with no modified files.

## Self-Review

Spec coverage:

- Read-only lab mode: Tasks 2 and 3.
- Multiple derivatives-conditioned candidates: Task 2 Steps 9 and 10.
- Candidate diagnostics on blocked outcomes: Task 1 Steps 4-5 and Task 2 Step 9.
- No strategy registration or paper simulation: file structure excludes
  strategy registry and paper simulator files; Task 5 report requires explicit
  confirmation.
- CLI mode and artifacts: Task 3.
- Local recent derivatives evidence run: Task 4.
- State, roadmap, and phase report updates: Task 5.
- Verification and secret safety: Task 6.

Placeholder scan:

- This plan contains no unresolved markers, fake URL tokens, or unbound
  function names.
- Every new function referenced by tests is introduced in Task 2 or Task 3.

Type consistency:

- Public builder name: `build_derivatives_conditioned_lab_report`.
- Public renderer name: `render_derivatives_conditioned_lab_markdown`.
- Mode string: `derivatives-conditioned-lab`.
- Candidate model field: `candidate_metrics`.
- Safety fields: `uses_real_capital` and `live_order_routing`.

## Execution Choice

Plan complete and saved to
`docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md`.

Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task and
   review between tasks.
2. Inline Execution - execute tasks in this session using `executing-plans`
   with checkpoints.

## Actual Result

- Lab readiness: `blocked`.
- Report reason codes: `non_positive_cost_adjusted_expectancy`.
- Local coverage: BTC/USDT, ETH/USDT, and SOL/USDT each had 1000 market
  candles, 500 records for each derivatives feed, and 493 aligned
  market/derivatives records.
- Candidate results:
  - `long_short_crowding_contrarian`: blocked with
    `non_positive_cost_adjusted_expectancy`; observations 491; net mean
    -0.0005793479847853515; split net means -0.0006046264302122882,
    -0.00024592520433118714, and -0.00009748984824635497.
  - `taker_imbalance_reversal`: blocked with
    `non_positive_cost_adjusted_expectancy`; observations 492; net mean
    -0.000431171117083367; split net means -0.000658372949526737,
    -0.0008965914216619971, and 0.000347163847484194.
  - `premium_basis_risk_filter`: blocked with
    `non_positive_cost_adjusted_expectancy`; observations 491; net mean
    -0.0006688325383074194; split net means -0.0011450362603508074,
    -0.000411893774893493, and 0.00033193163994549264.
  - `momentum_derivatives_confirmation`: blocked with
    `non_positive_cost_adjusted_expectancy`; observations 176; net mean
    -0.000967730200042078; split net means -0.0001942394487509473,
    -0.001054052042053019, and -0.0008452017705897148.
- Strategy registration: remains blocked; no registry entry, paper runner,
  wallet path, live order route, or live-capital path was added.
- Verification summary: focused final suite passed with 42 tests, full pytest
  passed with 1136 tests, ruff passed, diff/staged checks passed, and staged
  secret scan returned `[]`.
- Commit status: implementation commits plus documentation closeout commit
  completed.
- Push status: pushed to `origin/main`.
