# Evidence Universe Expansion And Multi-Hypothesis Feasibility Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the upstream research funnel from a narrow derivatives lab into a read-only evidence universe, candidate screen registry, and multi-hypothesis feasibility lab that can prove or reject public-data strategy ideas before strategy registration, backtesting, paper collection, or live review.

**Architecture:** Keep the existing evidence factory, source-health records, SQLite store, `strategy-feasibility` command, paper gates, and live-readiness blockers. Add focused read-only modules for universe construction, candidate screen definitions, multi-hypothesis scoring, candidate state memory, and backtest/paper handoff artifacts. Every candidate advances through explicit gates: `candidate`, `source_qualified`, `feasibility_passed`, `backtest_passed`, `paper_collecting`, `stopped`, or `redesign_required`.

**Tech Stack:** Python 3.12, Pydantic v2 strict models, SQLite through `ResearchDataStore`, existing Binance Public Data / Binance USD-M / DefiLlama / DexScreener clients, argparse CLI, pytest, ruff, Smart Search evidence under `var/smart-search-evidence/2026-06-08-expand-profit-evidence-loop/`.

---

## Persisted Research Evidence

Evidence directory:

`var/smart-search-evidence/2026-06-08-expand-profit-evidence-loop/`

Source-backed constraints that must stay in the implementation:

- Binance global long/short account ratio and taker buy/sell volume are recent derivatives context only. The fetched official docs state latest-30-day availability and max `limit=500`.
- Binance Public Data is the long-history market-data route for klines, trades, and aggregate trades. It should be used for 12-24 month spot or futures market history before a candidate is treated as historically meaningful.
- Binance funding history can be paginated with max `limit=1000`, but funding or basis is not a risk-free edge.
- DefiLlama TVL, fees/revenue, DEX/perp volume, yields, stablecoins, and related data are research/regime inputs unless a later feasibility gate proves an executable family.
- DexScreener pair, liquidity, volume, price-change, transactions, FDV, market-cap, pair metadata, profiles, boosts, and trending data are discovery/watchlist inputs unless point-in-time snapshots accumulate enough evidence.
- Ordinary time-series validation must preserve chronological ordering and avoid training on future data.
- Backtests must include fees, slippage, spread or liquidity assumptions, market impact or latency buffers where relevant, and a lookahead-bias check before any paper queue handoff.

External reference URLs recorded by the research pass:

- Binance long/short ratio: <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio>
- Binance taker buy/sell volume: <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Taker-BuySell-Volume>
- Binance public data: <https://github.com/binance/binance-public-data>
- DefiLlama docs: <https://docs.llama.fi/>
- DexScreener API: <https://docs.dexscreener.com/api/reference>
- scikit-learn `TimeSeriesSplit`: <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>
- QuantStart backtesting costs: <https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/>
- Freqtrade lookahead analysis: <https://www.freqtrade.io/en/stable/lookahead-analysis/>
- Perpetual futures research: <https://arxiv.org/html/2212.06888v5>

## Hard Scope Boundaries

This phase must not:

- Register the current four derivatives-conditioned candidates as strategy families.
- Send any one-split or single-asset positive result to paper.
- Add live execution, wallet access, exchange order routing, order submission, or real-capital paths.
- Add MEV, CEX-DEX speed arbitrage, bridge races, flash loans, premium RPC, private order flow, colocation, or large-balance-sheet dependencies.
- Treat LLM autonomy as the solution to the profit-evidence blocker. The current blocker is strategy evidence, not agent framework coverage.
- Promote DefiLlama or DexScreener discovery output into execution without point-in-time historical evidence and feasibility/backtest gates.

## File Structure

- Create: `src/crypto_alpha_agent/pipeline/evidence_universe.py`
  - Strict universe models, point-in-time asset eligibility, source coverage, staleness, duplicate, timestamp-alignment, source-health, proxy/direct route, and survivorship/lookahead diagnostics.
- Create: `src/crypto_alpha_agent/pipeline/candidate_screens.py`
  - Read-only candidate screen catalog and deterministic signal evaluators. This is not the strategy registry.
- Create: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
  - Multi-hypothesis report models, cost sensitivity, walk-forward split metrics, turnover, asset/time coverage, blocked reasons, and pass/fail aggregation.
- Create: `src/crypto_alpha_agent/pipeline/candidate_state_memory.py`
  - Candidate state machine persistence through existing JSONL memory patterns, including pass/block/fail reasons.
- Modify: `src/crypto_alpha_agent/data/binance_public.py`
  - Extend Binance Public Data URL building and parsing to support USD-M futures monthly klines when the phase needs futures market history.
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
  - Add ingestion summaries for futures public monthly klines if local feasibility confirms source access and parser shape.
- Modify: `src/crypto_alpha_agent/data/source_probe.py`
  - Ensure DefiLlama and DexScreener discovery routes are explicitly qualified for read-only source discovery and distinguish route/source failure.
- Modify: `src/crypto_alpha_agent/cli.py`
  - Add `strategy-feasibility --mode multi-hypothesis-lab` or a narrower `candidate-lab` command after RED CLI tests decide the least invasive command shape.
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
  - Add Markdown rendering for universe coverage, candidate screens, cost sensitivity, and candidate-state transitions if rendering does not fit cleanly inside the lab module.
- Modify: `docs/goals/project-completion-state.md`
  - Record this plan, evidence path, next planned round, blocked current candidates, and actual-vs-expected gap.
- Modify: `docs/roadmap.md`
  - Add the persistent path map from data expansion through paper/governance automation.
- Create: `docs/goals/phase-reports/2026-06-08-evidence-universe-expansion-and-multi-hypothesis-feasibility-lab-report.md`
  - Written only after implementation and verification.
- Test: `tests/test_binance_public_data.py`
- Test: `tests/test_source_probe.py`
- Test: `tests/test_evidence_universe.py`
- Test: `tests/test_candidate_screens.py`
- Test: `tests/test_multi_hypothesis_feasibility.py`
- Test: `tests/test_strategy_feasibility.py`
- Test: `tests/test_cli_multi_hypothesis_feasibility.py`
- Test: `tests/test_candidate_state_memory.py`
- Test: `tests/test_documentation_contract.py`

## Task 1: Source Evidence And Long-History Data Gate

**Files:**
- Modify: `src/crypto_alpha_agent/data/binance_public.py`
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
- Modify: `src/crypto_alpha_agent/data/source_probe.py`
- Test: `tests/test_binance_public_data.py`
- Test: `tests/test_source_probe.py`
- Test: `tests/test_cli_ingest.py`

- [x] **Step 1: Add RED tests for Binance Public Data futures monthly klines**

Add tests that assert:

- `build_monthly_um_futures_klines_url("BTCUSDT", "1h", 2026, 5)` returns `/data/futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05.zip`.
- Parsed futures kline rows become `MarketCandle` records with `source="binance_public"`, `venue="binance_usdm"`, normalized symbol `BTC/USDT`, timeframe `1h`, non-negative OHLCV, and `uses_real_capital=false` through the stored record payload contract.
- A bad or empty archive writes source-health failure and raises a clear ingestion error.

- [x] **Step 2: Run the futures public-data RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_binance_public_data.py -q
```

Expected: FAIL on the missing futures URL/client method.

- [x] **Step 3: Implement the minimal futures public-data client extension**

Add methods parallel to existing spot monthly klines:

- `build_monthly_um_futures_klines_url(symbol, interval, year, month)`
- `download_monthly_um_futures_klines(symbol, interval, year, month)`

The parser must reuse the existing kline row parser shape and set `venue="binance_usdm"` for futures records.

- [x] **Step 4: Add ingestion wrapper and CLI coverage for futures public data**

Add an ingestion wrapper that writes typed `market_candle` records and source-health rows. The command must require `--allow-network`, must not print secrets, and must write `uses_real_capital=false` plus `live_order_routing=false` in the CLI payload.

- [x] **Step 5: Run focused source tests**

Run:

```bash
uv run --extra dev pytest tests/test_binance_public_data.py tests/test_cli_ingest.py tests/test_source_probe.py -q
```

Expected: PASS.

- [x] **Step 6: Commit Task 1**

Run:

```bash
git add src/crypto_alpha_agent/data/binance_public.py src/crypto_alpha_agent/data/ingestion.py src/crypto_alpha_agent/data/source_probe.py tests/test_binance_public_data.py tests/test_cli_ingest.py tests/test_source_probe.py
git commit -m "feat: expand public data source gate"
```

## Task 2: Point-In-Time Evidence Universe Builder

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/evidence_universe.py`
- Test: `tests/test_evidence_universe.py`

- [x] **Step 1: Add RED tests for universe construction**

Add tests that seed market candles, derivatives records, source-health rows, DefiLlama snapshots, and DexScreener snapshots, then assert the universe report includes:

- requested symbol list and normalized exchange symbols;
- `market_candle` coverage counts by symbol/timeframe;
- derivatives context coverage by record type and latest-30-day limitation flag;
- DefiLlama and DexScreener discovery coverage marked as `watchlist_or_regime_only`;
- stale, duplicate, missing, and timestamp-alignment blocked reasons;
- `point_in_time_universe=true` only when the universe does not use a future discovery list to evaluate past windows;
- `uses_real_capital=false` and `live_order_routing=false`.

- [x] **Step 2: Run the universe RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_universe.py -q
```

Expected: FAIL because `evidence_universe.py` does not exist.

- [x] **Step 3: Implement strict universe models**

Create strict Pydantic models:

- `UniverseAsset`
- `UniverseSourceCoverage`
- `UniverseQualityIssue`
- `EvidenceUniverseReport`

Reason codes must include at least:

- `missing_market_history`
- `insufficient_history_window`
- `stale_source_health`
- `duplicate_timestamps`
- `timestamp_alignment_gap`
- `lookahead_universe_risk`
- `watchlist_only_source`
- `source_probe_required`

- [x] **Step 4: Implement `build_evidence_universe_report`**

The function must load only local records from `ResearchDataStore`, produce no new source records, and be deterministic for the same database input.

- [x] **Step 5: Run focused universe tests**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_universe.py -q
```

Expected: PASS.

- [x] **Step 6: Commit Task 2**

Run:

```bash
git add src/crypto_alpha_agent/pipeline/evidence_universe.py tests/test_evidence_universe.py
git commit -m "feat: add evidence universe builder"
```

## Task 3: Read-Only Candidate Screen Registry

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/candidate_screens.py`
- Test: `tests/test_candidate_screens.py`

- [x] **Step 1: Add RED tests for candidate catalog**

Add tests that assert the catalog contains these screen IDs:

- `short_horizon_momentum_volatility_filter`
- `short_horizon_reversal_volatility_filter`
- `perp_spot_basis_funding_deviation`
- `derivatives_crowding_price_action`
- `defi_dex_regime_discovery`
- `cross_asset_ranking_turnover_cap`

Each screen must declare required record types, minimum history bars, cost model requirement, lookahead risk level, execution role, and blocked reasons.

- [x] **Step 2: Run candidate screen RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_candidate_screens.py -q
```

Expected: FAIL because the module does not exist.

- [x] **Step 3: Implement strict screen catalog models**

Create:

- `CandidateScreenDefinition`
- `CandidateScreenSignal`
- `CandidateScreenResult`

The catalog must be read-only and must not import or mutate `default_strategy_registry`.

- [x] **Step 4: Implement deterministic screen evaluators**

Implement evaluators that can return blocked results when required records are missing. Positive signals are allowed only when they are derived from historical records already present in SQLite.

- [x] **Step 5: Run focused candidate screen tests**

Run:

```bash
uv run --extra dev pytest tests/test_candidate_screens.py -q
```

Expected: PASS.

- [x] **Step 6: Commit Task 3**

Run:

```bash
git add src/crypto_alpha_agent/pipeline/candidate_screens.py tests/test_candidate_screens.py
git commit -m "feat: add read-only candidate screens"
```

## Task 4: Multi-Hypothesis Feasibility Lab

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
- Modify: `src/crypto_alpha_agent/pipeline/strategy_feasibility.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_multi_hypothesis_feasibility.py`
- Test: `tests/test_strategy_feasibility.py`
- Test: `tests/test_cli_multi_hypothesis_feasibility.py`

- [x] **Step 1: Add RED tests for lab report gates**

Add tests that assert each candidate output includes:

- sample count;
- asset coverage;
- split coverage;
- gross mean;
- net mean;
- win rate;
- turnover;
- selected symbol counts;
- cost sensitivity at 5, 10, 20, and 50 bps;
- per-split net expectancy;
- blocked reason codes;
- candidate state transition target.

Required blocked reasons:

- `insufficient_universe_coverage`
- `insufficient_samples`
- `insufficient_walk_forward_splits`
- `non_positive_cost_adjusted_expectancy`
- `unstable_walk_forward_performance`
- `cost_sensitivity_fragile`
- `single_asset_or_time_window_dependency`
- `lookahead_risk`
- `watchlist_only_source`

- [x] **Step 2: Run the lab RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py -q
```

Expected: FAIL because the lab module and CLI mode do not exist.

- [x] **Step 3: Implement strict feasibility report models**

Create:

- `CostSensitivityMetric`
- `CandidateSplitMetric`
- `CandidateFeasibilityMetric`
- `MultiHypothesisFeasibilityReport`

All models must set `extra="forbid"`, `strict=True`, and `allow_inf_nan=False`.

- [x] **Step 4: Implement report builder**

Implement `build_multi_hypothesis_feasibility_report` so it:

- accepts `db_path`, `memory_path`, `symbols`, `timeframe`, `current_capital_usd`, `cost_bps_grid`, `min_split_count`, and optional `candidate` filters;
- uses the universe report and screen catalog;
- performs chronological walk-forward splits;
- fails closed when any candidate uses future data, watchlist-only data as execution evidence, or insufficient cost robustness;
- writes no database rows unless explicitly called through candidate-state memory in Task 5.

- [x] **Step 5: Wire the CLI**

Add either:

```text
strategy-feasibility --mode multi-hypothesis-lab
```

or a dedicated:

```text
candidate-lab
```

Use the command shape that produces the smallest clean diff after checking `src/crypto_alpha_agent/cli.py`. The command must write Markdown and JSON artifacts and must set `llm_gate_bypass=True` only if it remains a deterministic read-only feasibility command like the current `strategy-feasibility` modes.

- [x] **Step 6: Run focused feasibility tests**

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py tests/test_strategy_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py -q
```

Expected: PASS.

- [x] **Step 7: Commit Task 4**

Run:

```bash
git add src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py src/crypto_alpha_agent/pipeline/strategy_feasibility.py src/crypto_alpha_agent/cli.py tests/test_multi_hypothesis_feasibility.py tests/test_strategy_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py
git commit -m "feat: add multi-hypothesis feasibility lab"
```

## Task 5: Candidate State Memory And Rejection Ledger

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/candidate_state_memory.py`
- Modify: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
- Test: `tests/test_candidate_state_memory.py`
- Test: `tests/test_multi_hypothesis_feasibility.py`

- [ ] **Step 1: Add RED tests for candidate state transitions**

Add tests that assert:

- candidates start as `candidate`;
- source-qualified candidates become `source_qualified`;
- candidates with all feasibility gates passing become `feasibility_passed`;
- candidates with any hard blocker become `stopped` or `redesign_required`;
- the four current derivatives candidates persist rejected memory with `non_positive_cost_adjusted_expectancy`;
- repeated runs update the same candidate memory record instead of duplicating stale pass/fail records.

- [ ] **Step 2: Run candidate memory RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_candidate_state_memory.py -q
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement candidate state memory**

Use existing `MemoryStore` JSONL persistence. Store candidate records with:

- `record_id`;
- `candidate_id`;
- `state`;
- `reason_codes`;
- `evidence_refs`;
- `source_coverage`;
- `feasibility_summary`;
- `last_seen_at`;
- `uses_real_capital=false`;
- `live_order_routing=false`.

- [ ] **Step 4: Add CLI persistence switch**

Add an explicit `--memory` argument and `--persist-candidate-state` gate for the lab command. The default lab run remains read-only and does not mutate memory.

- [ ] **Step 5: Run focused memory tests**

Run:

```bash
uv run --extra dev pytest tests/test_candidate_state_memory.py tests/test_multi_hypothesis_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add src/crypto_alpha_agent/pipeline/candidate_state_memory.py src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py src/crypto_alpha_agent/cli.py tests/test_candidate_state_memory.py tests/test_multi_hypothesis_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py
git commit -m "feat: persist candidate feasibility states"
```

## Task 6: Backtest And Paper Handoff Path Map

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Add documentation contract tests**

Add tests that assert `docs/roadmap.md` and `docs/goals/project-completion-state.md` mention:

- `Evidence Universe Expansion and Multi-Hypothesis Feasibility Lab`;
- `backtest_passed`;
- `paper_collecting`;
- `30/60/90`;
- `lookahead`;
- `cost sensitivity`;
- `live execution` remains blocked.

- [ ] **Step 2: Run documentation RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: FAIL until docs are updated.

- [ ] **Step 3: Update the persistent path map**

Record this sequence:

1. Source and universe expansion.
2. Data-quality and lookahead-risk gate.
3. Candidate screen registry.
4. Multi-hypothesis feasibility lab.
5. Event-driven backtest readiness and cost realism.
6. Paper queue only after feasibility plus backtest pass.
7. 30/60/90 paper observation tracking.
8. Governance state machine and stopped/redesign memory.
9. Automated daily collection and ranking reports.

- [ ] **Step 4: Run documentation tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add docs/roadmap.md docs/goals/project-completion-state.md tests/test_documentation_contract.py
git commit -m "docs: persist evidence universe path map"
```

## Task 7: Local Evidence Run And Phase Report

**Files:**
- Create: `docs/goals/phase-reports/2026-06-08-evidence-universe-expansion-and-multi-hypothesis-feasibility-lab-report.md`
- Modify: `docs/goals/project-completion-state.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Run source probes**

Run source probes for the expanded data sources:

```bash
uv run --extra dev crypto-alpha-agent source-probe --list-targets
uv run --extra dev crypto-alpha-agent source-probe --db var/research.sqlite --target dexscreener_pairs --allow-network
uv run --extra dev crypto-alpha-agent source-probe --db var/research.sqlite --target defillama_yield_pools --allow-network
uv run --extra dev crypto-alpha-agent source-probe --db var/research.sqlite --target defillama_fundamentals --allow-network
```

Expected: each network probe either writes a parsed source-health record or records a blocked provider/source failure with no secrets and no live execution.

- [ ] **Step 2: Collect or confirm long-history market coverage**

Run a bounded public-data collection for a liquid universe. The implementation must choose symbols that are already normalized by the universe builder, starting with BTC/USDT, ETH/USDT, SOL/USDT and then expanding only when source health and storage coverage are clean.

- [ ] **Step 3: Run the multi-hypothesis lab**

Run the chosen CLI command with:

- `--cost-bps-grid 5 --cost-bps-grid 10 --cost-bps-grid 20 --cost-bps-grid 50`
- at least three symbols;
- at least three walk-forward splits;
- Markdown and JSON outputs under `var/reports/strategy-feasibility/`.

Expected: candidates either pass all gates or produce explicit blocked reasons. Passing feasibility is not paper approval.

- [ ] **Step 4: Write the phase report**

The phase report must list:

- Smart Search evidence path;
- source-probe outcomes;
- data coverage;
- candidates evaluated;
- candidate states;
- pass/block reasons;
- cost sensitivity;
- lookahead/data-quality notes;
- whether any candidate is eligible for the later backtest phase;
- verification commands and outputs;
- explicit confirmation that live execution, wallet access, and order routing remain absent.

- [ ] **Step 5: Run final verification**

Run:

```bash
uv run --extra dev pytest tests/test_binance_public_data.py tests/test_source_probe.py tests/test_evidence_universe.py tests/test_candidate_screens.py tests/test_multi_hypothesis_feasibility.py tests/test_candidate_state_memory.py tests/test_strategy_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py tests/test_documentation_contract.py -q
uv run --extra dev pytest -q
uv run --extra dev ruff check .
```

Expected: all pass before closeout.

- [ ] **Step 6: Secret and diff checks**

Run:

```bash
git diff --check
git diff --cached --check
uv run --extra dev python -m crypto_alpha_agent.security.secret_scan --staged
```

Expected: no whitespace errors and secret scan returns no findings.

- [ ] **Step 7: Commit Task 7**

Run:

```bash
git add docs/goals/phase-reports/2026-06-08-evidence-universe-expansion-and-multi-hypothesis-feasibility-lab-report.md docs/goals/project-completion-state.md docs/roadmap.md
git commit -m "docs: record evidence universe lab result"
```

## Downstream Path After This Phase

This phase completes only the upstream research funnel. The next phases must be separate goal rounds:

1. **Event-Driven Backtest Expansion**
   - Enter only for candidates with `feasibility_passed`.
   - Add fees on entry and exit, slippage, spread or liquidity assumptions, latency buffer, min notional, precision, partial/missed fill, timeframe-detail checks, monthly/yearly breakdown, and lookahead-analysis style validation.
2. **Paper Evidence Delta Tracker**
   - Enter only for candidates with `backtest_passed`.
   - Track backtest expectation versus paper actual, 30/60/90 observations, closed trades, failed trades, missed trades, net PnL, drawdown, cost drag, signal decay, and paper failure reasons.
3. **Governance And Automation Expansion**
   - Daily schedule updates long-history and recent derivatives data, runs candidate discovery, runs the multi-hypothesis lab, writes pass/fail rankings, and sends only passed candidates to the backtest queue.
   - Stopped families and failed candidates remain in memory and are not silently rerun.
4. **Live Readiness Review**
   - Still blocked by charter until a future explicit charter revision and owner approval.
   - No current phase should implement live-capital execution.

## Completion Gate

The phase is complete only when:

- the new plan and path map are committed;
- local source qualification is persisted in source-health rows or blocked with explicit provider/source reasons;
- the universe builder reports data coverage and lookahead risk;
- the candidate screen registry produces deterministic read-only screen results;
- the multi-hypothesis lab reports cost sensitivity, walk-forward metrics, turnover, and pass/block reasons;
- current failed derivatives candidates are persisted as rejected memory when the explicit persistence switch is used;
- no strategy registry entry is added unless a later approved phase proves feasibility plus backtest readiness;
- full pytest, focused pytest, ruff, diff checks, and staged secret scan pass;
- the phase report is written under `docs/goals/phase-reports/`.
