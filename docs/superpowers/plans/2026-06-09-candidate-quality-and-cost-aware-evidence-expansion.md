# Candidate Quality And Cost-Aware Evidence Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Round 24 cost-aware candidate-quality controls, deterministic liquid-universe expansion, and richer feasibility diagnostics while preserving read-only research boundaries.

**Architecture:** Extend the existing Round 23 lab. Add a focused `universe_presets` module, extend `multi_hypothesis_feasibility` with signal-score filtering and turnover gates, and thread the new options through `strategy-feasibility`, `data-depth-campaign`, and `evidence-universe-lab`.

**Tech Stack:** Python 3.12, Pydantic v2 strict models, argparse CLI, SQLite through `ResearchDataStore`, pytest, ruff, Markdown/JSON artifacts, existing candidate-state JSONL memory.

---

## File Structure

- Create: `src/crypto_alpha_agent/pipeline/universe_presets.py`
  - Deterministic liquid USD-M preset and symbol resolution helpers.
- Modify: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
  - Add cost-aware validation policy fields, observation signal scores,
    raw/filtered sample counts, per-cost filtering, turnover cap, and
    `excessive_turnover` reason code.
- Modify: `src/crypto_alpha_agent/cli.py`
  - Add universe preset and cost-aware flags to existing read-only commands.
- Create: `tests/test_universe_presets.py`
- Modify: `tests/test_multi_hypothesis_feasibility.py`
- Modify: `tests/test_cli_multi_hypothesis_feasibility.py`
- Modify: `tests/test_cli_evidence_universe_lab.py`
- Modify: `tests/test_cli_data_depth_campaign.py`
- Modify: `tests/test_documentation_contract.py`
- Create at closeout:
  `docs/goals/phase-reports/2026-06-09-candidate-quality-and-cost-aware-evidence-expansion-report.md`
- Create:
  `docs/goals/round-24-candidate-quality-cost-aware-path-map.md`
- Modify at closeout: `docs/goals/project-completion-state.md`
- Modify at closeout: `docs/roadmap.md`
- Modify at closeout: `docs/runbook.md`

## Task 1: Liquid Universe Preset

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/universe_presets.py`
- Test: `tests/test_universe_presets.py`

- [x] **Step 1: Write RED tests**

Create tests that assert:

- `resolve_universe_symbols(["BTC/USDT"], universe_preset="liquid-usdm-top20", max_symbols=3)` returns `["BTC/USDT", "ETH/USDT", "BNB/USDT"]`.
- Explicit duplicates like `BTCUSDT` and `BTC/USDT` dedupe by exchange symbol.
- Unknown presets raise `ValueError`.
- `max_symbols=0` raises `ValueError`.

Run:

```bash
uv run --extra dev pytest tests/test_universe_presets.py -q
```

Expected: FAIL because the module does not exist.

- [x] **Step 2: Implement the module**

Add:

- `LIQUID_USDM_TOP20_SYMBOLS`
- `resolve_universe_symbols(symbols, universe_preset=None, max_symbols=None)`

The function returns slash-form symbols, preserves explicit symbol priority, and
then appends preset symbols until the optional cap is reached.

- [x] **Step 3: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_universe_presets.py -q
```

Expected: PASS.

## Task 2: Cost-Aware Feasibility Filter

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
- Test: `tests/test_multi_hypothesis_feasibility.py`

- [x] **Step 1: Write RED tests**

Add tests that seed weak noisy candles and assert:

- Without `cost_aware_execution`, the candidate keeps raw observations.
- With `cost_aware_execution=True` and
  `min_edge_over_cost_multiplier=2.0`, low-signal observations are filtered.
- The metric reports `raw_sample_count > sample_count`.
- The validation policy reports `cost_aware_execution=True` and multiplier
  `2.0`.
- Filtering that removes too many observations blocks with
  `insufficient_samples`.

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py::test_multi_hypothesis_lab_cost_aware_filter_reduces_low_edge_turnover -q
```

Expected: FAIL because the new fields and parameters do not exist.

- [x] **Step 2: Implement policy and observation fields**

Extend:

- `_Observation(signal_score: float)`
- `FeasibilityValidationPolicy.cost_aware_execution`
- `FeasibilityValidationPolicy.min_edge_over_cost_multiplier`
- `CandidateFeasibilityMetric.raw_sample_count`
- `CandidateFeasibilityMetric.cost_aware_sample_count`

Default behavior must match Round 23 when `cost_aware_execution=False`.

- [x] **Step 3: Implement filtering**

Add `_filter_cost_aware_observations(observations, cost_bps, policy)`.
Use baseline cost for the main candidate metric and each grid cost for cost
sensitivity.

- [x] **Step 4: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py -q
```

Expected: PASS.

## Task 3: Turnover Gate

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
- Test: `tests/test_multi_hypothesis_feasibility.py`

- [x] **Step 1: Write RED tests**

Add a test that seeds alternating selected-symbol observations for
`cross_asset_ranking_turnover_cap` and asserts:

- `max_turnover=0.05` blocks the candidate.
- Reason codes include `excessive_turnover`.
- `candidate_state_target` is `redesign_required`.
- The policy records `max_turnover=0.05`.

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py::test_multi_hypothesis_lab_blocks_excessive_turnover -q
```

Expected: FAIL because `max_turnover` and `excessive_turnover` do not exist.

- [x] **Step 2: Implement turnover gate**

Add `max_turnover: float | None` to the policy and
`"excessive_turnover"` to `MultiHypothesisBlockedReason`. When the metric
turnover exceeds the configured cap, block the candidate.

- [x] **Step 3: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py -q
```

Expected: PASS.

## Task 4: CLI Wiring

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `tests/test_cli_multi_hypothesis_feasibility.py`
- Modify: `tests/test_cli_evidence_universe_lab.py`
- Modify: `tests/test_cli_data_depth_campaign.py`
- Modify: `tests/test_documentation_contract.py`

- [x] **Step 1: Write RED CLI tests**

Add representative parse/run tests that assert:

- `strategy-feasibility --mode multi-hypothesis-lab` accepts
  `--cost-aware-execution`, `--min-edge-over-cost-multiplier`, and
  `--max-turnover`.
- `data-depth-campaign` accepts `--universe-preset liquid-usdm-top20
  --max-symbols 3` and writes a report using the expanded symbol list.
- `evidence-universe-lab` threads the same options into feasibility output.

Run:

```bash
uv run --extra dev pytest tests/test_cli_multi_hypothesis_feasibility.py tests/test_cli_evidence_universe_lab.py tests/test_cli_data_depth_campaign.py tests/test_documentation_contract.py -q
```

Expected: FAIL because CLI args do not exist.

- [x] **Step 2: Add CLI args and symbol resolution**

Add shared parser arguments and call `resolve_universe_symbols` before building
campaign specs and feasibility reports.

- [x] **Step 3: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_cli_multi_hypothesis_feasibility.py tests/test_cli_evidence_universe_lab.py tests/test_cli_data_depth_campaign.py tests/test_documentation_contract.py -q
```

Expected: PASS.

## Task 5: Bounded Round 24 Run And Closeout

**Files:**
- Create: `docs/goals/phase-reports/2026-06-09-candidate-quality-and-cost-aware-evidence-expansion-report.md`
- Create: `docs/goals/round-24-candidate-quality-cost-aware-path-map.md`
- Modify: `docs/goals/project-completion-state.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/runbook.md`

- [x] **Step 1: Run bounded lab**

Run a bounded read-only or explicitly gated collection lab using:

```bash
uv run crypto-alpha-agent evidence-universe-lab \
  --db var/research.sqlite \
  --memory var/memory/candidate-state.jsonl \
  --universe-preset liquid-usdm-top20 \
  --max-symbols 8 \
  --timeframe 1h \
  --start-year 2026 \
  --start-month 1 \
  --end-year 2026 \
  --end-month 5 \
  --min-unique-months 3 \
  --min-asset-count 3 \
  --min-split-count 3 \
  --purge-gap-bars 24 \
  --cost-bps-grid 5 \
  --cost-bps-grid 10 \
  --cost-bps-grid 20 \
  --cost-bps-grid 50 \
  --cost-aware-execution \
  --min-edge-over-cost-multiplier 2 \
  --max-turnover 0.5 \
  --persist-candidate-state \
  --out-dir var/reports/evidence-universe-lab/round-24-cost-aware-main \
  --json-out var/reports/evidence-universe-lab/round-24-cost-aware-main/evidence-universe-lab.json
```

If missing market data prevents a useful run, add `--collect --allow-network`
only for the bounded symbol/month set.

- [x] **Step 2: Write closeout docs**

Record actual collection counts, candidate counts, feasibility outcome, blocker
reasons, safety boundaries, and artifact paths.

- [x] **Step 3: Run verification**

Run:

```bash
uv run --extra dev pytest tests/test_universe_presets.py tests/test_multi_hypothesis_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py tests/test_cli_evidence_universe_lab.py tests/test_cli_data_depth_campaign.py tests/test_documentation_contract.py -q
uv run --extra dev pytest -q -m "not llm_integration"
uv run --extra dev ruff check .
git diff --check
```

Expected: all pass.

- [x] **Step 4: Commit and push**

Run staged secret scan before commit. Commit the Round 24 changes and push
`main`.

## Self-Review

- Spec coverage: tasks cover liquid universe expansion, cost-aware filtering,
  turnover gates, CLI wiring, runtime artifacts, and closeout docs.
- Completion marker scan: no incomplete markers are present.
- Type consistency: policy fields and metric fields are named consistently
  across tests, implementation, CLI, and reports.
