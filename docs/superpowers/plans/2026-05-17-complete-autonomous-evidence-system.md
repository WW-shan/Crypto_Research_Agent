# Complete Autonomous Evidence System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining path from the current safe evidence factory to an autonomous, low-capital, profit-first crypto alpha research system that continuously ingests public data, validates strategy families, accumulates paper evidence, uses AI to propose bounded experiments, and produces daily/weekly operator decisions without live trading.

**Architecture:** Keep the charter as the hard boundary: public data, local SQLite, deterministic validators, paper simulation, long-term memory, and human-gated tiny-live readiness artifacts only. Build a strategy registry and daily evidence runner around existing components so new strategy families plug into the same ingestion, validation, paper, report, memory, and rollout pipeline. LLMs are research planners and critics; they can propose experiments against registered validators but cannot invent data, bypass gates, or create live execution authority.

**Tech Stack:** Python 3.12, uv, pytest, ruff, Pydantic, SQLite stdlib, LangGraph, ccxt, requests, existing VectorBT/Backtrader wrappers, existing JSONL memory store, existing CLI and Markdown report modules.

---

## Governing Constraints

The binding constraints are in `docs/project-charter.md`:

- Owner has only a few hundred USD.
- Ordinary public APIs/RPC only.
- No speed edge, no MEV, no private RPC, no mempool, no bridge races, no flash-loan races.
- No wallet keys, live order routing, exchange order submission, or real capital.
- Research and paper validation come before any tiny-live readiness review.
- The system must preserve failed evidence and avoid retesting rejected assumptions.

This plan deliberately does not implement live trading. It completes the system up to repeated paper evidence and tiny-live review artifacts. Any live adapter remains blocked until a future explicit charter revision.

## Current State Audit

Already implemented:

- Real data foundations: Binance Public Data, CCXT OHLCV/funding, DexScreener, DefiLlama clients, SQLite `ResearchDataStore`.
- Stored-data research loop: scanner signals, anomaly ranking, hypotheses, validation summaries, Markdown report.
- Paper evidence factory: strict evidence models, paper outcome ledger, funding extremity plus price confirmation validator, walk-forward gate, `paper-sim-loop`, paper evidence report section, paper evidence memory.
- Safety: charter guard, risk guardian, rollout gates, tiny-live readiness artifact, paper-only Hummingbot/Freqtrade adapter boundary.
- LLM research foundation: strict task/proposal contracts, guarded LLM research node, LangGraph routing, memory persistence for LLM output.

Observed gaps from docs/code comparison:

- Scheduler is only a dry-run plan and does not execute the daily evidence sequence.
- `research-loop --include-validation` currently summarizes only close momentum over candles; it does not run the funding-plus-price validator or strategy registry.
- Only one paper-sim strategy family is implemented: `funding_extremity_price_confirmation`.
- DexScreener and DefiLlama clients exist, but their network results are not persisted by `ingest`.
- Dune and TheGraph clients exist as tools, but they are not part of stored-data evidence production. This plan adds them only as optional slow research evidence sources; they must never become execution or speed edges.
- There is no unified strategy registry, validator selector, or strategy-family report contract.
- There is no daily/weekly evidence trend report, degradation detector, or automatic "stop testing this" decision.
- Research hypotheses are persistable through `persist_research_loop_memory`, but `research-loop` CLI has no `--memory` option.
- LLMs do not yet read paper evidence and memory to propose bounded next experiments.
- Rollout gates exist, but there is no command that converts accumulated `PaperSimulationOutcome` rows into rollout observations and readiness artifacts.
- README/runbook/roadmap are partially behind the current paper evidence factory.
- Local hygiene is incomplete: `.DS_Store` files are untracked and `.gitignore` does not ignore them.

## Completion Target

This plan is complete when the repository can run this safe local loop:

```bash
uv run --extra dev crypto-alpha-agent evidence-run \
  --db var/research.sqlite \
  --memory var/memory.jsonl \
  --report-out var/reports/daily.md \
  --weekly-report-out var/reports/weekly.md \
  --current-capital-usd 300 \
  --allow-network \
  --ccxt-exchange binance \
  --symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 200
```

Expected properties:

- Pulls public OHLCV and funding data only after `--allow-network`.
- Optionally persists DefiLlama and DexScreener research snapshots when requested.
- Runs registered validators.
- Runs paper simulations only for historically approved strategy candidates.
- Writes/updates paper outcome ledger and paper memory with run-level replacement.
- Writes research-loop hypothesis memory.
- Produces daily and weekly reports.
- Runs the stored-data research loop so scanner signals, anomaly detection, hypothesis generation, deterministic reflection/accept-reject reasons, and memory persistence are part of the daily evidence product.
- Produces a machine-readable evidence decision with reason codes.
- Does not touch wallets, exchange orders, live capital, or private RPC.

The local scheduler intentionally remains dry-run. Autonomy is achieved by making `evidence-run` a safe one-shot command that can be called by an external operator-controlled cron/systemd/GitHub Actions job. This keeps process scheduling outside the agent while the evidence workflow itself is automated and repeatable.

## File Map

Create:

- `src/crypto_alpha_agent/strategy/__init__.py`
- `src/crypto_alpha_agent/strategy/registry.py`
- `src/crypto_alpha_agent/strategy/models.py`
- `src/crypto_alpha_agent/strategy/funding_mean_reversion.py`
- `src/crypto_alpha_agent/strategy/defi_yield_regime.py`
- `src/crypto_alpha_agent/strategy/dex_liquidity_watchlist.py`
- `src/crypto_alpha_agent/pipeline/evidence_runner.py`
- `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- `src/crypto_alpha_agent/pipeline/experiment_planner.py`
- `src/crypto_alpha_agent/evidence/validation_ledger.py`
- `src/crypto_alpha_agent/data/quality.py`
- `src/crypto_alpha_agent/data/onchain_ingestion.py`
- `tests/test_strategy_registry.py`
- `tests/test_research_loop_strategy_validation.py`
- `tests/test_defillama_dex_ingestion_service.py`
- `tests/test_onchain_ingestion_service.py`
- `tests/test_data_quality_reports.py`
- `tests/test_validation_evidence_ledger.py`
- `tests/test_validation_memory.py`
- `tests/test_funding_mean_reversion_strategy.py`
- `tests/test_defi_yield_regime_strategy.py`
- `tests/test_dex_liquidity_watchlist_strategy.py`
- `tests/test_evidence_runner.py`
- `tests/test_evidence_reports.py`
- `tests/test_evidence_degradation.py`
- `tests/test_research_loop_memory_cli.py`
- `tests/test_ai_experiment_planner.py`
- `tests/test_rollout_readiness_cli.py`
- `tests/test_documentation_contract.py`
- `tests/test_complete_evidence_system.py`

Modify:

- `src/crypto_alpha_agent/cli.py`
- `src/crypto_alpha_agent/data/ingestion.py`
- `src/crypto_alpha_agent/data/models.py`
- `src/crypto_alpha_agent/data/store.py`
- `src/crypto_alpha_agent/pipeline/research_loop.py`
- `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- `src/crypto_alpha_agent/pipeline/markdown.py`
- `src/crypto_alpha_agent/pipeline/memory.py`
- `src/crypto_alpha_agent/orchestrator.py`
- `src/crypto_alpha_agent/scheduler.py`
- `src/crypto_alpha_agent/evidence/__init__.py`
- `src/crypto_alpha_agent/risk/paper_gate.py`
- `src/crypto_alpha_agent/risk/rollout.py`
- `src/crypto_alpha_agent/evidence/live_readiness.py`
- `docs/roadmap.md`
- `docs/runbook.md`
- `docs/rollout-gates.md`
- `docs/tiny-live-readiness.md`
- `README.md`
- `.gitignore`
- `tests/test_cli_smoke.py`
- `tests/test_scheduler_cli.py`

---

## Phase A: Hygiene And Documentation Truth Alignment

### Task 1: Repository Hygiene And Ignore Rules

**Files:**
- Modify: `.gitignore`
- Modify: `docs/roadmap.md`
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Test: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write failing hygiene expectations**

Add a test to `tests/test_cli_smoke.py`:

```python
from pathlib import Path


def test_repo_ignores_local_macos_and_cache_artifacts():
    ignore_text = Path(".gitignore").read_text(encoding="utf-8")

    assert ".DS_Store" in ignore_text
    assert ".ruff_cache/" in ignore_text
    assert ".venv/" in ignore_text
```

- [ ] **Step 2: Verify red**

Run:

```bash
uv run --extra dev pytest tests/test_cli_smoke.py::test_repo_ignores_local_macos_and_cache_artifacts -q
```

Expected: FAIL because `.DS_Store`, `.ruff_cache/`, or `.venv/` is not ignored.

- [ ] **Step 3: Implement ignore rules**

Update `.gitignore` to include:

```gitignore
.DS_Store
**/.DS_Store
.ruff_cache/
.venv/
.worktrees/
__pycache__/
.pytest_cache/
*.pyc
var/
```

Remove untracked `.DS_Store` files from the working tree with `rm .DS_Store docs/.DS_Store src/.DS_Store src/crypto_alpha_agent/.DS_Store`.

- [ ] **Step 4: Update docs to current truth**

Update docs so they explicitly say:

- Funding-plus-price validator and hard walk-forward gate are implemented for the first strategy family.
- Scheduler is still dry-run before this plan.
- Active work is now "complete autonomous evidence system".
- README includes the current safe paper memory workflow from `docs/runbook.md`.

- [ ] **Step 5: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_cli_smoke.py -q
uv run --extra dev ruff check tests/test_cli_smoke.py
git status --short --ignored
git diff --check
```

Commit:

```bash
git add .gitignore README.md docs/roadmap.md docs/runbook.md tests/test_cli_smoke.py
git commit -m "docs: align roadmap with evidence factory state"
```

**Exit criteria:** Local generated artifacts are ignored, docs no longer imply missing components that already exist, and README describes the latest safe workflow.

---

## Phase B: Complete Real Data Persistence

### Task 2: Persist DexScreener And DefiLlama Ingestion

**Files:**
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_defillama_dex_ingestion_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_defillama_dex_ingestion_service.py` with tests that assert:

- `ingest_dexscreener_pairs(db_path, query="USDC", allow_network=True, client=fake)` writes `record_type="dex_pair"` rows.
- Low-liquidity DEX pairs persist as research-only suitability payloads.
- `ingest_defillama_yield_pools(db_path, min_tvl_usd=10000, allow_network=True, client=fake)` writes `record_type="defi_yield"` rows.
- CLI rejects `--source dexscreener` and `--source defillama` without `--allow-network`.
- CLI with `--source dexscreener --query USDC --allow-network` writes records.
- CLI with `--source defillama --min-tvl-usd 10000 --allow-network` writes records.

Use fake clients with deterministic snapshots; do not hit network in tests.

- [ ] **Step 2: Verify red**

Run:

```bash
uv run --extra dev pytest tests/test_defillama_dex_ingestion_service.py -q
```

Expected: FAIL because the ingestion services and CLI flags do not exist.

- [ ] **Step 3: Implement services**

Add functions to `src/crypto_alpha_agent/data/ingestion.py`:

- `ingest_dexscreener_pairs(db_path, query, allow_network=False, client=None)`
- `ingest_defillama_yield_pools(db_path, min_tvl_usd=10000.0, allow_network=False, client=None)`

Both return strict summary models with:

- `source`
- `db_path`
- `feed`
- `records_fetched`
- `records_written`
- `network_allowed`
- `uses_real_capital=False`
- `live_order_routing=False`

Record IDs must include source, chain/project/dex/pair/token identity, and observed timestamp so repeated sources do not overwrite unrelated rows.

- [ ] **Step 4: Wire CLI**

Extend `ingest` flags:

- `--query` for DexScreener search.
- `--chain` and `--token-address` for DexScreener token lookup.
- `--min-tvl-usd` for DefiLlama yield pools.

Rules:

- `--source dexscreener` requires `--allow-network` and either `--query` or both `--chain` plus at least one `--token-address`.
- `--source defillama` requires `--allow-network`.
- Do not allow combining CCXT-specific flags with DEX/DeFi sources.

- [ ] **Step 5: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_defillama_dex_ingestion_service.py tests/test_dex_defillama_collectors.py tests/test_scanner_bridge_low_capital.py tests/test_cli_ingest.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/data/ingestion.py src/crypto_alpha_agent/cli.py tests/test_defillama_dex_ingestion_service.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/data/ingestion.py src/crypto_alpha_agent/cli.py tests/test_defillama_dex_ingestion_service.py
git commit -m "feat: persist dex and defi research data"
```

**Exit criteria:** DEX and DeFi discovery data become durable stored records, not only client-level objects.

### Task 2A: Optional Dune And TheGraph Slow Evidence Persistence

**Files:**
- Create: `src/crypto_alpha_agent/data/onchain_ingestion.py`
- Modify: `src/crypto_alpha_agent/data/models.py`
- Modify: `src/crypto_alpha_agent/data/store.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Test: `tests/test_onchain_ingestion_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_onchain_ingestion_service.py` with concrete fake clients:

```python
from datetime import UTC, datetime

from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.data.onchain_ingestion import (
    ingest_dune_query_result,
    ingest_thegraph_query_result,
)


class FakeDuneClient:
    def execute_query(self, query_id, *, params=None):
        return {
            "source": "dune",
            "query_id": query_id,
            "rows": [{"asset": "ETH", "metric": "stablecoin_inflow", "value": 123.0}],
            "raw": {"result": {"rows": [{"asset": "ETH"}]}},
        }


class FakeGraphClient:
    def query(self, subgraph_url, query, *, variables=None):
        return {
            "source": "thegraph",
            "subgraph_url": subgraph_url,
            "data": {"pools": [{"id": "pool-1", "liquidityUSD": "100000"}]},
            "raw": {"data": {"pools": []}},
        }


def test_dune_query_result_is_persisted_as_slow_research_snapshot(tmp_path):
    db_path = tmp_path / "research.sqlite"

    summary = ingest_dune_query_result(
        db_path,
        query_id=123,
        allow_network=True,
        client=FakeDuneClient(),
        observed_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="dune")
    assert summary.records_written == 1
    assert records[0].payload["execution_role"] == "research_only"
    assert records[0].payload["live_order_routing"] is False


def test_thegraph_query_result_is_persisted_as_slow_research_snapshot(tmp_path):
    db_path = tmp_path / "research.sqlite"

    summary = ingest_thegraph_query_result(
        db_path,
        subgraph_url="https://example.test/subgraph",
        query="{ pools { id } }",
        allow_network=True,
        client=FakeGraphClient(),
        observed_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="thegraph")
    assert summary.records_written == 1
    assert records[0].payload["latency_dependency"] == "low"
```

Also add CLI tests:

- `ingest --source dune` requires `--allow-network`, `--dune-query-id`, and `--dune-api-key` unless a test monkeypatch supplies a fake client.
- `ingest --source thegraph` requires `--allow-network`, `--subgraph-url`, and `--graph-query`.
- Dune/TheGraph flags cannot be combined with CCXT execution/data flags.

- [ ] **Step 2: Verify red**

Run:

```bash
uv run --extra dev pytest tests/test_onchain_ingestion_service.py -q
```

Expected: FAIL because `research_snapshot` and the ingestion services are missing.

- [ ] **Step 3: Extend record model**

Add `"research_snapshot"` to `RecordType` in `src/crypto_alpha_agent/data/models.py`.

Payload requirements for slow on-chain/fundamental snapshots:

- `source`: `dune` or `thegraph`
- `observed_at`
- `query_ref`: Dune query id or subgraph URL hash
- `rows` or `data`
- `execution_role="research_only"`
- `latency_dependency="low"`
- `rpc_dependency="none"`
- `uses_real_capital=False`
- `live_order_routing=False`
- `blocked_reasons=[]`

- [ ] **Step 4: Implement ingestion services**

Create `src/crypto_alpha_agent/data/onchain_ingestion.py` with:

- `SlowEvidenceIngestionSummary`
- `ingest_dune_query_result(db_path, query_id, allow_network=False, api_key=None, client=None, params=None, observed_at=None)`
- `ingest_thegraph_query_result(db_path, subgraph_url, query, allow_network=False, client=None, variables=None, observed_at=None)`

Record IDs must include source, query identifier hash, and observed date/time so unrelated queries do not overwrite each other.

- [ ] **Step 5: Wire CLI safely**

Extend `ingest --source` choices with `dune` and `thegraph`.

Add:

- `--dune-query-id`
- `--dune-api-key`
- `--dune-param KEY=VALUE` repeated
- `--subgraph-url`
- `--graph-query`
- `--graph-variable KEY=VALUE` repeated

Rules:

- Dune is optional and may require an API key; absence of a key must block with a clear error, not fall back to scraping.
- TheGraph is optional and must be used for slow research snapshots only.
- Both sources require `--allow-network`.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_onchain_ingestion_service.py tests/test_tools_normalization.py tests/test_tool_retries.py tests/test_cli_ingest.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/data/onchain_ingestion.py src/crypto_alpha_agent/data/models.py src/crypto_alpha_agent/data/store.py src/crypto_alpha_agent/pipeline/research_loop.py src/crypto_alpha_agent/cli.py tests/test_onchain_ingestion_service.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/data/onchain_ingestion.py src/crypto_alpha_agent/data/models.py src/crypto_alpha_agent/data/store.py src/crypto_alpha_agent/pipeline/research_loop.py src/crypto_alpha_agent/cli.py tests/test_onchain_ingestion_service.py
git commit -m "feat: persist slow onchain research evidence"
```

**Exit criteria:** Dune and TheGraph can feed durable slow research evidence when explicitly configured, while staying research-only and optional.

### Task 3: Data Quality And Source Health Reports

**Files:**
- Create/Modify: `src/crypto_alpha_agent/data/quality.py`
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Test: `tests/test_data_quality_reports.py`

- [ ] **Step 1: Write failing tests**

Create tests for:

- Missing timestamp gaps on OHLCV series.
- Duplicate source records by semantic key.
- Stale latest record relative to a supplied `now`.
- Non-positive prices/volumes flagged.
- Source health rows written after ingestion success/failure.
- Markdown report includes a `## Data Quality` section.

- [ ] **Step 2: Implement models**

Create:

- `DataQualityIssue`
- `DataQualityReport`
- `SourceHealthSnapshot`
- `build_data_quality_report(records, now)`

Reason codes:

- `missing_ohlcv_bars`
- `duplicate_semantic_record`
- `stale_source`
- `non_positive_price`
- `zero_volume`
- `source_error`

- [ ] **Step 3: Persist health snapshots**

Represent source health as `SourceRecord(record_type="source_health")` with payload including:

- source
- feed
- success
- attempts
- failure
- observed_at
- records_fetched
- records_written

- [ ] **Step 4: Attach quality reports**

Add `data_quality_reports` to `ResearchLoopReport` and render it in Markdown.

- [ ] **Step 5: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_data_quality_reports.py tests/test_research_loop_pipeline.py tests/test_cli_research_loop.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/data src/crypto_alpha_agent/pipeline tests/test_data_quality_reports.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/data src/crypto_alpha_agent/pipeline tests/test_data_quality_reports.py
git commit -m "feat: report research data quality"
```

**Exit criteria:** Every daily report can say whether the evidence is based on fresh, complete, non-duplicated data.

---

## Phase C: Strategy Registry And Unified Validation

### Task 4: Strategy Registry Interface

**Files:**
- Create: `src/crypto_alpha_agent/strategy/models.py`
- Create: `src/crypto_alpha_agent/strategy/registry.py`
- Create: `src/crypto_alpha_agent/strategy/__init__.py`
- Test: `tests/test_strategy_registry.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- Registry lists available strategy families.
- Unknown family fails closed.
- A strategy spec declares required record types, required symbols, validator, paper simulator support, and low-capital constraints.
- Strategy specs cannot declare speed edge, premium RPC, live routing, or min capital above configured capital.

- [ ] **Step 2: Implement models**

Create strict Pydantic models:

- `StrategyFamilySpec`
- `StrategyValidationRequest`
- `StrategyValidationReport`
- `StrategyPaperRequest`
- `StrategyPaperReport`

Required fields:

- strategy_family
- display_name
- required_record_types
- supports_paper_simulation
- min_capital_usd
- max_notional_usd
- requires_speed_edge=False
- requires_premium_rpc=False
- live_order_routing=False
- validator_name
- blocked_reasons

- [ ] **Step 3: Implement registry**

Create:

- `StrategyRegistry.register(spec, validator, paper_runner=None)`
- `StrategyRegistry.get(strategy_family)`
- `StrategyRegistry.validate(request)`
- `StrategyRegistry.run_paper(request)`
- `default_strategy_registry()`

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_registry.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/strategy tests/test_strategy_registry.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/strategy tests/test_strategy_registry.py
git commit -m "feat: add strategy registry"
```

**Exit criteria:** New strategy families have one safe interface instead of ad hoc CLI-specific code.

### Task 5: Register Existing Funding-Price Strategy And Use It In Research Reports

**Files:**
- Modify: `src/crypto_alpha_agent/strategy/registry.py`
- Modify: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_research_loop_strategy_validation.py`

- [ ] **Step 1: Write failing tests**

Tests must assert:

- `research-loop --include-validation --strategy-family funding_extremity_price_confirmation --price-symbol BTC/USDT --funding-symbol BTC/USDT:USDT --validation-timeframe 1h` returns a validation summary from `validate_funding_price_confirmation`.
- The summary includes walk-forward split count, pass rate, blocked reasons, fees, slippage, net return, max drawdown.
- If funding data is missing, the summary is blocked with `insufficient_funding_samples`.
- Markdown report names the strategy family and blocked reasons.

- [ ] **Step 2: Wire CLI flags**

Add optional research-loop flags:

- `--strategy-family`
- `--price-symbol`
- `--funding-symbol`
- `--validation-timeframe`
- `--threshold-abs`
- `--hold-bars`
- `--fee-rate`
- `--slippage-rate`
- `--min-trades`

Rules:

- If `--strategy-family` is supplied, validation uses the strategy registry.
- If not supplied, keep existing close-momentum validation for backward compatibility and mark it as `baseline_only`.

- [ ] **Step 3: Implement validation mapping**

Convert `FundingPriceValidationResult` into `ValidationSummary` without losing:

- `walk_forward_split_count`
- `walk_forward_pass_rate`
- `gross_expectancy`
- `fee_adjusted_expectancy`
- `slippage_adjusted_expectancy`
- `blocked_reasons`

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_research_loop_strategy_validation.py tests/test_research_loop_validation_summary.py tests/test_funding_price_validator.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/strategy src/crypto_alpha_agent/pipeline src/crypto_alpha_agent/cli.py tests/test_research_loop_strategy_validation.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/strategy src/crypto_alpha_agent/pipeline src/crypto_alpha_agent/cli.py tests/test_research_loop_strategy_validation.py
git commit -m "feat: validate registered strategies in research loop"
```

**Exit criteria:** Research reports and paper simulations talk about the same strategy-family evidence instead of separate baseline summaries.

### Task 6: Validation Evidence Ledger

**Files:**
- Create: `src/crypto_alpha_agent/evidence/validation_ledger.py`
- Modify: `src/crypto_alpha_agent/evidence/__init__.py`
- Modify: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Test: `tests/test_validation_evidence_ledger.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- Upsert and load `ValidationEvidence` rows.
- Replace by `run_id` and strategy family without deleting other runs.
- Failed validation evidence is persisted with blocked reasons.
- Research loop writes validation evidence when `--include-validation` is used with a registered strategy.

- [ ] **Step 2: Implement ledger**

Create table `validation_evidence` with:

- evidence_id primary key
- run_id
- strategy_family
- symbol
- timeframe
- approved
- blocked_reasons_json
- payload_json
- inserted_at

Methods:

- `upsert_evidence(items)`
- `replace_run_evidence(run_id, items)`
- `load_evidence(strategy_family=None, symbol=None, run_id=None)`

- [ ] **Step 3: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_validation_evidence_ledger.py tests/test_evidence_models.py tests/test_research_loop_strategy_validation.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/evidence src/crypto_alpha_agent/pipeline tests/test_validation_evidence_ledger.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/evidence src/crypto_alpha_agent/pipeline tests/test_validation_evidence_ledger.py
git commit -m "feat: persist validation evidence"
```

**Exit criteria:** Historical validation failures and approvals are durable evidence, not transient report fields.

### Task 6A: Validation Evidence Memory Feedback

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/memory.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_validation_memory.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_validation_memory.py`:

```python
from crypto_alpha_agent.evidence.models import ValidationEvidence
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.memory import persist_validation_evidence_memory


def test_blocked_validation_evidence_is_persisted_to_memory(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence = ValidationEvidence(
        strategy_family="funding_extremity_price_confirmation",
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price",
        trade_count=0,
        net_return=0.0,
        gross_expectancy=0.0,
        fee_adjusted_expectancy=0.0,
        slippage_adjusted_expectancy=0.0,
        max_drawdown=0.0,
        walk_forward_split_count=0,
        walk_forward_pass_rate=0.0,
        approved=False,
        blocked_reasons=["insufficient_walk_forward_splits", "non_positive_net_return"],
    )

    stored = persist_validation_evidence_memory([evidence], memory_path, run_id="daily-001")
    records = MemoryStore(memory_path).list_records()

    assert len(stored) == 1
    assert records[0].record_id.startswith("validation:daily-001:")
    assert records[0].opportunity["strategy_family"] == "funding_extremity_price_confirmation"
    assert "validation-evidence" in records[0].tags
    assert "insufficient_walk_forward_splits" in records[0].rejected_reasons
    assert records[0].hypothesis["lesson"] == "validation_blocked"


def test_approved_validation_evidence_memory_has_no_rejected_reasons(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence = ValidationEvidence(
        strategy_family="funding_extremity_price_confirmation",
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price",
        trade_count=30,
        net_return=0.05,
        gross_expectancy=0.003,
        fee_adjusted_expectancy=0.002,
        slippage_adjusted_expectancy=0.001,
        max_drawdown=0.02,
        walk_forward_split_count=3,
        walk_forward_pass_rate=1.0,
        approved=True,
        blocked_reasons=[],
    )

    persist_validation_evidence_memory([evidence], memory_path, run_id="daily-001")

    record = MemoryStore(memory_path).list_records()[0]
    assert record.rejected_reasons == []
    assert record.hypothesis["lesson"] == "validation_approved"
```

- [ ] **Step 2: Verify red**

Run:

```bash
uv run --extra dev pytest tests/test_validation_memory.py -q
```

Expected: FAIL because `persist_validation_evidence_memory` is missing.

- [ ] **Step 3: Implement memory persistence**

Add `persist_validation_evidence_memory(evidence_items, memory_path, run_id)`:

- one memory record per validation evidence item
- record id: `validation:<run_id>:<evidence_id>`
- tags: `validation-evidence`, strategy family, symbol slug, `approved` or `blocked`, run id
- opportunity: strategy family, symbol, timeframe, validator, run id, live flags false
- hypothesis: lesson, metrics, blocked reasons, disconfirmation hints
- score: trade count, expectancy fields, drawdown, walk-forward fields
- rejected reasons: blocked reasons if not approved, else `[]`

- [ ] **Step 4: Wire callers**

When `research-loop --memory` is added in Task 12, it must call both:

- `persist_research_loop_memory`
- `persist_validation_evidence_memory` when validation evidence exists

When `evidence-run` is added in Task 10, it must write validation memory before experiment planning.

- [ ] **Step 5: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_validation_memory.py tests/test_research_loop_memory.py tests/test_evidence_models.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/pipeline/memory.py tests/test_validation_memory.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/pipeline/memory.py tests/test_validation_memory.py
git commit -m "feat: persist validation lessons to memory"
```

**Exit criteria:** Failed validation lessons become durable memory for future experiment planning.

---

## Phase D: Broader Low-Capital Strategy Families

### Task 7: Funding Mean Reversion Strategy Family

**Files:**
- Create: `src/crypto_alpha_agent/strategy/funding_mean_reversion.py`
- Modify: `src/crypto_alpha_agent/strategy/registry.py`
- Modify: `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- Test: `tests/test_funding_mean_reversion_strategy.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- Positive extreme funding followed by price drop creates short mean-reversion trade.
- Negative extreme funding followed by price bounce creates long mean-reversion trade.
- OI is optional; if unavailable, result includes `missing_open_interest_confirmation` note but does not crash.
- Fee/slippage-adjusted expectancy must be positive for approval.
- Walk-forward gate is required by default.
- Duplicate timestamps and non-positive prices fail closed.

- [ ] **Step 2: Implement validator**

Create:

- `validate_funding_mean_reversion(db_path, price_symbol, funding_symbol, timeframe, threshold_abs, hold_bars, fee_rate, slippage_rate, min_trades, require_walk_forward=True, ...)`

Return `StrategyValidationReport` with strategy family `funding_mean_reversion_after_extreme`.

- [ ] **Step 3: Implement paper extraction**

Add deterministic paper trade extraction and paper outcomes using the same shared ID rules as the existing paper loop. Update `run_paper_sim_loop(...)` so it dispatches through the strategy registry instead of the current single-family constant, while preserving backward compatibility for `funding_extremity_price_confirmation`.

- [ ] **Step 4: Register strategy**

Add to `default_strategy_registry()`.

- [ ] **Step 5: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_funding_mean_reversion_strategy.py tests/test_strategy_registry.py tests/test_paper_sim_loop.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/strategy src/crypto_alpha_agent/pipeline/paper_sim_loop.py tests/test_funding_mean_reversion_strategy.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/strategy src/crypto_alpha_agent/pipeline/paper_sim_loop.py tests/test_funding_mean_reversion_strategy.py
git commit -m "feat: add funding mean reversion strategy"
```

**Exit criteria:** The second low-capital funding strategy family can be validated and paper-simulated through the registry.

### Task 8: DeFi Yield Regime Watchlist Strategy

**Files:**
- Create: `src/crypto_alpha_agent/strategy/defi_yield_regime.py`
- Modify: `src/crypto_alpha_agent/strategy/registry.py`
- Test: `tests/test_defi_yield_regime_strategy.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- APY jump with sufficient TVL creates a research watchlist candidate.
- Low TVL blocks with `insufficient_tvl`.
- Missing prior observations blocks with `insufficient_history`.
- Strategy is `research_only` or `paper_watchlist_only`, not execution.
- No paper closed trades are created for DeFi yield watchlist.

- [ ] **Step 2: Implement validator**

Create:

- `validate_defi_yield_regime(records, min_tvl_usd=100000, min_apy_change=1.0, min_observations=2)`

Outputs:

- strategy_family `defi_yield_regime_watchlist`
- approved only for watchlist/reporting
- blocked reasons for low TVL, missing history, stale source, unsupported chain

- [ ] **Step 3: Register as watchlist-only**

Registry spec must set:

- `supports_paper_simulation=False`
- `execution_role="research_only"`

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_defi_yield_regime_strategy.py tests/test_scanner_bridge_low_capital.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/strategy tests/test_defi_yield_regime_strategy.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/strategy tests/test_defi_yield_regime_strategy.py
git commit -m "feat: add defi yield regime watchlist"
```

**Exit criteria:** DeFi fundamentals can generate validated watchlist evidence without pretending to be executable.

### Task 9: DEX Liquidity And Volume Watchlist Strategy

**Files:**
- Create: `src/crypto_alpha_agent/strategy/dex_liquidity_watchlist.py`
- Modify: `src/crypto_alpha_agent/strategy/registry.py`
- Test: `tests/test_dex_liquidity_watchlist_strategy.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- Liquidity and volume increase with sufficient liquidity creates a watchlist candidate.
- Thin liquidity blocks with `insufficient_liquidity`.
- Any strategy requiring direct DEX execution is blocked.
- The strategy records `research_only` and no live routing.

- [ ] **Step 2: Implement validator**

Create:

- `validate_dex_liquidity_watchlist(records, min_liquidity_usd=100000, min_volume_24h_usd=10000, min_observations=2)`

- [ ] **Step 3: Register as watchlist-only**

Use `supports_paper_simulation=False`.

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_dex_liquidity_watchlist_strategy.py tests/test_dex_defillama_collectors.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/strategy tests/test_dex_liquidity_watchlist_strategy.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/strategy tests/test_dex_liquidity_watchlist_strategy.py
git commit -m "feat: add dex liquidity watchlist strategy"
```

**Exit criteria:** DEX data becomes slow discovery evidence, not a false CEX-DEX race target.

---

## Phase E: Daily Evidence Runner

### Task 10: Safe Evidence Runner Pipeline

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/evidence_runner.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_evidence_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_evidence_runner.py` with these concrete checks:

```python
def test_evidence_runner_executes_complete_research_milestone(tmp_path, fake_ccxt_collector):
    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "daily.md",
        current_capital_usd=300.0,
        allow_network=True,
        ccxt_collector=fake_ccxt_collector,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        strategy_families=["funding_extremity_price_confirmation"],
    )

    assert [step.name for step in report.steps] == [
        "ingest_ccxt_ohlcv",
        "ingest_ccxt_funding",
        "research_loop",
        "strategy_validation",
        "validation_memory",
        "paper_simulation",
        "paper_memory",
        "daily_report",
    ]
    assert report.research_milestone.signal_count > 0
    assert report.research_milestone.anomaly_count > 0
    assert report.research_milestone.hypothesis_count > 0
    assert report.research_milestone.accept_reject_reason_count > 0
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
```

Also add tests:

- `test_evidence_runner_blocks_network_sources_without_allow_network`: fake collector must not be called.
- `test_evidence_runner_writes_blocked_paper_outcome_when_validation_blocks`: ledger contains only blocked outcomes and memory contains the validation blockers.
- `test_evidence_runner_records_source_health_on_optional_source_failure`: optional DEX/DeFi/Dune/TheGraph failures become source health and report notes, not crashes that hide prior evidence.
- `test_evidence_run_cli_outputs_safe_json_and_writes_report`: JSON payload includes `uses_real_capital=False`, `live_order_routing=False`, `memory_records_written`, and ordered step statuses.

- [ ] **Step 2: Implement model**

Create:

- `EvidenceRunnerStep`
- `EvidenceRunnerReport`
- `run_daily_evidence_pipeline(...)`

Required report fields:

- run_id
- started_at
- db_path
- memory_path
- strategy_families
- steps
- records_written
- validation_evidence_written
- paper_outcomes_written
- memory_records_written
- report_artifact
- research_milestone with loaded records, signal count, anomaly count, hypothesis count, reflection count, accept/reject reason count
- source_health with optional_source_skipped and optional_source_failures counts
- decision reason codes
- uses_real_capital=False
- live_order_routing=False

`run_daily_evidence_pipeline` must call `run_stored_research_loop(...)` after ingestion and before strategy validation. It must pass strategy validation parameters through to the research loop, including `price_symbol`, `funding_symbol`, and `validation_timeframe`; the daily runner's `--timeframe` CLI argument is the CCXT OHLCV ingestion timeframe and must also be used as the default validation timeframe unless an internal caller overrides it. It must persist both research-loop memory and validation evidence memory. Deterministic reflection can be implemented as a small summary over hypotheses, validation evidence, and paper evidence; it must produce accept/reject reasons but no orders or code execution.

Optional slow sources in the daily runner:

- Dune/TheGraph are not required for the default daily run.
- When not configured, they are recorded as `skipped/not_configured`, not failures.
- When explicitly configured through CLI flags, the runner calls the Task 2A ingestion services and records success or failure as source-health evidence.
- A configured optional source failure must not hide previously ingested core CCXT evidence.

Implementation detail for testability:

- Import ingestion modules rather than binding network functions at module import time, so tests can monkeypatch fake collectors.
- `run_daily_evidence_pipeline(...)` accepts optional `ccxt_collector`, `dex_client`, `defillama_client`, `dune_client`, and `thegraph_client` parameters.
- Create `build_ccxt_collector(exchange_id)` in `evidence_runner.py`; CLI execution uses that factory and tests monkeypatch it to avoid real network calls.
- CLI handlers pass `None` for these optional clients; tests pass fakes.
- The runner records optional-source failures as `source_health` and continues to validation/reporting when core stored market data is available.

- [ ] **Step 3: Wire CLI**

Add command `evidence-run`:

- `--db`
- `--memory`
- `--report-out`
- `--current-capital-usd`
- `--allow-network`
- `--ccxt-exchange`
- `--symbol`
- `--funding-symbol`
- `--timeframe`
- `--limit`
- `--strategy-family` repeated, default `funding_extremity_price_confirmation`
- `--include-defillama`
- `--include-dexscreener`
- `--dex-query`
- `--min-tvl-usd`
- `--include-dune`
- `--dune-query-id`
- `--dune-api-key`
- `--dune-param KEY=VALUE` repeated
- `--include-thegraph`
- `--subgraph-url`
- `--graph-query`
- `--graph-variable KEY=VALUE` repeated

Do not implement sleeping, cron, daemon mode, or live execution.

Do not add `--weekly-report-out` in this task. Weekly report generation is implemented and wired in Task 14 after the report builder exists.

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_runner.py tests/test_ccxt_ingestion_service.py tests/test_paper_sim_loop.py tests/test_research_loop_memory.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/pipeline/evidence_runner.py src/crypto_alpha_agent/cli.py tests/test_evidence_runner.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/pipeline/evidence_runner.py src/crypto_alpha_agent/cli.py tests/test_evidence_runner.py
git commit -m "feat: run daily evidence pipeline"
```

**Exit criteria:** The operator has one safe command that actually runs the evidence factory sequence without live trading.

### Task 11: Scheduler Execution Plan Upgrade

**Files:**
- Modify: `src/crypto_alpha_agent/scheduler.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_scheduler_cli.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- `schedule --dry-run` now plans `evidence-run`, not only `research-loop`.
- The plan includes OHLCV, funding, paper memory, validation, and report outputs.
- `schedule --dry-run` still never runs subprocesses or sleeps.
- Any non-dry-run schedule mode is rejected with a clear message.
- The returned payload explicitly says: `execution_model="external_operator_cron_calls_evidence_run"` and `scheduler_executes_commands=False`.

- [ ] **Step 2: Update scheduler plan**

Modify `build_daily_schedule_plan` so planned commands include:

- optional offline check
- `evidence-run` with configured public data source args

Keep:

- `dry_run=True`
- `runs_subprocesses=False`
- `sleeps=False`
- `uses_real_capital=False`
- `live_order_routing=False`

This is intentional. The project does not need an always-on daemon inside the agent. The safe automation boundary is an idempotent `evidence-run` command plus an external scheduler controlled by the operator.

- [ ] **Step 3: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_scheduler_cli.py tests/test_evidence_runner.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/scheduler.py src/crypto_alpha_agent/cli.py tests/test_scheduler_cli.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/scheduler.py src/crypto_alpha_agent/cli.py tests/test_scheduler_cli.py
git commit -m "feat: plan daily evidence runs"
```

**Exit criteria:** Scheduling points at the real evidence runner while remaining a dry-run operator surface.

---

## Phase F: Memory Feedback And AI Experiment Planning

### Task 12: Research Loop Memory CLI

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/pipeline/memory.py`
- Test: `tests/test_research_loop_memory_cli.py`

- [ ] **Step 1: Write failing tests**

Tests must assert:

- `research-loop --memory var/memory.jsonl` persists generated and blocked hypotheses.
- `research-loop --include-validation --strategy-family ... --memory var/memory.jsonl` persists validation evidence lessons through `persist_validation_evidence_memory`.
- JSON output includes `memory_records_written` and `memory_path`.
- JSON output includes `validation_memory_records_written` when validation evidence exists.
- Re-running the same run is idempotent by record ID.
- Empty reports do not create memory files.

- [ ] **Step 2: Wire CLI**

Add `--memory` to `research-loop` and call:

- `persist_research_loop_memory(report, args.memory)`
- `persist_validation_evidence_memory(report.validation_evidence, args.memory, run_id=report.run_id)` when registered validation evidence exists

The CLI must not create live authority. Memory records are research evidence only.

- [ ] **Step 3: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_research_loop_memory_cli.py tests/test_research_loop_memory.py tests/test_cli_research_loop.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/pipeline/memory.py tests/test_research_loop_memory_cli.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/pipeline/memory.py tests/test_research_loop_memory_cli.py
git commit -m "feat: persist research loop memory from cli"
```

**Exit criteria:** Daily research hypotheses and rejections enter long-term memory without needing a custom Python call.

### Task 13: AI Experiment Planner

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/experiment_planner.py`
- Modify: `src/crypto_alpha_agent/orchestrator.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_ai_experiment_planner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ai_experiment_planner.py` with explicit cases:

```python
def test_planner_uses_validation_memory_to_avoid_repeating_blocked_parameters(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    seed_validation_memory(
        memory_path,
        run_id="daily-001",
        strategy_family="funding_extremity_price_confirmation",
        blocked_reasons=["non_positive_net_return"],
        parameters={"threshold_abs": 0.0005, "hold_bars": 1},
    )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        strategy_family="funding_extremity_price_confirmation",
        max_proposals=2,
        current_capital_usd=300.0,
    )

    assert result.live_order_routing is False
    assert all(proposal.strategy_family == "funding_extremity_price_confirmation" for proposal in result.proposals)
    assert all(proposal.max_capital_usd <= 300.0 for proposal in result.proposals)
    assert all(proposal.parameter_changes != {"threshold_abs": 0.0005, "hold_bars": 1} for proposal in result.proposals)


def test_planner_rejects_unsafe_llm_experiment(tmp_path):
    def unsafe_llm(_task):
        return '{"strategy_family":"mev_sandwich","live_order_routing":true,"parameter_changes":{}}'

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=unsafe_llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert "charter_violation" in result.rejected_reason_codes
    assert result.proposals == []
```

Also cover:

- Planner reads recent `PaperEvidencePackage`, validation evidence, and memory records.
- Planner proposes bounded parameter experiments only for registered strategy families.
- Planner emits disconfirmation tests and stop conditions.
- Planner does not create code or orders; it creates `ExperimentProposal` objects.
- Fake LLM invalid JSON is rejected and written to memory as rejected.

- [ ] **Step 2: Implement models**

Create:

- `ExperimentProposal`
- `ExperimentBatch`
- `ExperimentPlannerInput`
- `ExperimentPlannerResult`

Required proposal fields:

- proposal_id
- strategy_family
- parameter_changes
- evidence_refs
- why_it_might_improve_edge
- disconfirmation_tests
- stop_conditions
- allowed_data_sources
- max_capital_usd
- max_notional_usd, capped at `min(25.0, current_capital_usd * 0.1)`
- live_order_routing=False

- [ ] **Step 3: Implement deterministic fallback planner**

When no LLM is supplied:

- If paper evidence is blocked for `insufficient_walk_forward_splits`, propose collecting more data.
- If `fee_killed_edge` or negative expectancy appears, propose smaller threshold sweep or mark family as degraded.
- If no evidence exists, propose baseline run for first registered funding family.
- If validation memory shows the same parameter set repeatedly failed, do not propose the identical parameters again.

- [ ] **Step 4: Add optional LLM planner node**

Extend LangGraph with a planner node that:

- receives report + memory context
- calls LLM only through strict contract
- guards output through charter guard
- stores accepted/rejected experiment proposals in memory with record ids `experiment-proposal:<batch_id>:<proposal_id>` and tag `experiment-proposal`

- [ ] **Step 5: Wire CLI**

Add command `plan-experiments`:

- `--db`
- `--memory`
- `--strategy-family`
- `--max-proposals`
- `--current-capital-usd`
- `--offline-only`

Default is deterministic offline planning.

CLI JSON output must include:

- `command="plan-experiments"`
- `current_capital_usd`
- `proposals`
- `degraded_strategy_families`
- `accepted`
- `rejected_reason_codes`
- `uses_real_capital=False`
- `live_order_routing=False`

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_ai_experiment_planner.py tests/test_llm_graph_routing.py tests/test_llm_contracts.py tests/test_charter_guard.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/pipeline/experiment_planner.py src/crypto_alpha_agent/orchestrator.py src/crypto_alpha_agent/cli.py tests/test_ai_experiment_planner.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/pipeline/experiment_planner.py src/crypto_alpha_agent/orchestrator.py src/crypto_alpha_agent/cli.py tests/test_ai_experiment_planner.py
git commit -m "feat: plan bounded evidence experiments"
```

**Exit criteria:** AI can help decide the next experiments, but only inside registered, testable, low-capital evidence lanes.

---

## Phase G: Evidence Reports, Degradation, And Stop Decisions

### Task 14: Daily And Weekly Evidence Reports

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_evidence_reports.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_evidence_reports.py` with concrete checks:

```python
def test_daily_evidence_report_includes_validation_paper_and_memory_sections(tmp_path):
    report = build_daily_evidence_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        strategy_families=["funding_extremity_price_confirmation"],
    )

    assert report.should_continue is True
    assert "validation" in report.reason_codes or report.validation_evidence_count >= 0
    assert report.paper_evidence_count >= 0
    assert report.next_experiments is not None


def test_weekly_evidence_report_aggregates_by_strategy_family(tmp_path):
    report = build_weekly_evidence_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
    )

    assert isinstance(report.family_summaries, list)
    assert report.near_tiny_live_review is False
```

Also cover:

- Daily report includes new candidates, blocked candidates, paper outcomes, validation evidence, data quality, and next experiments.
- Weekly report aggregates by strategy family.
- Weekly report includes top rejected reasons, best improving family, degraded family, and sample-size progress toward 30 observations.
- Reports explicitly say whether anything is close to paper eligibility or tiny-live review.

- [ ] **Step 2: Implement reports**

Create:

- `DailyEvidenceReport`
- `WeeklyEvidenceReport`
- `build_daily_evidence_report(...)`
- `build_weekly_evidence_report(...)`
- Markdown renderers

Decision fields:

- `should_continue`
- `should_stop_family`
- `should_collect_more_data`
- `near_paper_eligibility`
- `near_tiny_live_review`
- `reason_codes`
- `uses_real_capital=False`
- `live_order_routing=False`

- [ ] **Step 3: Wire CLI**

- Add `evidence-report --daily` and `evidence-report --weekly` as operator-facing report commands.
- Required flags: `--db`, `--memory`, and `--out`.
- Optional repeated flag: `--strategy-family`.
- CLI JSON output includes `daily_report_out` when `--daily` is used and `weekly_report_out` when `--weekly` is used.
- Also teach `evidence-run` to call the same report builders when `--report-out` or `--weekly-report-out` is provided, so the runner can emit both artifacts in one pass.

The builder functions must exist before `evidence-run` consumes them. Do not wire the optional weekly output in Task 10; wire it here after the builder exists.

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_reports.py tests/test_research_loop_paper_evidence.py tests/test_paper_evidence.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/pipeline/evidence_reports.py src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/cli.py tests/test_evidence_reports.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/pipeline/evidence_reports.py src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/cli.py tests/test_evidence_reports.py
git commit -m "feat: summarize daily and weekly evidence"
```

**Exit criteria:** The owner can read one report and know what improved, what failed, what to stop, and what to run next.

### Task 15: Degradation Detector And Auto-Stop Rules

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- Modify: `src/crypto_alpha_agent/pipeline/experiment_planner.py`
- Modify: `src/crypto_alpha_agent/risk/paper_gate.py`
- Test: `tests/test_evidence_degradation.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- Negative rolling expectancy triggers `degraded_expectancy`.
- Repeated blocked outcomes trigger `insufficient_evidence_progress`.
- Fee/slippage killing the edge triggers `fee_killed_edge` or `slippage_killed_edge`.
- Degraded families are excluded from next experiment proposals unless explicitly requested.
- The experiment planner must receive the degraded-family decision and exclude it by default.

- [ ] **Step 2: Implement detector**

Create:

- `detect_strategy_degradation(outcomes, validation_evidence, window=10)`
- `mark_family_degraded(strategy_family, reason_codes, memory_path=None)` or equivalent state helper that the planner can read.

Reason codes:

- `degraded_expectancy`
- `fee_killed_edge`
- `slippage_killed_edge`
- `insufficient_evidence_progress`
- `drawdown_breach`
- `too_many_blocked_runs`

- [ ] **Step 3: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_degradation.py tests/test_evidence_reports.py tests/test_ai_experiment_planner.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/pipeline/evidence_reports.py src/crypto_alpha_agent/pipeline/experiment_planner.py src/crypto_alpha_agent/risk/paper_gate.py tests/test_evidence_degradation.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/pipeline/evidence_reports.py src/crypto_alpha_agent/pipeline/experiment_planner.py src/crypto_alpha_agent/risk/paper_gate.py tests/test_evidence_degradation.py
git commit -m "feat: detect degraded paper evidence"
```

**Exit criteria:** The system stops wasting time on strategy families whose evidence is getting worse.

---

## Phase H: Rollout Readiness From Accumulated Evidence

### Task 16: Rollout Evidence Builder And Readiness CLI

**Files:**
- Modify: `src/crypto_alpha_agent/risk/rollout.py`
- Modify: `src/crypto_alpha_agent/evidence/live_readiness.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_rollout_readiness_cli.py`

- [ ] **Step 1: Write failing tests**

Tests must cover:

- `rollout-review --db ... --strategy-family funding_extremity_price_confirmation` loads paper outcomes and validation evidence.
- It converts closed outcomes into `PaperTradeObservation`.
- It converts walk-forward validation into `WalkForwardSplit`.
- Fewer than 30 observations blocks with `insufficient_sample_size`.
- Passing data can generate `ready_for_human_review=True` only when human approval reference is supplied.
- The artifact always has `live_execution_enabled=False`.
- CLI payload always has `uses_real_capital=False` and `live_order_routing=False`.

- [ ] **Step 2: Implement builder**

Create functions:

- `paper_outcomes_to_rollout_observations(outcomes)`
- `validation_evidence_to_walk_forward_splits(evidence)`
- `build_rollout_review_artifact(db_path, strategy_family, human_approved=False, human_approval_reference=None, max_notional_usd=25.0, max_daily_loss_usd=10.0)`

- [ ] **Step 3: Wire CLI**

Add command `rollout-review`:

- `--db`
- `--strategy-family`
- `--human-approved`
- `--human-approval-reference`
- `--max-notional-usd`
- `--max-daily-loss-usd`
- `--artifact-out`

No live execution flags.

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_rollout_readiness_cli.py tests/test_rollout_gates.py tests/test_live_readiness.py -q
uv run --extra dev ruff check src/crypto_alpha_agent/risk/rollout.py src/crypto_alpha_agent/evidence/live_readiness.py src/crypto_alpha_agent/cli.py tests/test_rollout_readiness_cli.py
git diff --check
```

Commit:

```bash
git add src/crypto_alpha_agent/risk/rollout.py src/crypto_alpha_agent/evidence/live_readiness.py src/crypto_alpha_agent/cli.py tests/test_rollout_readiness_cli.py
git commit -m "feat: build rollout review from evidence"
```

**Exit criteria:** Tiny-live review artifacts can be generated from accumulated evidence, but still cannot execute trades.

---

## Phase I: Documentation And Operator Workflow

### Task 17: Complete Operator Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/rollout-gates.md`
- Modify: `docs/tiny-live-readiness.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write failing documentation contract tests**

Create tests that assert docs mention:

- `evidence-run`
- `plan-experiments`
- `rollout-review`
- no wallet keys
- no live order routing
- ordinary public APIs
- few hundred USD
- 30 paper observations before tiny-live review

- [ ] **Step 2: Update README**

README must include:

- setup
- safe evidence-run example
- safe experiment planning example
- safe rollout-review example
- explicit no-live statement

- [ ] **Step 3: Update runbook**

Runbook must include:

- daily sequence
- weekly sequence
- what to inspect
- failure reasons and what they mean
- how to stop a degraded family
- how to preserve evidence

- [ ] **Step 4: Update roadmap**

Roadmap must mark:

- Phase 2 strategy validation expanded.
- Phase 4 evidence accumulation operational.
- Remaining blocked item: live execution until future charter revision.

- [ ] **Step 5: Verify and commit**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
uv run --extra dev ruff check tests/test_documentation_contract.py
git diff --check
```

Commit:

```bash
git add README.md docs/runbook.md docs/roadmap.md docs/rollout-gates.md docs/tiny-live-readiness.md tests/test_documentation_contract.py
git commit -m "docs: document complete evidence workflow"
```

**Exit criteria:** Docs and code describe the same safe operator workflow.

---

## Phase J: End-To-End Acceptance

### Task 18: Full Local Acceptance Scenario

**Files:**
- Create: `tests/test_complete_evidence_system.py`
- Modify: no production files unless this test exposes a bug

- [ ] **Step 1: Write end-to-end test**

Use fake collectors and local temp files to run:

1. `evidence-run`
2. `research-loop --include-validation --include-paper-evidence --memory`
3. `plan-experiments`
4. `evidence-report --weekly`
5. `rollout-review`

Assert:

- SQLite has source records, validation evidence, paper outcomes.
- Optional Dune/TheGraph sources are represented as `skipped/not_configured` when not configured; when explicitly configured and failing, they become source-health failures instead of hidden crashes.
- Memory has research-loop records, validation lesson records, paper evidence records, and experiment proposal records.
- The research milestone includes non-zero signal, anomaly, hypothesis, reflection, and accept/reject reason counts.
- Daily and weekly reports exist.
- The AI experiment planner excludes degraded strategy families and does not repeat parameter sets already blocked by validation memory.
- Rollout review blocks before 30 observations.
- Every payload has `uses_real_capital=False` and `live_order_routing=False`.

Use this acceptance shape:

```python
from __future__ import annotations

import json
import sqlite3
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle


class FakeCcxtCollector:
    def fetch_ohlcv(self, symbol, timeframe, *, since=None, limit=None, params=None):
        start = datetime(2026, 5, 17, tzinfo=UTC)
        closes = [100, 103, 101, 99, 102, 104, 101, 100, 98, 101, 105, 103]
        return [
            MarketCandle(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=start + timedelta(hours=index),
                timeframe=timeframe,
                open=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1000.0 + index,
            )
            for index, close in enumerate(closes)
        ][:limit]

    def fetch_funding_rate_history(self, symbol, *, since=None, limit=None, params=None):
        start = datetime(2026, 5, 17, tzinfo=UTC)
        rates = [0.0008, -0.0009, 0.0007, -0.0006]
        return [
            FundingRateRecord(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=start + timedelta(hours=index * 3),
                funding_rate=rate,
            )
            for index, rate in enumerate(rates)
        ][:limit]


@pytest.fixture
def fake_ccxt_collector():
    return FakeCcxtCollector()


def invoke_json(args: list[str]) -> dict[str, object]:
    stdout = StringIO()
    with redirect_stdout(stdout):
        exit_code = main(args)
    assert exit_code == 0, stdout.getvalue()
    return json.loads(stdout.getvalue())


def sqlite_count(db_path: Path, table_name: str) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute(f"select count(*) from {table_name}").fetchone()[0])


def memory_contains(memory_path: Path, tag_or_record_prefix: str) -> bool:
    return any(
        tag_or_record_prefix in json.loads(line).get("tags", [])
        or json.loads(line).get("record_id", "").startswith(tag_or_record_prefix)
        for line in memory_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def test_complete_safe_autonomous_evidence_system(tmp_path, monkeypatch, fake_ccxt_collector):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    daily_path = tmp_path / "daily.md"
    weekly_path = tmp_path / "weekly.md"
    rollout_path = tmp_path / "rollout.json"

    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda _exchange_id: fake_ccxt_collector,
    )

    run_result = invoke_json([
        "evidence-run",
        "--db", str(db_path),
        "--memory", str(memory_path),
        "--report-out", str(daily_path),
        "--current-capital-usd", "300",
        "--allow-network",
        "--symbol", "BTC/USDT",
        "--funding-symbol", "BTC/USDT:USDT",
        "--timeframe", "1h",
        "--limit", "200",
        "--strategy-family", "funding_extremity_price_confirmation",
        "--strategy-family", "funding_mean_reversion_after_extreme",
    ])

    research_result = invoke_json([
        "research-loop",
        "--db", str(db_path),
        "--memory", str(memory_path),
        "--include-validation",
        "--include-paper-evidence",
        "--strategy-family", "funding_extremity_price_confirmation",
        "--price-symbol", "BTC/USDT",
        "--funding-symbol", "BTC/USDT:USDT",
        "--validation-timeframe", "1h",
    ])

    planner_result = invoke_json([
        "plan-experiments",
        "--db", str(db_path),
        "--memory", str(memory_path),
        "--current-capital-usd", "300",
        "--max-proposals", "3",
    ])

    report_result = invoke_json([
        "evidence-report",
        "--db", str(db_path),
        "--memory", str(memory_path),
        "--weekly",
        "--out", str(weekly_path),
    ])

    rollout_result = invoke_json([
        "rollout-review",
        "--db", str(db_path),
        "--strategy-family", "funding_extremity_price_confirmation",
        "--artifact-out", str(rollout_path),
    ])

    assert run_result["uses_real_capital"] is False
    assert run_result["live_order_routing"] is False
    assert run_result["research_milestone"]["signal_count"] > 0
    assert run_result["research_milestone"]["anomaly_count"] > 0
    assert run_result["research_milestone"]["hypothesis_count"] > 0
    assert run_result["research_milestone"]["reflection_count"] > 0
    assert run_result["research_milestone"]["accept_reject_reason_count"] > 0
    assert run_result["source_health"]["optional_source_skipped"] >= 0
    assert run_result["source_health"]["optional_source_failures"] >= 0

    assert sqlite_count(db_path, "source_records") > 0
    assert sqlite_count(db_path, "validation_evidence") > 0
    assert sqlite_count(db_path, "paper_outcomes") > 0
    assert memory_contains(memory_path, "research-loop:")
    assert memory_contains(memory_path, "validation-evidence")
    assert memory_contains(memory_path, "paper-evidence")
    assert memory_contains(memory_path, "experiment-proposal")

    assert planner_result["current_capital_usd"] == 300.0
    assert all(exp["max_notional_usd"] <= 25.0 for exp in planner_result["proposals"])
    assert all(not exp.get("requires_speed_edge") for exp in planner_result["proposals"])
    assert all(exp["strategy_family"] not in planner_result["degraded_strategy_families"] for exp in planner_result["proposals"])

    assert daily_path.exists()
    assert weekly_path.exists()
    assert report_result["weekly_report_out"] == str(weekly_path)
    assert rollout_result["decision"] == "blocked"
    assert "insufficient_sample_size" in rollout_result["blocked_reasons"]
    assert rollout_result["uses_real_capital"] is False
    assert rollout_result["live_order_routing"] is False
    for payload in [run_result, research_result, planner_result, report_result, rollout_result]:
        assert payload["uses_real_capital"] is False
        assert payload["live_order_routing"] is False
```

The two argv entries `"--timeframe", "1h"` are the test form of the command-line flag `--timeframe "1h"`.

- [ ] **Step 2: Verify red or expose missing integration**

Run:

```bash
uv run --extra dev pytest tests/test_complete_evidence_system.py -q
```

Expected before all phases: FAIL. Expected after Tasks 1-17: PASS.

- [ ] **Step 3: Fix only integration bugs**

Do not add new features here. Fix only mismatches found by the acceptance test.

- [ ] **Step 4: Full verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
rg -n "create_order|private_key|seed phrase|send_transaction|live_order_routing.*True|touched_real_capital.*True" src tests docs
```

The `rg` command may return documentation/tests that assert forbidden paths are blocked; it must not reveal production live execution paths.

- [ ] **Step 5: Commit**

```bash
git status --short
git add tests/test_complete_evidence_system.py
git commit -m "test: cover complete evidence system"
```

If Step 3 fixed integration mismatches in production code, stage only the exact production files changed in Step 3 before the commit. Do not stage unrelated dirty files.

**Exit criteria:** The repository proves the complete safe autonomous evidence workflow locally.

---

## Execution Order For Subagents

Run one task at a time, with these gates after every task:

1. Implementation subagent writes tests first, then code, then commits.
2. Spec review subagent checks the task against this plan.
3. Code quality review subagent checks for Critical/Important issues.
4. If review fails, send fixes back to a worker and re-review.
5. After each phase, run the phase test group.
6. After Task 18, run full verification.

Recommended phase order:

1. Task 1
2. Tasks 2, 2A, and 3
3. Tasks 4, 5, 6, and 6A
4. Tasks 7, 8, and 9
5. Task 10
6. Task 11
7. Task 12
8. Task 13
9. Tasks 14 and 15
10. Task 16
11. Task 17
12. Task 18

## Global Stop Conditions

Stop and report instead of implementing if:

- Any task requires wallet keys, exchange order routing, private keys, live balances, or live orders.
- A data source requires paid access and no free public fallback exists.
- A strategy needs speed, premium RPC, private mempool, MEV, bridge racing, or flash loans.
- Tests reveal existing mainline behavior is broken before a task starts.
- A strategy only works by assuming fills, liquidity, or fees the owner cannot plausibly get.

## Final Integration Criteria

The plan is complete only when:

1. `uv run --extra dev pytest -q` passes.
2. `uv run --extra dev ruff check .` passes.
3. `git diff --check` passes.
4. `evidence-run` can execute locally with fake/injected collectors in tests.
5. `research-loop` can persist hypothesis memory from CLI.
6. `plan-experiments` can produce bounded next experiments from evidence and memory.
7. `evidence-report` can produce daily and weekly summaries.
8. `rollout-review` can build a blocking or passing readiness artifact from accumulated evidence.
9. No production code path loads wallet keys, submits live exchange orders, signs transactions, or routes real capital.
10. Docs match the implemented workflow.

## What Remains Outside This Plan

- Any live execution adapter.
- Any real exchange key integration.
- Any wallet signing path.
- Paid data dependencies as required infrastructure.
- MEV, mempool, bridge race, flash-loan, or sub-second arbitrage strategy families.
