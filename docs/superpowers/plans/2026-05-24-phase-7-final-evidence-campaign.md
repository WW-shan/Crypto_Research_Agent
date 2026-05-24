# Phase 7 Final Evidence Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible Phase 7 historical bootstrap and ongoing evidence-campaign artifact that ties stored historical data, validation, paper simulation, source health, governance classification, and 30/60/90 sample targets together without live execution.

**Architecture:** Add a focused `pipeline/historical_bootstrap.py` module that reuses existing ledgers, `run_stored_research_loop()`, `run_paper_sim_loop()`, source probes, weekly evidence reports, and profit governance. Expose it through a safe `historical-bootstrap` CLI command and Markdown renderer. Keep daily collection on the existing `evidence-run` path; the new artifact records the historical baseline and compares accumulated out-of-sample observations against it.

**Tech Stack:** Python 3.12, Pydantic strict models, SQLite-backed `ResearchDataStore`, existing validation/paper/governance ledgers, argparse CLI, pytest, ruff.

---

## Smart Search Evidence

Evidence directory: `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/`.

Commands run before design:

- `smart-search doctor --format json > /tmp/smart-search-evidence/20260524-phase7-evidence-campaign/doctor.json`
- `smart-search deep "Phase 7 crypto alpha evidence campaign historical bootstrap Binance Public Data funding open interest paper trading observations governance report out-of-sample validation" --format json --output /tmp/smart-search-evidence/20260524-phase7-evidence-campaign/00-deep-plan.json`
- `smart-search search "crypto trading strategy historical bootstrap out-of-sample paper trading Binance public data funding rate open interest governance scorecard" --validation balanced --extra-sources 3 --timeout 90 --format json --output /tmp/smart-search-evidence/20260524-phase7-evidence-campaign/01-search.json`
- Fetched sources:
  - `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/02-fetch-binance-public-data.md`
  - `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/03-fetch-binance-funding-rate-history.md`
  - `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/04-fetch-binance-open-interest-statistics.md`
  - `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/05-fetch-out-of-sample-testing.md`
  - `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/06-fetch-binance-basis.md`
  - `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/07-fetch-binance-long-short-ratio.md`
  - `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/08-fetch-binance-kline.md`
  - `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/09-fetch-paper-trading-forward-testing.md`

External findings used:

- Binance Public Data provides reproducible public market-data files with daily/monthly kline files, futures kline records, and checksum files.
- Binance USD-M funding history exposes `GET /fapi/v1/fundingRate` with `symbol`, `startTime`, `endTime`, and `limit` up to 1000.
- Binance USD-M open-interest statistics expose `GET /futures/data/openInterestHist`, but the official docs state only the latest one month is available.
- Binance basis and global long/short ratio endpoints are recent-history public market-data endpoints; they are source-health/probe evidence in this repo until a future validator requires typed storage.
- Out-of-sample testing is used to detect overfit historical strategies; paper/forward testing helps observe real-time execution and slippage gaps but is not profit proof.

## Local Feasibility

Files inspected:

- `docs/project-charter.md`
- `docs/roadmap.md`
- `docs/runbook.md`
- `docs/rollout-gates.md`
- `docs/tiny-live-readiness.md`
- `docs/project-asset-assessment.md`
- `docs/goals/project-completion-goal.md`
- `docs/goals/project-completion-state.md`
- `src/crypto_alpha_agent/cli.py`
- `src/crypto_alpha_agent/pipeline/evidence_runner.py`
- `src/crypto_alpha_agent/pipeline/evidence_run_ops.py`
- `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- `src/crypto_alpha_agent/pipeline/governance_reports.py`
- `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- `src/crypto_alpha_agent/pipeline/research_loop.py`
- `src/crypto_alpha_agent/strategy/registry.py`
- `src/crypto_alpha_agent/data/source_probe.py`
- `src/crypto_alpha_agent/data/models.py`
- `tests/test_evidence_runner.py`
- `tests/test_governance_reports.py`
- `tests/test_documentation_contract.py`

Baseline focused feasibility command:

```bash
uv run --extra dev pytest \
  tests/test_evidence_runner.py::test_evidence_runner_executes_complete_research_milestone \
  tests/test_governance_reports.py::test_governance_report_marks_registered_no_evidence_families_add_data \
  tests/test_documentation_contract.py::test_documented_representative_cli_examples_parse \
  -q
```

Result: `3 passed in 8.63s`.

Reuse decisions:

- Use `default_strategy_registry()` to enumerate every registered family. Run paper simulation only for families with `supports_paper_simulation=True`.
- Add date-window filtering to `ResearchDataStore.load_records()` and thread it through `run_stored_research_loop()` and `run_paper_sim_loop()` so a multi-window bootstrap records actual windowed evidence instead of repeated whole-database evidence.
- Use `run_stored_research_loop(... include_validation=True, observed_at_start=..., observed_at_end=...)` for per-family validation evidence because it already writes validation ledger rows and stable blocked reasons.
- Use `run_paper_sim_loop(... observed_at_start=..., observed_at_end=...)` for per-family historical paper outcomes because it already applies Phase 10 cost realism and writes the paper ledger.
- Use `build_weekly_evidence_report()` for 30-observation progress and `build_profit_governance_report()` for keep/stop/redesign/add-data/owner-review actions.
- Add one `source-probe` target for Binance USD-M global long/short ratio; existing targets already cover open interest and basis.
- Do not add typed basis or long/short record types in Phase 7 because no current executable validator requires them. Record them as source-health/probe evidence and list typed ingestion as a future blocked candidate.

Rejected or blocked candidates:

- Live trading, exchange order submission, wallet access, or exchange trade permissions: blocked by the charter.
- Premium data/RPC, speed-edge execution, MEV, or high-capital strategy work: blocked by the charter.
- Adding typed basis/long-short storage now: rejected as YAGNI for current executable validators; source-health proof is enough for Phase 7.
- Claiming profit proof from historical bootstrap: blocked by roadmap; report must say future out-of-sample samples decide.

## Files

- Create: `src/crypto_alpha_agent/pipeline/historical_bootstrap.py`
- Modify: `src/crypto_alpha_agent/data/store.py`
- Modify: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Modify: `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/data/source_probe.py`
- Create: `tests/test_historical_bootstrap.py`
- Modify: `tests/test_documentation_contract.py`
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-asset-assessment.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-24-phase-7-final-evidence-campaign-completion-report.md`

## Task 1: Date-Windowed Store, Research, And Paper Simulation

**Files:**
- Modify: `src/crypto_alpha_agent/data/store.py`
- Modify: `src/crypto_alpha_agent/pipeline/research_loop.py`
- Modify: `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- Modify: `tests/test_data_models_store.py`
- Modify: `tests/test_research_loop_strategy_validation.py`
- Modify: `tests/test_paper_sim_loop.py`

- [ ] **Step 1: Write failing date-window tests**

Add tests that seed one record before a window, records inside the window, and one record after the window. Assert:

```python
loaded = store.load_records(
    observed_at_start=datetime(2026, 4, 1, tzinfo=UTC),
    observed_at_end=datetime(2026, 5, 1, tzinfo=UTC),
)
assert [record.record_id for record in loaded] == ["inside-window"]
```

Add research-loop and paper-loop tests that call:

```python
run_stored_research_loop(... observed_at_start=start, observed_at_end=end)
run_paper_sim_loop(... observed_at_start=start, observed_at_end=end)
```

Expected assertions:

- research-loop `loaded_records` excludes records outside the window;
- validation summaries reflect only the windowed records;
- paper outcomes for a no-signal window are blocked with no out-of-window trade ids;
- safety flags remain false.

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --extra dev pytest \
  tests/test_data_models_store.py \
  tests/test_research_loop_strategy_validation.py::test_research_loop_filters_validation_records_by_observed_window \
  tests/test_paper_sim_loop.py::test_paper_sim_loop_filters_records_by_observed_window \
  -q
```

Expected: fail because `observed_at_start` and `observed_at_end` are unsupported.

- [ ] **Step 3: Implement date-window filtering**

Update `ResearchDataStore.load_records()` signature:

```python
def load_records(
    self,
    record_type: RecordType | None = None,
    source: str | None = None,
    observed_at_start: datetime | None = None,
    observed_at_end: datetime | None = None,
) -> list[SourceRecord]:
```

Use inclusive start and exclusive end:

```sql
observed_at >= ?
observed_at < ?
```

Update `run_stored_research_loop()` and `run_paper_sim_loop()` to accept and pass the same optional window bounds. Include the bounds in stable paper run/config ids so separate windows do not overwrite each other.

- [ ] **Step 4: Run date-window tests**

```bash
uv run --extra dev pytest \
  tests/test_data_models_store.py \
  tests/test_research_loop_strategy_validation.py::test_research_loop_filters_validation_records_by_observed_window \
  tests/test_paper_sim_loop.py::test_paper_sim_loop_filters_records_by_observed_window \
  -q
```

Expected: pass.

## Task 2: Tests For Historical Bootstrap Models And Builder

**Files:**
- Create: `tests/test_historical_bootstrap.py`
- Later create: `src/crypto_alpha_agent/pipeline/historical_bootstrap.py`

- [ ] **Step 1: Write failing model/builder tests**

Add tests that seed market candles, funding rates, and open-interest records into a temp DB, then call:

```python
from crypto_alpha_agent.pipeline.historical_bootstrap import build_historical_bootstrap_report

report = build_historical_bootstrap_report(
    db_path=db_path,
    memory_path=memory_path,
    run_id="phase7-fixture",
    current_capital_usd=300.0,
    price_symbol="BTC/USDT",
    funding_symbol="BTC/USDT:USDT",
    timeframe="1h",
    bootstrap_windows=["2026-02-01/2026-03-01", "2026-03-01/2026-04-01", "2026-04-01/2026-05-01"],
    strategy_families=None,
    allow_network=False,
)
```

Expected assertions:

- `report.command == "historical-bootstrap"`
- `report.uses_real_capital is False`
- `report.live_order_routing is False`
- `report.network_route == "blocked"`
- `report.bootstrap_windows` contains three windows and records `price_symbol`, `funding_symbol`, and `timeframe`
- every window has concrete `start_at` and `end_at` ISO timestamps
- `report.source_steps` includes blocked rows for `binance_public_klines`, `ccxt_funding_rate_history`, `ccxt_open_interest_history`, `binance_usdm_basis`, and `binance_usdm_global_long_short_account_ratio`
- `report.strategy_results` includes all paper-capable families: `funding_extremity_price_confirmation`, `funding_mean_reversion_after_extreme`, and `funding_open_interest_crowding`
- each strategy result contains validation status, validation metrics, paper outcome count, paper statuses, blocked reasons, cost model mode, and governance action
- `report.sample_targets.paper_observation_targets == [30, 60]`
- `report.sample_targets.calendar_day_target == 90`
- `report.out_of_sample_policy == "future_evidence_run_observations_only"`

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run --extra dev pytest tests/test_historical_bootstrap.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'crypto_alpha_agent.pipeline.historical_bootstrap'`.

## Task 3: Historical Bootstrap Builder

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/historical_bootstrap.py`
- Test: `tests/test_historical_bootstrap.py`

- [ ] **Step 1: Implement strict report models**

Add Pydantic models:

```python
class HistoricalBootstrapWindow(BaseModel): ...
class HistoricalBootstrapSourceStep(BaseModel): ...
class HistoricalBootstrapStrategyResult(BaseModel): ...
class HistoricalBootstrapSampleTargets(BaseModel): ...
class HistoricalBootstrapManifest(BaseModel): ...
class HistoricalBootstrapReport(BaseModel): ...
```

All models use `ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)`. Top-level safety fields are `uses_real_capital: Literal[False] = False` and `live_order_routing: Literal[False] = False`.

- [ ] **Step 2: Implement `build_historical_bootstrap_report()`**

Inputs:

```python
def build_historical_bootstrap_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    run_id: str | None = None,
    current_capital_usd: float = 300.0,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    bootstrap_windows: Sequence[str] = (),
    strategy_families: Sequence[str] | None = None,
    allow_network: bool = False,
    binance_symbol: str | None = None,
    ccxt_exchange: str = "binance",
    limit: int = 200,
    notional_usd: float = 25.0,
) -> HistoricalBootstrapReport:
```

Behavior:

- Normalize `run_id` to `historical-bootstrap-<UTC timestamp>` when omitted.
- Parse bootstrap windows in `YYYY-MM-DD/YYYY-MM-DD` form, with inclusive start and exclusive end.
- Normalize empty `strategy_families` to every registered family.
- Mark network route through `network_route_from_environment(allow_network=allow_network)`.
- For Phase 7, use stored records when `allow_network=False`; record source steps as blocked with `network_not_allowed`.
- When `allow_network=True`, call existing public ingestion helpers for Binance Public klines, CCXT funding history, and CCXT open-interest history; record each source step with parameters and records written. If a source fails, record `status="failed"` and continue to validation/paper with existing stored data.
- Always run source probes for `binance_usdm_open_interest_history`, `binance_usdm_basis`, and `binance_usdm_global_long_short_account_ratio`; with `allow_network=False`, they produce blocked source-health rows.
- For each paper-capable family and each parsed window, run `run_stored_research_loop(... include_validation=True, include_paper_evidence=True, observed_at_start=start, observed_at_end=end)` and `run_paper_sim_loop(... observed_at_start=start, observed_at_end=end)`.
- For watchlist-only families, add a strategy result with `paper_simulation_supported=False`, `classification="research_only"`, and `blocked_reasons=["paper_simulation_not_supported"]`.
- Build `weekly_report = build_weekly_evidence_report(...)` and `governance_report = build_profit_governance_report(...)`.
- Classify family results from governance action:
  - `owner_decision_review`, `keep_collecting`: worth future out-of-sample observation
  - `stop`: negative or degraded
  - `add_data`, `redesign_validator`: blocked or needs more evidence

- [ ] **Step 3: Run model/builder tests**

```bash
uv run --extra dev pytest tests/test_historical_bootstrap.py -q
```

Expected: builder tests pass; CLI/Markdown tests fail until later tasks add those surfaces.

## Task 4: Markdown Renderer

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Test: `tests/test_historical_bootstrap.py`

- [ ] **Step 1: Add failing Markdown test**

Assert:

```python
from crypto_alpha_agent.pipeline.markdown import render_historical_bootstrap_markdown

markdown = render_historical_bootstrap_markdown(report)
assert markdown.startswith("# Phase 7 Historical Bootstrap Report")
assert "Real capital: false" in markdown
assert "Live order routing: false" in markdown
assert "## Bootstrap Windows" in markdown
assert "## Source Collection" in markdown
assert "## Strategy Results" in markdown
assert "## 30/60/90 Evidence Targets" in markdown
assert "future_evidence_run_observations_only" in markdown
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run --extra dev pytest tests/test_historical_bootstrap.py::test_historical_bootstrap_markdown_renders_phase7_targets -q
```

Expected: import failure for missing renderer.

- [ ] **Step 3: Implement renderer**

Add `render_historical_bootstrap_markdown(report: HistoricalBootstrapReport) -> str` with sections:

- Safety
- Bootstrap Windows
- Source Collection
- Strategy Results
- Weekly Sample Progress
- Governance Classification
- 30/60/90 Evidence Targets
- Out-of-Sample Policy
- Manifest

- [ ] **Step 4: Run Markdown test**

```bash
uv run --extra dev pytest tests/test_historical_bootstrap.py::test_historical_bootstrap_markdown_renders_phase7_targets -q
```

Expected: pass.

## Task 5: CLI And Source Probe Target

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/data/source_probe.py`
- Test: `tests/test_historical_bootstrap.py`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Add failing CLI and source-probe tests**

Add assertions that:

- `source-probe --list-targets` includes `binance_usdm_global_long_short_account_ratio`
- `historical-bootstrap` writes Markdown, JSON payload, and manifest files
- CLI JSON has `command == "historical-bootstrap"`
- manifest records `run_id`, redacted inputs, `network_route`, source health, records written, report paths, memory path, status, and no live flags
- parser accepts a representative documented command

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --extra dev pytest tests/test_historical_bootstrap.py tests/test_documentation_contract.py::test_documented_representative_cli_examples_parse -q
```

Expected: fail because the parser does not know `historical-bootstrap` and source-probe target is missing.

- [ ] **Step 3: Add `binance_usdm_global_long_short_account_ratio` probe target**

Use endpoint family `GET /futures/data/globalLongShortAccountRatio`, URL family `binance_usdm_global_long_short_account_ratio`, expected fields `symbol`, `longShortRatio`, `timestamp`, and rate-limit assumption from Binance docs.

- [ ] **Step 4: Add CLI parser and handler**

Add parser:

```python
historical_parser = subparsers.add_parser(
    "historical-bootstrap",
    help="Generate Phase 7 historical bootstrap and evidence-campaign report.",
)
```

Arguments:

- `--db`
- `--memory`
- `--out`
- `--json-out`
- `--manifest-out`
- `--run-id`
- `--current-capital-usd`
- `--allow-network`
- `--binance-symbol`
- `--price-symbol`
- `--funding-symbol`
- `--timeframe`
- repeated `--bootstrap-window`
- repeated `--strategy-family`
- `--ccxt-exchange`
- `--limit`
- `--notional-usd`

Handler writes Markdown through `render_historical_bootstrap_markdown()`, JSON payload through `write_json_artifact()`, and manifest JSON. Return payload with `exit_code=0` for success, `exit_code=2` for failed status.

- [ ] **Step 5: Run CLI tests**

```bash
uv run --extra dev pytest tests/test_historical_bootstrap.py tests/test_documentation_contract.py::test_documented_representative_cli_examples_parse -q
```

Expected: pass.

## Task 6: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-asset-assessment.md`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Add documentation contract terms**

Add terms for:

- `historical-bootstrap`
- `historical bootstrap report`
- `future out-of-sample`
- `30/60/90 evidence targets`
- `binance_usdm_global_long_short_account_ratio`

- [ ] **Step 2: Run documentation contract to verify it fails**

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: fail until docs are updated.

- [ ] **Step 3: Update docs**

Update:

- `README.md`: add safe Phase 7 command example and explain it remains paper-only.
- `docs/runbook.md`: add a Historical Bootstrap Workflow before Daily Sequence and clarify future `evidence-run` observations are out-of-sample checks.
- `docs/roadmap.md`: mark Phase 7 deliverables as complete for the historical bootstrap command/report and ongoing campaign handoff; keep Phase 13 as next.
- `docs/project-asset-assessment.md`: list `historical-bootstrap` under P0 evidence factory assets.

- [ ] **Step 4: Run documentation tests**

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: pass.

## Task 7: Completion State And Phase Report

**Files:**
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-24-phase-7-final-evidence-campaign-completion-report.md`

- [ ] **Step 1: Update state and report**

Record:

- Smart Search evidence path and fetched sources.
- Local feasibility result and baseline tests.
- Files changed and tests added.
- Subagent audit/review usage.
- Historical bootstrap command/report behavior.
- Ongoing evidence campaign handoff: daily `evidence-run`, weekly `evidence-report`, governance report, manifests, failed markers, notification hook, retention.
- Explicit note that Phase 7 is not profit proof and Phase 13 is next.

- [ ] **Step 2: Run focused docs test**

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: pass.

## Task 8: Review, Verification, Commit, Merge

**Files:**
- All changed files.

- [ ] **Step 1: Focused verification**

```bash
uv run --extra dev pytest \
  tests/test_historical_bootstrap.py \
  tests/test_evidence_runner.py \
  tests/test_evidence_reports.py \
  tests/test_governance_reports.py \
  tests/test_documentation_contract.py \
  tests/test_complete_evidence_system.py::test_complete_safe_autonomous_evidence_system \
  -q
```

- [ ] **Step 2: Changed-file lint**

```bash
uv run ruff check \
  src/crypto_alpha_agent/pipeline/historical_bootstrap.py \
  src/crypto_alpha_agent/data/store.py \
  src/crypto_alpha_agent/pipeline/research_loop.py \
  src/crypto_alpha_agent/pipeline/paper_sim_loop.py \
  src/crypto_alpha_agent/pipeline/markdown.py \
  src/crypto_alpha_agent/cli.py \
  src/crypto_alpha_agent/data/source_probe.py \
  tests/test_historical_bootstrap.py \
  tests/test_documentation_contract.py
```

- [ ] **Step 3: Subagent review passes**

Request:

- Spec/requirements review against Phase 7 roadmap, charter, and this plan.
- Code/safety review of the implementation diff.

Fix all Critical or Important findings, rerun focused tests, and request re-review until no Critical or Important findings remain.

- [ ] **Step 4: Full verification**

```bash
uv run --extra dev pytest -q
uv run ruff check
git diff --check
uv run python -m crypto_alpha_agent.security.secret_scan --path src --path tests --path docs --path README.md --fail-on-empty-with-untracked
```

- [ ] **Step 5: Commit and publish**

```bash
git status --short
git add src/crypto_alpha_agent/pipeline/historical_bootstrap.py \
  src/crypto_alpha_agent/data/store.py \
  src/crypto_alpha_agent/pipeline/research_loop.py \
  src/crypto_alpha_agent/pipeline/paper_sim_loop.py \
  src/crypto_alpha_agent/pipeline/markdown.py \
  src/crypto_alpha_agent/cli.py \
  src/crypto_alpha_agent/data/source_probe.py \
  tests/test_historical_bootstrap.py \
  tests/test_documentation_contract.py \
  README.md docs/runbook.md docs/roadmap.md docs/project-asset-assessment.md \
  docs/goals/project-completion-state.md \
  docs/goals/phase-reports/2026-05-24-phase-7-final-evidence-campaign-completion-report.md \
  docs/superpowers/plans/2026-05-24-phase-7-final-evidence-campaign.md
git commit -m "feat: add historical evidence campaign report"
git push origin phase-7-final-evidence-campaign
git switch main
git merge --ff-only phase-7-final-evidence-campaign
git push origin main
```

## Self-Review

Spec coverage:

- Phase 7A historical bootstrap: covered by `historical-bootstrap` source steps, validation, paper simulation, report, and manifest.
- Phase 7B ongoing collection: covered by runbook and state handoff; daily execution stays on existing `evidence-run`.
- Run manifests: covered by existing `evidence-run` and new bootstrap manifest.
- Failure notification: already in runbook; Phase 7 docs reference and retain it.
- 30/60/90 targets: explicit in report and docs.
- Governance classification: uses Phase 12 `build_profit_governance_report()`.
- No live capital/wallet/orders: enforced by report models, CLI payload, docs, and verification.

Placeholder scan:

- No `TODO`, `TBD`, or unresolved placeholders.

Type consistency:

- New report builder returns `HistoricalBootstrapReport`.
- Markdown renderer accepts `HistoricalBootstrapReport`.
- CLI command returns JSON with `command="historical-bootstrap"` and writes Markdown/JSON/manifest artifacts.
