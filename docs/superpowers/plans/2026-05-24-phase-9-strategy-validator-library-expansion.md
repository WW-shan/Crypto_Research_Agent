# Phase 9 Strategy Validator Library Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the deterministic strategy library to at least three paper-simulated families and at least three watchlist-only families, with evidence-first fail-closed behavior.

**Architecture:** Add one Phase 8 data-backed executable family, `funding_open_interest_crowding`, that uses stored candles, funding rates, and open-interest history. Add one watchlist-only family, `volatility_compression_expansion_watchlist`, that emits research candidates from stored market candles but never enters paper simulation. Tighten existing executable funding validators with explicit stale-source, unsupported-symbol, and excessive-drawdown gates.

**Tech Stack:** Python 3.12, Pydantic models, SQLite-backed `ResearchDataStore`, existing `StrategyRegistry`, `paper_sim_loop`, `ValidationEvidenceLedger`, pytest, ruff.

---

## Evidence And Feasibility Inputs

- Smart Search evidence lives in `SMART_SEARCH_EVIDENCE_DIR=phase9-strategy-validator-library`. Do not commit the raw evidence files.
- Fetched sources used:
  - Binance funding-rate history docs: `06-binance-funding-rate-history.md`
  - Binance open-interest statistics docs: `07-binance-open-interest-statistics.md`
  - Binance basis docs: `08-binance-basis.md`
  - Perpetual futures paper: `09-arxiv-fundamentals-perpetual-futures.md`
  - QuantConnect walk-forward optimization docs: `10-quantconnect-walk-forward.md`
  - scikit-learn `TimeSeriesSplit` docs: `11-sklearn-time-series-split.md`
  - DefiLlama API docs: `12-defillama-api-docs.md`
  - DEX Screener API docs: `13-dexscreener-api-reference.md`
  - BIS crypto carry paper: `14-bis-crypto-carry.md`
- Local feasibility prototype:
  - Typed `MarketCandle`, `FundingRateRecord`, and `OpenInterestRecord` records aligned to produce one funding trade with 12% OI expansion.
  - Typed candle records produced a volatility-compression watchlist candidate with 0.000812 compression volatility, 2.3976% expansion return, and 51.8987% volume expansion.
- Explorer findings:
  - Existing default registry has two paper families and two watchlists.
  - Existing funding validators already produce core Phase 9 metrics but lack explicit stale-source, unsupported-symbol, and excessive-drawdown gates.
  - Watchlist-only families are already blocked from paper by registry and evidence-run gates.

## File Structure

- Create `src/crypto_alpha_agent/strategy/funding_oi_crowding.py`: executable validator and trade extraction for funding plus open-interest crowding.
- Create `src/crypto_alpha_agent/strategy/volatility_regime_watchlist.py`: research-only volatility compression/expansion watchlist.
- Modify `src/crypto_alpha_agent/strategy/registry.py`: register the new executable and watchlist families; wire validator and paper runner.
- Modify `src/crypto_alpha_agent/strategy/__init__.py`: export new strategy family constants and validators.
- Modify `src/crypto_alpha_agent/validation/funding_price.py`: add optional stale-source, unsupported-symbol, and max-drawdown gates used by the two existing funding families.
- Modify `src/crypto_alpha_agent/strategy/funding_mean_reversion.py`: pass the new funding-price gate parameters through.
- Modify `src/crypto_alpha_agent/pipeline/evidence_runner.py`: ingest open-interest history when an active family requires `open_interest`.
- Modify `src/crypto_alpha_agent/pipeline/expansion_preparation.py`: promote the OI-crowding family from candidate to registered deterministic validator and include the new volatility watchlist.
- Add tests:
  - `tests/test_funding_oi_crowding_strategy.py`
  - `tests/test_volatility_regime_watchlist_strategy.py`
- Update tests:
  - `tests/test_strategy_registry.py`
  - `tests/test_funding_price_validator.py`
  - `tests/test_research_loop_strategy_validation.py`
  - `tests/test_evidence_runner.py`
  - `tests/test_expansion_preparation.py`
  - `tests/test_documentation_contract.py`
- Update docs:
  - `README.md`
  - `docs/runbook.md`
  - `docs/project-asset-assessment.md`
  - `docs/roadmap.md`
  - `docs/goals/project-completion-state.md`
  - `docs/goals/phase-reports/2026-05-24-phase-9-strategy-validator-library-expansion-completion-report.md`

### Task 1: Tighten Existing Funding Validator Gates

**Files:**
- Modify: `src/crypto_alpha_agent/validation/funding_price.py`
- Modify: `src/crypto_alpha_agent/strategy/funding_mean_reversion.py`
- Test: `tests/test_funding_price_validator.py`

- [ ] **Step 1: Write failing tests for stale, unsupported, and drawdown gates**

Add tests that call `validate_funding_price_confirmation` with:

```python
result = validate_funding_price_confirmation(
    db_path,
    price_symbol="DOGE/USDT",
    funding_symbol="DOGE/USDT:USDT",
    timeframe="1h",
    supported_price_symbols=("BTC/USDT",),
    supported_funding_symbols=("BTC/USDT:USDT",),
    require_walk_forward=False,
)
assert "unsupported_symbol" in result.blocked_reasons
```

Also add a stale-source case with `now=datetime(2026, 5, 24, tzinfo=UTC)` and `max_age_hours=24.0`, plus a drawdown case with `max_drawdown_limit=0.01`.

- [ ] **Step 2: Run failing tests**

Run: `uv run --extra dev pytest tests/test_funding_price_validator.py -q`

Expected: tests fail because the parameters and blocked reasons do not exist yet.

- [ ] **Step 3: Implement the new optional gates**

Add parameters to `validate_funding_price_confirmation`, `validate_funding_price_confirmation_from_records`, and `_validate_funding_price_confirmation_from_history`:

```python
max_drawdown_limit: float = 0.20,
now: datetime | None = None,
max_age_hours: float | None = None,
supported_price_symbols: Sequence[str] | None = ("BTC/USDT",),
supported_funding_symbols: Sequence[str] | None = ("BTC/USDT:USDT",),
```

Append stable blocked reasons:

```python
unsupported_symbol
stale_source
excessive_drawdown
```

Keep defaults permissive enough for current BTC tests, and validate non-finite thresholds with `ValueError`.

- [ ] **Step 4: Pass through mean-reversion parameters**

In `strategy/funding_mean_reversion.py`, pass the same optional parameters through both database and records entrypoints.

- [ ] **Step 5: Run focused tests**

Run: `uv run --extra dev pytest tests/test_funding_price_validator.py tests/test_funding_mean_reversion_strategy.py -q`

Expected: all focused tests pass.

### Task 2: Add Funding Plus OI Crowding Executable Family

**Files:**
- Create: `src/crypto_alpha_agent/strategy/funding_oi_crowding.py`
- Modify: `src/crypto_alpha_agent/strategy/registry.py`
- Modify: `src/crypto_alpha_agent/strategy/__init__.py`
- Test: `tests/test_funding_oi_crowding_strategy.py`

- [ ] **Step 1: Write failing OI-crowding tests**

Add fixtures for candles, funding, and open-interest records. Required assertions:

```python
validation.strategy_family == "funding_open_interest_crowding"
validation.validator_name == "funding_oi_crowding"
validation.approved is True
validation.metrics["trade_count"] == 1
validation.metrics["open_interest_confirmed_trade_count"] == 1
validation.metrics["slippage_adjusted_expectancy"] > 0.0
```

Add fail-closed cases for:

```python
"missing_open_interest_records"
"no_open_interest_expansion"
"stale_source"
"unsupported_symbol"
```

Add a `run_paper_sim_loop` assertion that the family writes closed paper outcomes with `touched_real_capital is False` and `live_order_routing is False`.

- [ ] **Step 2: Run failing tests**

Run: `uv run --extra dev pytest tests/test_funding_oi_crowding_strategy.py -q`

Expected: import failures because the module and registry family do not exist.

- [ ] **Step 3: Implement the validator module**

Create:

```python
STRATEGY_FAMILY = "funding_open_interest_crowding"
VALIDATOR_NAME = "funding_oi_crowding"

def validate_funding_oi_crowding_from_records(...) -> StrategyValidationReport:
    ...

def extract_funding_oi_crowding_trades_from_records(...) -> list[FundingPriceTrade]:
    ...
```

Use `OpenInterestRecord` parsing from `SourceRecord` payloads, require an OI observation at or before the funding timestamp and a prior OI observation, and require:

```python
open_interest_change_pct >= min_open_interest_change_pct
```

Compute all Phase 9 metrics from OI-confirmed trades: `trade_count`, `gross_expectancy`, `net_return`, `max_drawdown`, `fee_adjusted_expectancy`, `slippage_adjusted_expectancy`, `walk_forward_split_count`, `walk_forward_pass_rate`, and blocked reasons.

- [ ] **Step 4: Register the family**

In `default_strategy_registry`, add:

```python
StrategyFamilySpec(
    strategy_family="funding_open_interest_crowding",
    display_name="Funding Crowding With Open Interest Confirmation",
    required_record_types=["market_candle", "funding_rate", "open_interest"],
    required_symbols=["BTC/USDT", "BTC/USDT:USDT"],
    supports_paper_simulation=True,
    min_capital_usd=25.0,
    max_notional_usd=25.0,
    validator_name="funding_oi_crowding",
    blocked_reasons=[],
    configured_capital_usd=max(current_capital_usd, 25.0),
)
```

Add `_funding_oi_crowding_validator` and `_funding_oi_crowding_paper_runner`, using the same paper-trade metrics shape as the existing funding runners.

- [ ] **Step 5: Run focused tests**

Run: `uv run --extra dev pytest tests/test_funding_oi_crowding_strategy.py tests/test_strategy_registry.py -q`

Expected: all focused tests pass.

### Task 3: Add Volatility Compression Watchlist

**Files:**
- Create: `src/crypto_alpha_agent/strategy/volatility_regime_watchlist.py`
- Modify: `src/crypto_alpha_agent/strategy/registry.py`
- Modify: `src/crypto_alpha_agent/strategy/__init__.py`
- Test: `tests/test_volatility_regime_watchlist_strategy.py`

- [ ] **Step 1: Write failing watchlist tests**

Create typed candle fixtures that show low realized volatility followed by a price and volume expansion. Required assertions:

```python
report.strategy_family == "volatility_compression_expansion_watchlist"
report.validator_name == "volatility_regime_watchlist"
report.approved is True
report.metrics["execution_role"] == "research_only"
report.metrics["paper_watchlist_only"] is True
report.metrics["candidate_count"] == 1
```

Add fail-closed tests for:

```python
"missing_market_candle_records"
"insufficient_history"
"stale_source"
"unsupported_symbol"
```

Add registry paper assertion:

```python
paper.status == "unsupported"
paper.blocked_reasons == ("paper_simulation_not_supported",)
```

- [ ] **Step 2: Run failing tests**

Run: `uv run --extra dev pytest tests/test_volatility_regime_watchlist_strategy.py -q`

Expected: import failures because the module and registry family do not exist.

- [ ] **Step 3: Implement the watchlist module**

Create:

```python
STRATEGY_FAMILY = "volatility_compression_expansion_watchlist"
VALIDATOR_NAME = "volatility_regime_watchlist"

def validate_volatility_regime_watchlist(records: Sequence[object], ...) -> StrategyValidationReport:
    ...
```

Group candles by `(symbol, timeframe)`, compute compression volatility from close-to-close returns, compute expansion return and volume-change percentage, and emit candidate dictionaries with:

```python
symbol
timeframe
latest_observed_at
compression_volatility
expansion_return
volume_change_pct
direction
```

- [ ] **Step 4: Register the watchlist**

Add a `StrategyFamilySpec` with `execution_role="research_only"`, `supports_paper_simulation=False`, `min_capital_usd=0.0`, and `max_notional_usd=0.0`.

- [ ] **Step 5: Run focused tests**

Run: `uv run --extra dev pytest tests/test_volatility_regime_watchlist_strategy.py tests/test_strategy_registry.py -q`

Expected: all focused tests pass.

### Task 4: Wire Research Loop, Evidence Runner, And Expansion Prep

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/evidence_runner.py`
- Modify: `src/crypto_alpha_agent/pipeline/expansion_preparation.py`
- Test: `tests/test_research_loop_strategy_validation.py`
- Test: `tests/test_evidence_runner.py`
- Test: `tests/test_expansion_preparation.py`

- [ ] **Step 1: Write failing pipeline tests**

Add tests that:

```python
summary.strategy_family == "funding_open_interest_crowding"
summary.walk_forward_split_count is not None
```

Add an evidence-run test with a fake collector that implements `fetch_open_interest_history`; assert an `ingest_ccxt_open_interest` step appears only when the requested family requires `open_interest`.

Update expansion-prep assertions so `funding_open_interest_crowding` is a registered deterministic validator and `volatility_compression_expansion_watchlist` is a watchlist-only adapter.

- [ ] **Step 2: Run failing pipeline tests**

Run: `uv run --extra dev pytest tests/test_research_loop_strategy_validation.py tests/test_evidence_runner.py tests/test_expansion_preparation.py -q`

Expected: pipeline tests fail until open-interest ingestion and catalog changes are wired.

- [ ] **Step 3: Add conditional OI ingestion**

In `run_daily_evidence_pipeline`, instantiate the registry before core ingestion and call `ingest_ccxt_open_interest_history` when any active family spec includes `open_interest`.

Use the existing funding symbol and timeframe:

```python
ingest_ccxt_open_interest_history(
    db,
    symbol=funding_symbol,
    timeframe=timeframe,
    limit=limit,
    allow_network=True,
    exchange_id=ccxt_exchange,
    collector=collector,
)
```

- [ ] **Step 4: Update expansion-preparation catalog**

Replace `funding_oi_crowding_candidate` with `funding_open_interest_crowding`, and add `volatility_compression_expansion_watchlist` as a Phase 9 watchlist family using `market_candle`, `volume`, and `close` fields.

- [ ] **Step 5: Run focused pipeline tests**

Run: `uv run --extra dev pytest tests/test_research_loop_strategy_validation.py tests/test_evidence_runner.py tests/test_expansion_preparation.py -q`

Expected: all focused tests pass.

### Task 5: Documentation, State, And Phase Report

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `docs/project-asset-assessment.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-24-phase-9-strategy-validator-library-expansion-completion-report.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write/update documentation contract tests**

Assert docs mention:

```text
funding_open_interest_crowding
volatility_compression_expansion_watchlist
blocked_by_missing_data
blocked_by_unqualified_source
```

Keep exact safety phrases:

```text
no wallet keys
no live order routing
no live execution
no wallet-key access
no order routing
no live capital
live_execution_enabled=false
```

- [ ] **Step 2: Run failing documentation test**

Run: `uv run --extra dev pytest tests/test_documentation_contract.py -q`

Expected: fails until docs are updated.

- [ ] **Step 3: Update operator docs**

Document the three executable families:

```text
funding_extremity_price_confirmation
funding_mean_reversion_after_extreme
funding_open_interest_crowding
```

Document the three watchlist-only families:

```text
defi_yield_regime_watchlist
dex_liquidity_volume_watchlist
volatility_compression_expansion_watchlist
```

State that basis/carry and cross-exchange funding dispersion remain blocked by missing qualified records and cost model gaps.

- [ ] **Step 4: Update roadmap and goal state**

Mark Phase 9 complete, make Phase 10 the next round, and link the Phase 9 report.

- [ ] **Step 5: Run documentation tests**

Run: `uv run --extra dev pytest tests/test_documentation_contract.py -q`

Expected: all documentation tests pass.

### Task 6: Review, Verification, Commit, And Push

**Files:**
- All changed files

- [ ] **Step 1: Run focused Phase 9 verification**

Run:

```bash
uv run --extra dev pytest \
  tests/test_funding_price_validator.py \
  tests/test_funding_mean_reversion_strategy.py \
  tests/test_funding_oi_crowding_strategy.py \
  tests/test_volatility_regime_watchlist_strategy.py \
  tests/test_strategy_registry.py \
  tests/test_research_loop_strategy_validation.py \
  tests/test_evidence_runner.py \
  tests/test_expansion_preparation.py \
  tests/test_documentation_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run two review passes**

Use subagents or local review to check:

```text
Critical/Important safety regressions
paper simulation accidentally routed for watchlists
missing fail-closed reasons
secret or local-path leaks
docs overstating basis/carry or cross-exchange readiness
```

Fix all Critical and Important findings and re-review.

- [ ] **Step 3: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests
```

Expected: pytest passes, ruff passes, diff check passes, secret scan returns `[]`.

- [ ] **Step 4: Stage and verify staged safety**

Run:

```bash
git status --short --untracked-files=all
git add README.md docs src tests
git diff --cached --check
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

Expected: staged diff check passes and staged secret scan returns `[]`.

- [ ] **Step 5: Commit and push**

Run:

```bash
git commit -m "feat: expand strategy validator library"
git push
```

Expected: commit and push succeed on `main`.

## Self-Review

- Spec coverage: The plan adds one executable OI-confirmed funding family, one watchlist-only volatility family, registry specs, paper gating, weekly-report-compatible evidence, docs/state/report updates, and blocked basis/cross-exchange candidates.
- Placeholder scan: No `TBD`, `TODO`, or undefined follow-up placeholders remain.
- Type consistency: New family ids are `funding_open_interest_crowding` and `volatility_compression_expansion_watchlist`; validator names are `funding_oi_crowding` and `volatility_regime_watchlist`.
