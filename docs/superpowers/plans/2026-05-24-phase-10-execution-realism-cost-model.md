# Phase 10 Execution Realism And Cost Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make paper simulation and validation outputs pessimistic enough that apparent edge cannot survive by ignoring exchange fees, min-notional and precision constraints, spread/slippage, stale signals, low-liquidity fills, or low-capital sizing.

**Architecture:** Add a small offline `execution.cost_model` module that turns each extracted paper trade into an execution-realism estimate. Integrate it at the paper materialization seam in `pipeline.paper_sim_loop`, keep validators responsible for historical signal quality and funding alignment, and preserve the existing paper-only safety boundary.

**Tech Stack:** Python 3.12, Pydantic strict models, SQLite payload ledgers, pytest, ruff, existing strategy registry and paper simulation loop.

---

## Binding Scope

Implement exactly Phase 10 from `docs/roadmap.md`: exchange maker/taker fee assumptions, symbol min notional and precision constraints, conservative slippage, funding timestamp alignment, stale-signal blocking, missed/partial-fill assumptions, pessimistic mode by default, and paper outcomes that record notional, fees, slippage, gross PnL, net PnL, max drawdown, stale status, and failure reasons. Keep all charter exclusions intact: no live trading, no wallet/private-key access, no exchange order routing, no real-capital execution, no MEV, no private RPC, and no speed-edge infrastructure.

## External Evidence

Smart Search deep research was run before this plan. Evidence files are intentionally kept under ignored `var/smart-search-evidence/phase-10-execution-realism/` in the main worktree, not committed.

Key source-backed implementation constraints:

- Binance USD-M Futures exchange information documents `PRICE_FILTER.tickSize`, `LOT_SIZE.stepSize`, `MARKET_LOT_SIZE`, and `MIN_NOTIONAL.notional`, and warns not to treat precision fields as tick/step sizes: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- Binance Spot filters define `PRICE_FILTER`, `LOT_SIZE`, `MIN_NOTIONAL`, `NOTIONAL`, and `MARKET_LOT_SIZE` semantics: https://developers.binance.com/docs/binance-spot-api-docs/filters
- Binance funding documentation says funding payments happen at specified intervals, defaulting to 00:00, 08:00, and 16:00 UTC for most perpetual contracts, and notes possible timing deviation: https://www.binance.com/en/support/faq/detail/360033525031
- CCXT market metadata exposes `maker`, `taker`, `precision`, and `limits` after `load_markets`, and distinguishes precision from limits: https://github.com/ccxt/ccxt/wiki/manual
- NautilusTrader backtesting docs emphasize simulated exchange processing, precision validation, and realistic fill modeling: https://nautilustrader.io/docs/latest/concepts/backtesting/
- CoinAPI execution-grade backtesting guidance highlights slippage, liquidity depth, order book/tick data, partial fills, and timestamp granularity as missing from OHLCV-only tests: https://www.coinapi.io/blog/backtest-crypto-strategies-with-real-market-data

## Local Feasibility

Baseline worktree verification:

- `git worktree add .worktrees/phase-10-execution-realism -b phase-10-execution-realism`
- `uv run --extra dev pytest -q` in the worktree: `864 passed, 4 skipped, 2 warnings in 92.24s`

Existing seams:

- `PaperSimulationOutcome` stores full JSON in `PaperOutcomeLedger`, so richer outcome fields do not require a table migration.
- `paper_sim_loop._closed_outcomes` is the narrow materialization seam that already computes notional, fees, slippage, gross PnL, and net PnL.
- `FundingPriceTrade` already carries funding timestamp, entry timestamp, exit timestamp, raw return, entry price, and exit price. It can export next funding timestamp and candle volume without changing strategy family interfaces.
- Existing validators already reject non-positive fee/slippage-adjusted expectancy and net return. Phase 10 should strengthen this with execution feasibility, not replace validators.

Prototype result:

```text
btc_perp_large_step {'adverse_entry': '65000', 'max_trade_qty': '0.000', 'effective_notional': '0.000', 'min_qty_notional': '65.000', 'feasible_under_25': False}
spot_small_step {'adverse_entry': '65000', 'max_trade_qty': '0.00038', 'effective_notional': '24.70000', 'min_qty_notional': '5.20000', 'feasible_under_25': True}
```

This proves the Phase 10 low-capital constraint cannot be represented by simple notional capping. The model must apply tick and quantity steps before deciding whether a candidate can trade under the owner profile.

## File Structure

- Create `src/crypto_alpha_agent/execution/cost_model.py`
  - Own typed execution assumptions, fee schedules, market constraints, adverse tick/step rounding, slippage, stale-signal checks, volume participation, missed/partial fill decisions, and per-trade cost estimates.
- Modify `src/crypto_alpha_agent/evidence/models.py`
  - Extend `PaperSimulationOutcome` with defaulted cost model, venue, fee, stale signal, and fill fields while preserving existing ledger payload compatibility.
- Modify `src/crypto_alpha_agent/evidence/paper.py`
  - Aggregate total notional, gross PnL, fees, slippage, stale signals, missed fills, and partial fills into evidence packages.
- Modify `src/crypto_alpha_agent/validation/funding_price.py`
  - Add explicit funding timestamp alignment checks using `next_funding_at`, returning `funding_alignment_invalid` instead of silently treating invalid intervals as valid trades.
- Modify `src/crypto_alpha_agent/strategy/registry.py`
  - Export entry/exit volume and next funding timestamp in paper trade metrics.
- Modify `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
  - Add default pessimistic cost model parameters, resolve constraints, call the cost model before emitting outcomes, emit blocked outcomes for infeasible trades, and include new assumptions in stable run/config IDs.
- Modify `src/crypto_alpha_agent/cli.py`
  - Expose paper simulation flags for venue, cost mode, max signal age, min notional, quantity step, tick size, max volume participation, and partial fill policy.
- Modify focused tests:
  - `tests/test_execution_cost_model.py`
  - `tests/test_paper_sim_loop.py`
  - `tests/test_paper_evidence.py`
  - `tests/test_funding_price_validator.py`
  - `tests/test_strategy_registry.py`
  - `tests/test_documentation_contract.py`
- Modify docs:
  - `README.md`
  - `docs/runbook.md`
  - `docs/roadmap.md`
  - `docs/project-asset-assessment.md`
  - `docs/goals/project-completion-state.md`
  - Create `docs/goals/phase-reports/2026-05-24-phase-10-execution-realism-cost-model-completion-report.md`

---

### Task 1: Cost Model Core

**Files:**
- Create: `src/crypto_alpha_agent/execution/cost_model.py`
- Test: `tests/test_execution_cost_model.py`

- [ ] **Step 1: Write failing tests for fee schedules, constraints, and default pessimism**

```python
from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.execution.cost_model import (
    ExecutionCostAssumptions,
    ExecutionTradeSpec,
    SymbolMarketConstraints,
    estimate_execution_cost,
)


def test_pessimistic_binance_defaults_use_taker_fee_floor_and_record_assumptions():
    trade = ExecutionTradeSpec(
        symbol="ETH/USDT:USDT",
        venue="binance",
        direction="long_price",
        signal_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        entry_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        exit_timestamp=datetime(2026, 1, 1, 1, tzinfo=UTC),
        entry_reference_price=100.0,
        exit_reference_price=101.0,
        raw_return=0.01,
        requested_notional_usd=25.0,
        entry_volume=1000.0,
        exit_volume=1000.0,
    )

    estimate = estimate_execution_cost(trade, ExecutionCostAssumptions(venue="binance"))

    assert estimate.status == "tradeable"
    assert estimate.cost_model_mode == "pessimistic"
    assert estimate.fee_model_id.startswith("binance:")
    assert estimate.maker_fee_rate >= 0
    assert estimate.taker_fee_rate >= estimate.maker_fee_rate
    assert estimate.applied_entry_fee_rate == pytest.approx(0.001)
    assert estimate.applied_exit_fee_rate == pytest.approx(0.001)
    assert estimate.fill_status == "full"
    assert estimate.fill_ratio == pytest.approx(1.0)
    assert estimate.fees_usd == pytest.approx(0.05)
    assert estimate.slippage_bps == pytest.approx(5.0)


def test_constraints_block_symbol_that_cannot_trade_under_25_usd():
    trade = ExecutionTradeSpec(
        symbol="BTC/USDT:USDT",
        venue="binance",
        direction="long_price",
        signal_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        entry_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        exit_timestamp=datetime(2026, 1, 1, 1, tzinfo=UTC),
        entry_reference_price=65000.0,
        exit_reference_price=65100.0,
        raw_return=100.0 / 65000.0,
        requested_notional_usd=25.0,
        entry_volume=1000.0,
        exit_volume=1000.0,
    )
    constraints = SymbolMarketConstraints(
        venue="binance",
        symbol="BTC/USDT:USDT",
        min_notional_usd=5.0,
        min_quantity=0.001,
        quantity_step=0.001,
        tick_size=0.1,
    )

    estimate = estimate_execution_cost(
        trade,
        ExecutionCostAssumptions(venue="binance", symbol_constraints=constraints),
    )

    assert estimate.status == "blocked"
    assert "quantity_precision_not_tradeable" in estimate.failure_reasons
    assert "min_quantity_notional_exceeds_max_notional" in estimate.failure_reasons
    assert estimate.fill_status == "blocked"


def test_stale_signal_and_low_liquidity_are_explicit_block_reasons():
    trade = ExecutionTradeSpec(
        symbol="ETH/USDT:USDT",
        venue="binance",
        direction="short_price",
        signal_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        entry_timestamp=datetime(2026, 1, 1, 2, tzinfo=UTC),
        exit_timestamp=datetime(2026, 1, 1, 3, tzinfo=UTC),
        entry_reference_price=100.0,
        exit_reference_price=99.0,
        raw_return=0.01,
        requested_notional_usd=25.0,
        entry_volume=0.01,
        exit_volume=0.01,
    )

    estimate = estimate_execution_cost(
        trade,
        ExecutionCostAssumptions(
            venue="binance",
            max_signal_age_seconds=60.0,
            max_volume_participation_rate=0.05,
        ),
    )

    assert estimate.status == "blocked"
    assert estimate.stale_signal_status == "stale"
    assert "stale_signal" in estimate.failure_reasons
    assert "missed_fill_assumed" in estimate.failure_reasons
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --extra dev pytest tests/test_execution_cost_model.py -q
```

Expected: fail because `crypto_alpha_agent.execution.cost_model` does not exist.

- [ ] **Step 3: Implement `cost_model.py`**

Implement:

- Strict Pydantic models for assumptions, fee schedules, symbol constraints, trade specs, and estimates.
- Default exchange fee schedules for `binance`, `okx`, and `bybit`, with pessimistic mode applying `max(taker_fee_rate, fee_rate_floor)`.
- Default constraints for common public venues and symbols, plus per-run overrides.
- Decimal adverse rounding:
  - long entry rounds price up, long exit rounds down.
  - short entry rounds price down, short exit rounds up.
  - quantity rounds down to quantity step to stay under max notional.
- Block reasons:
  - `min_notional_exceeds_max_notional`
  - `min_quantity_notional_exceeds_max_notional`
  - `quantity_precision_not_tradeable`
  - `rounded_notional_exceeds_max_notional`
  - `pre_cost_only_profitable`
  - `stale_signal`
  - `missed_fill_assumed`
  - `partial_fill_below_min_notional`
- Fill support:
  - default pessimistic mode blocks if quote volume capacity cannot fill the effective notional.
  - if `allow_partial_fills=True`, reduce notional and quantity when partial capacity remains above min notional.

- [ ] **Step 4: Run focused cost model tests**

Run:

```bash
uv run --extra dev pytest tests/test_execution_cost_model.py -q
```

Expected: all cost model tests pass.

### Task 2: Evidence Model And Aggregation Fields

**Files:**
- Modify: `src/crypto_alpha_agent/evidence/models.py`
- Modify: `src/crypto_alpha_agent/evidence/paper.py`
- Test: `tests/test_paper_evidence.py`

- [ ] **Step 1: Write failing tests for ledger-compatible outcome fields and aggregation**

Add tests that construct a `PaperSimulationOutcome` with:

```python
cost_model_mode="pessimistic",
venue="binance",
fee_model_id="binance:usdm:conservative",
maker_fee_rate=0.0002,
taker_fee_rate=0.0005,
applied_entry_fee_rate=0.001,
applied_exit_fee_rate=0.001,
entry_fee_usd=0.025,
exit_fee_usd=0.025,
slippage_bps=5.0,
stale_signal_status="fresh",
signal_age_seconds=0.0,
fill_status="full",
fill_ratio=1.0,
```

Assert `aggregate_paper_evidence` returns totals for notional, gross PnL, fees, slippage, stale signal count, missed fill count, and partial fill count.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --extra dev pytest tests/test_paper_evidence.py -q
```

Expected: fail because new model fields and aggregate fields do not exist.

- [ ] **Step 3: Extend models with defaulted fields**

Add defaulted fields to `PaperSimulationOutcome` so old ledger payloads and existing tests remain valid:

- `venue: str = "unknown"`
- `cost_model_mode: Literal["legacy", "base", "pessimistic"] = "legacy"`
- `fee_model_id: str = "legacy_unspecified"`
- `maker_fee_rate`, `taker_fee_rate`, `applied_entry_fee_rate`, `applied_exit_fee_rate`
- `entry_fee_usd`, `exit_fee_usd`, `slippage_bps`
- `stale_signal_status: Literal["fresh", "stale", "not_evaluated"] = "not_evaluated"`
- `signal_age_seconds: NonNegativeFiniteFloat | None = None`
- `fill_status: Literal["full", "partial", "missed", "blocked", "not_evaluated"] = "not_evaluated"`
- `fill_ratio: float = Field(default=0.0, ge=0, le=1, strict=True, allow_inf_nan=False)`

Add compatible aggregate fields to `PaperEvidenceInput` and `PaperEvidencePackage` with defaults.

- [ ] **Step 4: Run focused evidence tests**

Run:

```bash
uv run --extra dev pytest tests/test_paper_evidence.py -q
```

Expected: all focused paper evidence tests pass.

### Task 3: Funding Timestamp Alignment

**Files:**
- Modify: `src/crypto_alpha_agent/validation/funding_price.py`
- Test: `tests/test_funding_price_validator.py`

- [ ] **Step 1: Write failing funding alignment test**

Add a test where an extreme funding record has `next_funding_at` before or equal to its own timestamp, or where the entry candle would start at or after `next_funding_at`. Assert validation blocks with `funding_alignment_invalid`.

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run --extra dev pytest tests/test_funding_price_validator.py::test_funding_price_validator_fails_closed_on_invalid_funding_alignment -q
```

Expected: fail because no such block reason exists.

- [ ] **Step 3: Implement alignment check**

Add `_has_invalid_funding_alignment` near funding trade extraction. It should:

- Ignore records without `next_funding_at`.
- Block if `next_funding_at <= funding.timestamp`.
- Block if the selected entry candle timestamp is earlier than funding timestamp.
- Block if the selected entry candle timestamp is at or after `next_funding_at`.

Add `funding_alignment_invalid` to `_blocked_reasons`, and avoid extracting trades when alignment is invalid.

- [ ] **Step 4: Run focused validator tests**

Run:

```bash
uv run --extra dev pytest tests/test_funding_price_validator.py -q
```

Expected: focused validator tests pass.

### Task 4: Strategy Registry Trade Metadata

**Files:**
- Modify: `src/crypto_alpha_agent/strategy/registry.py`
- Modify: `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- Test: `tests/test_strategy_registry.py`

- [ ] **Step 1: Write failing registry test**

Extend the supported paper family test to assert each `paper_trades` entry includes:

- `entry_volume`
- `exit_volume`
- `next_funding_at`

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_registry.py::test_default_registry_runs_paper_for_supported_funding_families -q
```

Expected: fail because trade metadata is not exported.

- [ ] **Step 3: Export and parse fields**

Update `_paper_trade_metrics` to include:

```python
"entry_volume": float(trade.entry_bar.volume),
"exit_volume": float(trade.exit_bar.volume),
"next_funding_at": trade.funding.next_funding_at.isoformat() if trade.funding.next_funding_at else None,
```

Update `_PaperTrade` and `_paper_trade_from_mapping` to accept the same fields.

- [ ] **Step 4: Run focused registry tests**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_registry.py -q
```

Expected: focused registry tests pass.

### Task 5: Paper Simulation Integration

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- Test: `tests/test_paper_sim_loop.py`

- [ ] **Step 1: Write failing paper simulation tests**

Add tests for:

- default report and outcomes record `cost_model_mode="pessimistic"` and `venue="binance"`.
- a positive gross paper trade that is cost-killed is blocked or has negative net PnL and cannot be presented as a profitable closed edge.
- `min_notional_usd=30` blocks under `max_notional_usd=25` with `min_notional_exceeds_max_notional`.
- stale signal blocks even when source data is fresh.
- low volume blocks with `missed_fill_assumed` and record `fill_status="missed"`.
- partial fill can be recorded when `allow_partial_fills=True`.
- stable run/config IDs change when cost model assumptions change.

- [ ] **Step 2: Run focused paper simulation tests to verify failures**

Run:

```bash
uv run --extra dev pytest tests/test_paper_sim_loop.py -q
```

Expected: fail on new expectations.

- [ ] **Step 3: Integrate cost model before `_closed_outcomes`**

Update `run_paper_sim_loop` signature with defaults:

```python
venue: str = "binance",
cost_model_mode: Literal["base", "pessimistic"] = "pessimistic",
max_notional_usd: float = 25.0,
max_signal_age_seconds: float | None = 3600.0,
min_notional_usd: float | None = None,
min_quantity: float | None = None,
quantity_step: float | None = None,
tick_size: float | None = None,
max_volume_participation_rate: float = 0.05,
allow_partial_fills: bool = False,
```

Stop hard-coding `25.0`; use validated `max_notional_usd`. Keep a note when requested notional is capped, but do not convert infeasible symbols into closed outcomes.

For each trade:

- Build `ExecutionTradeSpec`.
- Build `ExecutionCostAssumptions`.
- If estimate is blocked, emit a `PaperSimulationOutcome(status="blocked")` with the estimate's execution metadata. Structural blocks can stay zeroed, but cost-killed or liquidity-killed candidates should still carry the computed notional, PnL, fees, slippage, and failure reasons so evidence can distinguish them from no-signal or validation blocks.
- If estimate is tradeable, emit a closed outcome with estimate quantity, effective notional, gross PnL, fees, slippage, net PnL, drawdown, stale status, fill status, and fee/slippage fields.

Include all new parameters in `_stable_run_id`, `_stable_execution_config_id`, and `_stable_candidate_id`.

- [ ] **Step 4: Run focused paper simulation tests**

Run:

```bash
uv run --extra dev pytest tests/test_paper_sim_loop.py -q
```

Expected: focused paper simulation tests pass.

### Task 6: CLI Flags

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_paper_sim_loop.py`

- [ ] **Step 1: Write failing CLI test**

Extend the CLI paper simulation test to pass:

```bash
--venue binance
--cost-model-mode pessimistic
--max-signal-age-seconds 3600
--min-notional-usd 5
--quantity-step 0.001
--tick-size 0.1
--max-volume-participation-rate 0.05
```

Assert the JSON report contains these assumptions and paper outcomes record pessimistic mode.

- [ ] **Step 2: Run the failing CLI test**

Run:

```bash
uv run --extra dev pytest tests/test_paper_sim_loop.py::test_cli_paper_sim_loop_outputs_json_and_persists_ledger -q
```

Expected: fail because flags are missing.

- [ ] **Step 3: Add parser flags and handler plumbing**

Add the flags to `paper-sim-loop` and pass values into `run_paper_sim_loop`. Use existing `_non_negative_finite_float` and `_positive_finite_float` validators.

- [ ] **Step 4: Run focused CLI tests**

Run:

```bash
uv run --extra dev pytest tests/test_paper_sim_loop.py -q
```

Expected: focused CLI/paper tests pass.

### Task 7: Documentation And Phase Report

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-asset-assessment.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-24-phase-10-execution-realism-cost-model-completion-report.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write failing documentation contract test**

Add required terms:

- `cost_model_mode`
- `pessimistic`
- `min_notional_exceeds_max_notional`
- `stale_signal`
- `missed_fill_assumed`
- `partial_fill`
- `live_execution_enabled=false`

- [ ] **Step 2: Update docs**

Document:

- Phase 10 completed behavior.
- New paper simulation flags.
- External evidence sources and local feasibility.
- Cost model assumptions.
- Explicit blocked paths and safety boundaries.
- Next phase remains Phase 11; do not start it.

- [ ] **Step 3: Run docs contract**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: docs contract passes.

### Task 8: Review, Verification, Commit, Push

**Files:**
- All changed files.

- [ ] **Step 1: Run focused suites**

Run:

```bash
uv run --extra dev pytest tests/test_execution_cost_model.py tests/test_paper_sim_loop.py tests/test_paper_evidence.py tests/test_funding_price_validator.py tests/test_strategy_registry.py tests/test_documentation_contract.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Request review pass 1**

Dispatch a subagent code review over the branch diff. Fix all Critical and Important findings.

- [ ] **Step 3: Request review pass 2**

Dispatch an independent subagent re-review after fixes. Fix all remaining Critical and Important findings.

- [ ] **Step 4: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests
```

Expected:

- pytest passes.
- ruff passes.
- diff check is clean.
- secret scan returns `[]`.

- [ ] **Step 5: Stage, verify staged diff, commit, and push**

Run:

```bash
git add README.md docs src tests
git diff --cached --check
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
git commit -m "feat: add execution realism cost model"
git push -u origin phase-10-execution-realism
```

Then merge/push to `main` only after the branch is clean and verified, following the owner-directed direct-push policy already recorded in `docs/goals/project-completion-goal.md`.

## Plan Self-Review

- Spec coverage: Phase 10 deliverables map to Tasks 1, 3, 5, 6, and 7. Review and verification requirements map to Task 8.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: `cost_model_mode`, `venue`, `fee_model_id`, stale signal fields, and fill fields are named consistently across cost model, paper outcomes, aggregation, CLI, and docs.
- Safety: no task adds live execution, wallet access, exchange order submission, MEV, private RPC, or real-capital paths.
