# Evidence Universe Data Depth And Hypothesis Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Round 23 as a read-only data-depth campaign, universe coverage upgrade, redesigned candidate hypothesis catalog, and stricter multi-hypothesis feasibility v2 lab before any backtest, paper, or live transition.

**Architecture:** Extend the Round 22 evidence funnel rather than replacing it. Add a `data_depth_campaign` planning/reporting layer, strengthen `evidence_universe`, expand read-only `candidate_screens`, and upgrade `multi_hypothesis_feasibility` with purge/gap validation, month/asset coverage, and multiple-testing summaries. Preserve the existing strategy registry, paper simulation, rollout gates, and live-execution blockers.

**Tech Stack:** Python 3.12, Pydantic v2 strict models, SQLite through `ResearchDataStore`, Binance Public Data client, existing source-health records, argparse CLI, pytest, ruff, Markdown/JSON artifacts, candidate JSONL memory, Smart Search evidence under `var/smart-search-evidence/2026-06-08-expand-profit-evidence-loop/` and `var/smart-search-evidence/2026-06-09-next-route-gap-research/`.

---

## Scope Boundaries

This plan must not add strategy registration, paper queue promotion, live
execution, wallet access, exchange order routing, order submission, or real
capital paths. DefiLlama and DexScreener remain discovery/regime inputs unless
future point-in-time evidence and later gates prove otherwise.

## File Structure

- Create: `src/crypto_alpha_agent/pipeline/data_depth_campaign.py`
  - Campaign spec, month range expansion, local coverage audit, missing job
    planning, collection result models, Markdown renderer.
- Modify: `src/crypto_alpha_agent/cli.py`
  - Add `data-depth-campaign` command with plan-only default and explicit
    `--collect --allow-network` collection gate.
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
  - Reuse existing Binance Public Data collection wrappers for campaign jobs.
- Modify: `src/crypto_alpha_agent/pipeline/evidence_universe.py`
  - Add unique-month coverage, requested-month coverage, minimum asset/month
    gate diagnostics, and point-in-time eligibility details.
- Modify: `src/crypto_alpha_agent/pipeline/candidate_screens.py`
  - Add redesigned candidate families while preserving read-only behavior.
- Modify: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
  - Add v2 validation policy, purge/gap split metrics, month/asset gates,
    multiple-testing summary, and stricter pass logic.
- Modify: `src/crypto_alpha_agent/pipeline/candidate_state_memory.py`
  - Persist v2 candidate states and reason codes without changing live or paper
    behavior.
- Create: `tests/test_data_depth_campaign.py`
- Modify: `tests/test_cli_ingest.py`
- Create: `tests/test_cli_data_depth_campaign.py`
- Modify: `tests/test_evidence_universe.py`
- Modify: `tests/test_candidate_screens.py`
- Modify: `tests/test_multi_hypothesis_feasibility.py`
- Modify: `tests/test_candidate_state_memory.py`
- Modify: `tests/test_documentation_contract.py`
- Create at closeout: `docs/goals/phase-reports/2026-06-09-evidence-universe-data-depth-and-hypothesis-redesign-report.md`
- Modify at closeout: `docs/goals/project-completion-state.md`
- Modify at closeout: `docs/roadmap.md`

## Task 1: Data-Depth Campaign Planner

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/data_depth_campaign.py`
- Test: `tests/test_data_depth_campaign.py`

- [ ] **Step 1: Write RED tests for month expansion and strict models**

Add tests that import `DataDepthCampaignSpec`, `CampaignMonth`, and
`expand_campaign_months`. The tests must assert that January through March 2026
expands to three month objects, invalid reversed ranges raise `ValueError`, and
strict Pydantic models reject extra fields.

Run:

```bash
uv run --extra dev pytest tests/test_data_depth_campaign.py -q
```

Expected: FAIL because the module does not exist.

- [ ] **Step 2: Implement campaign range models**

Create strict models for:

- `CampaignMonth(year: int, month: int)`
- `DataDepthCampaignSpec(symbols, timeframe, market, start, end, min_unique_months)`
- `DataDepthCoverageRow`
- `DataDepthCollectionJob`
- `DataDepthCampaignReport`

Implementation rules:

- Normalize symbols to slash format.
- Support only `market="um-futures"` initially.
- Set `uses_real_capital=False` and `live_order_routing=False`.
- Reject empty symbol lists and reversed month ranges.

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_data_depth_campaign.py -q
```

Expected: PASS for range/model tests.

- [ ] **Step 4: Commit Task 1**

```bash
git add src/crypto_alpha_agent/pipeline/data_depth_campaign.py tests/test_data_depth_campaign.py
git commit -m "feat: add data depth campaign planner"
```

## Task 2: Local Coverage Audit And Campaign CLI

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/data_depth_campaign.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_data_depth_campaign.py`
- Test: `tests/test_cli_data_depth_campaign.py`

- [ ] **Step 1: Write RED tests for coverage audit**

Seed `ResearchDataStore` with BTC/USDT market candles for January and March
2026 while leaving February empty. Assert the report shows:

- `unique_months=2`
- requested months January, February, March
- one missing collection job for BTC/USDT February 2026
- readiness `blocked` when `min_unique_months=3`
- reason code `insufficient_month_coverage`
- no database mutations during plan-only audit

- [ ] **Step 2: Implement `build_data_depth_campaign_report`**

The function must read local SQLite records only, group `market_candle` rows by
symbol/timeframe/month, calculate missing jobs, and render deterministic JSON
and Markdown. It must not call the network.

- [ ] **Step 3: Add plan-only CLI**

Add `data-depth-campaign` with required:

- `--db`
- repeated `--symbol`
- `--timeframe`
- `--start-year`
- `--start-month`
- `--end-year`
- `--end-month`
- `--out`
- `--json-out`

Default mode is plan-only. The payload must include `uses_real_capital=false`
and `live_order_routing=false`.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run --extra dev pytest tests/test_data_depth_campaign.py tests/test_cli_data_depth_campaign.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/crypto_alpha_agent/pipeline/data_depth_campaign.py src/crypto_alpha_agent/cli.py tests/test_data_depth_campaign.py tests/test_cli_data_depth_campaign.py
git commit -m "feat: add data depth campaign coverage CLI"
```

## Task 3: Gated Binance Public Data Campaign Collection

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/data_depth_campaign.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
- Test: `tests/test_data_depth_campaign.py`
- Test: `tests/test_cli_data_depth_campaign.py`
- Test: `tests/test_cli_ingest.py`

- [ ] **Step 1: Write RED tests for collection gating**

Add CLI tests that assert:

- `--collect` without `--allow-network` exits with code 2.
- `--collect --allow-network` calls the Binance Public Data ingestion path for
  each missing monthly job.
- A failed monthly job is recorded with `status="failed"` and does not hide
  partial coverage.
- Collection payload still reports `uses_real_capital=false` and
  `live_order_routing=false`.

- [ ] **Step 2: Implement collection job execution**

Implement a small executor that accepts missing `DataDepthCollectionJob`
objects and calls the existing Binance Public Data monthly kline ingestion
wrapper. It must catch job-level source failures and record them in the report
instead of crashing the entire campaign unless all jobs fail.

- [ ] **Step 3: Run focused collection tests**

Run:

```bash
uv run --extra dev pytest tests/test_data_depth_campaign.py tests/test_cli_data_depth_campaign.py tests/test_cli_ingest.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 3**

```bash
git add src/crypto_alpha_agent/pipeline/data_depth_campaign.py src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/data/ingestion.py tests/test_data_depth_campaign.py tests/test_cli_data_depth_campaign.py tests/test_cli_ingest.py
git commit -m "feat: add gated data depth collection"
```

## Task 4: Evidence Universe Depth Gate

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/evidence_universe.py`
- Test: `tests/test_evidence_universe.py`

- [ ] **Step 1: Write RED tests for month and asset coverage**

Add tests that seed uneven symbol/month coverage and assert the universe report
includes:

- `unique_market_months`
- `requested_market_months`
- `missing_market_months`
- `min_unique_months`
- `min_asset_count`
- `point_in_time_eligible`
- reason codes `insufficient_month_coverage` and
  `insufficient_asset_coverage`

- [ ] **Step 2: Implement universe depth fields**

Extend `UniverseAsset` and `EvidenceUniverseReport` with strict fields for
month coverage and asset-count gate status. Keep existing reason codes stable
and add new reason codes without removing old ones.

- [ ] **Step 3: Run universe tests**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_universe.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 4**

```bash
git add src/crypto_alpha_agent/pipeline/evidence_universe.py tests/test_evidence_universe.py
git commit -m "feat: add evidence universe depth gates"
```

## Task 5: Redesigned Candidate Hypothesis Families

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/candidate_screens.py`
- Test: `tests/test_candidate_screens.py`

- [ ] **Step 1: Write RED tests for new screen definitions**

Assert the catalog includes these new screen ids:

- `regime_gated_cross_asset_momentum`
- `regime_gated_cross_asset_reversal`
- `funding_basis_convergence_liquidity_filter`
- `derivatives_crowding_recent_window_price_action`
- `defi_dex_liquidity_regime_watchlist`

Tests must assert each screen is read-only, has required record types, declares
lookahead risk, and sets `uses_real_capital=false` and
`live_order_routing=false`.

- [ ] **Step 2: Implement catalog definitions and deterministic evaluators**

Add conservative evaluators:

- momentum/reversal variants use only prior close returns and volatility;
- funding/basis variants require market candles plus funding/basis or premium
  records;
- crowding variants require recent derivatives records and must mark recent
  window limitations;
- DeFi/DEX variants emit watchlist/regime signals only.

- [ ] **Step 3: Run candidate tests**

Run:

```bash
uv run --extra dev pytest tests/test_candidate_screens.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 5**

```bash
git add src/crypto_alpha_agent/pipeline/candidate_screens.py tests/test_candidate_screens.py
git commit -m "feat: add redesigned candidate screens"
```

## Task 6: Multi-Hypothesis Feasibility V2

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_multi_hypothesis_feasibility.py`
- Test: `tests/test_cli_multi_hypothesis_feasibility.py`

- [ ] **Step 1: Write RED tests for v2 validation policy**

Assert the report includes:

- `validation_policy.version == "v2"`
- `purge_gap_bars`
- `min_unique_months`
- `min_asset_count`
- split metrics that exclude purge/gap bars between train and test
- multiple-testing summary with evaluated candidate count and pass count
- blocked reasons for insufficient months and single-month dependency

- [ ] **Step 2: Implement validation policy models**

Add strict models:

- `FeasibilityValidationPolicy`
- `MultipleTestingSummary`

Extend candidate metrics with unique-month coverage and dependency flags.

- [ ] **Step 3: Upgrade split logic**

Modify walk-forward split generation to accept `purge_gap_bars`. The train
window must end before the purge gap, and the test window must start after the
gap. Preserve existing behavior when `purge_gap_bars=0`.

- [ ] **Step 4: Add CLI arguments**

Add:

- `--purge-gap-bars`
- `--min-unique-months`
- `--min-asset-count`
- `--feasibility-version v2`

Keep v1-compatible defaults only where existing tests require them; Round 23
artifacts should use v2.

- [ ] **Step 5: Run feasibility tests**

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 6**

```bash
git add src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py src/crypto_alpha_agent/cli.py tests/test_multi_hypothesis_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py
git commit -m "feat: add multi hypothesis feasibility v2"
```

## Task 7: Candidate State Memory V2

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/candidate_state_memory.py`
- Test: `tests/test_candidate_state_memory.py`

- [ ] **Step 1: Write RED tests for v2 state memory**

Assert persisted candidate memory records include:

- `feasibility_version`
- `validation_policy`
- `unique_months`
- `multiple_testing_adjusted`
- v2 reason codes

Assert blocked v2 candidates with insufficient months stay out of
`paper_collecting`.

- [ ] **Step 2: Implement v2 memory fields**

Update candidate-state serialization without changing old record ids. Preserve
legacy derivatives rejection memory.

- [ ] **Step 3: Run memory tests**

Run:

```bash
uv run --extra dev pytest tests/test_candidate_state_memory.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 7**

```bash
git add src/crypto_alpha_agent/pipeline/candidate_state_memory.py tests/test_candidate_state_memory.py
git commit -m "feat: persist feasibility v2 candidate states"
```

## Task 8: Run Round 23 Bounded Campaign And Lab

**Files:**
- Runtime artifacts under `var/reports/data-depth-campaign/`
- Runtime artifacts under `var/reports/strategy-feasibility/`
- Runtime artifacts under `var/memory/candidate-state.jsonl`

- [ ] **Step 1: Run plan-only campaign**

Run a plan-only campaign for a conservative liquid universe:

```bash
uv run crypto-alpha-agent data-depth-campaign \
  --db var/research.sqlite \
  --symbol BTC/USDT \
  --symbol ETH/USDT \
  --symbol SOL/USDT \
  --symbol BNB/USDT \
  --symbol XRP/USDT \
  --timeframe 1h \
  --start-year 2026 \
  --start-month 1 \
  --end-year 2026 \
  --end-month 5 \
  --min-unique-months 3 \
  --out var/reports/data-depth-campaign/round-23-plan.md \
  --json-out var/reports/data-depth-campaign/round-23-plan.json
```

Expected: exits 0, writes Markdown/JSON, and reports missing jobs.

- [ ] **Step 2: Run bounded gated collection**

Run collection only for missing Binance Public Data monthly kline jobs from
January through May 2026 and the five-symbol universe above:

```bash
uv run crypto-alpha-agent data-depth-campaign \
  --db var/research.sqlite \
  --symbol BTC/USDT \
  --symbol ETH/USDT \
  --symbol SOL/USDT \
  --symbol BNB/USDT \
  --symbol XRP/USDT \
  --timeframe 1h \
  --start-year 2026 \
  --start-month 1 \
  --end-year 2026 \
  --end-month 5 \
  --min-unique-months 3 \
  --collect \
  --allow-network \
  --out var/reports/data-depth-campaign/round-23-collect.md \
  --json-out var/reports/data-depth-campaign/round-23-collect.json
```

Expected: exits 0 when at least one job succeeds; failed jobs are explicit in
the artifact. If source access fails completely, preserve the failure artifact
and continue with plan-only feasibility as blocked.

- [ ] **Step 3: Run feasibility v2**

Run:

```bash
uv run crypto-alpha-agent strategy-feasibility \
  --db var/research.sqlite \
  --memory var/memory/candidate-state.jsonl \
  --persist-candidate-state \
  --mode multi-hypothesis-lab \
  --feasibility-version v2 \
  --symbol BTC/USDT \
  --symbol ETH/USDT \
  --symbol SOL/USDT \
  --symbol BNB/USDT \
  --symbol XRP/USDT \
  --timeframe 1h \
  --cost-bps-grid 5 \
  --cost-bps-grid 10 \
  --cost-bps-grid 20 \
  --cost-bps-grid 50 \
  --min-split-count 3 \
  --min-unique-months 3 \
  --min-asset-count 3 \
  --purge-gap-bars 24 \
  --out var/reports/strategy-feasibility/multi-hypothesis-lab-v2.md \
  --json-out var/reports/strategy-feasibility/multi-hypothesis-lab-v2.json \
  --current-capital-usd 300
```

Expected: exits 0 and writes candidate-state memory. Readiness may be blocked;
that is acceptable when reasons are explicit.

- [ ] **Step 4: Commit Task 8 artifacts only if repo policy allows runtime artifacts**

If runtime artifacts are ignored, do not force-add them. Commit only source and
documentation changes in later tasks. Preserve artifact paths in the phase
report.

## Task 9: Documentation, Verification, And Closeout

**Files:**
- Create: `docs/goals/phase-reports/2026-06-09-evidence-universe-data-depth-and-hypothesis-redesign-report.md`
- Modify: `docs/goals/project-completion-state.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/round-23-evidence-universe-data-depth-path-map.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write the Round 23 phase report**

The report must include:

- data campaign plan/collection results;
- universe coverage before/after;
- source failures and source successes;
- candidate v2 outcomes;
- cost sensitivity;
- purge/gap policy;
- multiple-testing summary;
- candidate-state memory records;
- explicit backtest/paper/live decision.

- [ ] **Step 2: Update project state and roadmap**

Set Round 23 to completed only after verification passes. Set Round 24 as
eligible only if a candidate reached `feasibility_passed`; otherwise keep Round
24 blocked.

- [ ] **Step 3: Run focused and full verification**

Run:

```bash
uv run --extra dev pytest tests/test_data_depth_campaign.py tests/test_cli_data_depth_campaign.py tests/test_evidence_universe.py tests/test_candidate_screens.py tests/test_multi_hypothesis_feasibility.py tests/test_candidate_state_memory.py tests/test_documentation_contract.py -q
uv run --extra dev ruff check .
git diff --check
```

If time and environment allow, run:

```bash
uv run --extra dev pytest -q
```

- [ ] **Step 4: Commit closeout**

```bash
git add docs/goals/phase-reports/2026-06-09-evidence-universe-data-depth-and-hypothesis-redesign-report.md docs/goals/project-completion-state.md docs/roadmap.md docs/goals/round-23-evidence-universe-data-depth-path-map.md tests/test_documentation_contract.py
git commit -m "docs: record evidence data depth phase result"
```

## Completion Decision

Round 23 is complete only when the phase report states one of these outcomes:

- `ready_for_round_24_event_backtest`: at least one candidate reached
  `feasibility_passed` under v2 gates; or
- `blocked_for_more_redesign`: no candidate reached `feasibility_passed`, with
  explicit data, cost, split, month, asset, or source reason codes.

Either outcome is valid. Live execution remains blocked in both outcomes.
