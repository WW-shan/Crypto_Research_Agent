# Project Completion State

This file is the working memory for the long-running Codex Goal defined in
`docs/goals/project-completion-goal.md`. Update it at the end of every completed
round.

## Current Round

- Round: 13
- Status: Phase 7 Final Evidence Campaign After Factory Buildout complete and
  verified
- Started: 2026-05-24
- Completed: 2026-05-24
- Active slice: Phase 7: Final Evidence Campaign After Factory Buildout
- Active plan source:
  `docs/superpowers/plans/2026-05-24-phase-7-final-evidence-campaign.md`
- Phase report:
  `docs/goals/phase-reports/2026-05-24-phase-7-final-evidence-campaign-completion-report.md`

## Completed This Round

- Ran Phase 7 Smart Search deep research for historical bootstrap,
  out-of-sample testing, paper-trading forward testing, and public Binance
  futures data-source shapes. Search evidence is under
  `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/`.
- Verified local feasibility:
  - safe `evidence-run`, reports, manifests, source-health rows, three
    executable paper-simulated families, three research-only watchlists, cost
    realism, AI research guards, and governance classification already exist;
  - the missing Phase 7 capability was a first-class historical bootstrap
    command plus date-window filtering for stored validation and paper
    simulation;
  - historical bootstrap must not contaminate future out-of-sample sample
    progress, forward ledgers, or stopped-family memory.
- Added `pipeline/historical_bootstrap.py` with strict deterministic models for
  bootstrap windows, source steps, strategy results, sample targets, manifests,
  and the top-level `HistoricalBootstrapReport`.
- Added `historical-bootstrap` CLI and Markdown rendering with sections for
  safety, bootstrap windows, source collection, strategy results, forward
  sample progress, governance state, forward 30/60/90 evidence targets,
  out-of-sample policy, and manifest metadata.
- Added observed-window filtering to `ResearchDataStore.load_records()`,
  `run_stored_research_loop()`, and `run_paper_sim_loop()`.
- Added non-mutating historical bootstrap operation:
  validation summaries and paper outcomes are included in the report but not
  written to the forward validation ledger, forward paper-outcome ledger, or
  stopped-family memory.
- Added observed-window filtering to Binance Public Data, CCXT funding history,
  and CCXT open-interest-history ingestion, and split network source collection
  into monthly segments.
- Added Binance USD-M global long/short account ratio source-probe target and
  updated source coverage/query docs.
- Updated README, runbook, project asset assessment, roadmap, documentation
  contracts, and this state file.

## Verification Evidence

- Smart Search evidence:
  - `smart-search doctor --format json` returned `ok=true`.
  - `00-deep-plan.json`, `01-search.json`, and fetched source notes
    `02` through `09` are stored under the Phase 7 evidence directory.
  - External findings supported Binance Public Data historical archives,
    Binance USD-M funding, open-interest, basis, long/short, and kline public
    endpoints, plus out-of-sample and forward paper-testing methodology.
- Baseline feasibility:
  `uv run --extra dev pytest tests/test_evidence_runner.py::test_evidence_runner_executes_complete_research_milestone tests/test_governance_reports.py::test_governance_report_marks_registered_no_evidence_families_add_data tests/test_documentation_contract.py::test_documented_representative_cli_examples_parse -q`
  passed with 3 tests.
- Red/green Phase 7 focused tests:
  - Date-window tests initially failed on missing `observed_at_start` and
    `observed_at_end` support, then passed after implementation.
  - Historical bootstrap tests initially failed because
    `crypto_alpha_agent.pipeline.historical_bootstrap` did not exist, then
    passed after implementation.
- Review pass found Important issues:
  - historical bootstrap contaminated forward validation/paper ledgers and
    out-of-sample progress;
  - bootstrap could mutate stopped-family memory through weekly degradation
    persistence;
  - network source failures still produced successful manifests;
  - historical source collection ignored some requested window bounds;
  - state/report docs were not synchronized;
  - operator examples used a future-ended historical window;
  - source-query docs overstated expected probe fields.
  Implementation fixes and regression tests were added. Re-review reported no
  Critical or Important findings remaining.
- Focused verification after review fixes:
  `uv run --extra dev pytest tests/test_historical_bootstrap.py tests/test_binance_public_pipeline_ingestion.py tests/test_ccxt_ingestion_service.py tests/test_paper_sim_loop.py tests/test_research_loop_strategy_validation.py::test_research_loop_filters_validation_records_by_observed_window tests/test_documentation_contract.py -q`
  passed with 59 tests.
- Changed-file lint:
  `uv run ruff check src/crypto_alpha_agent/data/ingestion.py src/crypto_alpha_agent/pipeline/historical_bootstrap.py src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/pipeline/paper_sim_loop.py src/crypto_alpha_agent/pipeline/research_loop.py src/crypto_alpha_agent/cli.py tests/test_historical_bootstrap.py tests/test_binance_public_pipeline_ingestion.py tests/test_ccxt_ingestion_service.py tests/test_paper_sim_loop.py tests/test_documentation_contract.py`
  passed.
- Full verification:
  `uv run --extra dev pytest -q` passed with 912 tests, 4 skipped, and 2
  warnings.
- `uv run --extra dev ruff check .` passed.
- `git diff --check` passed.
- Staged diff checks passed:
  `git diff --cached --check`, `git diff --cached --name-only`, and
  `git diff --cached --no-ext-diff --unified=0`.
- Staged secret scan:
  `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`
  returned `[]`.
- Final commit message target: `feat: add historical bootstrap campaign`

## Current Project Target

The evidence factory now has execution-realistic paper simulation,
evidence-grounded AI research planning, and profit governance review active:

- public-data ingestion and local durable SQLite storage;
- typed OHLCV, funding, DEX, DeFi, and open-interest records;
- source-health records that distinguish route, provider reachability, parse
  status, typed rows, and blocked reasons;
- data-quality checks for source failures, stale records, gaps, duplicates,
  timestamp skew, and invalid values;
- three executable paper-simulated families:
  `funding_extremity_price_confirmation`,
  `funding_mean_reversion_after_extreme`, and
  `funding_open_interest_crowding`;
- three research-only watchlists:
  `defi_yield_regime_watchlist`, `dex_liquidity_volume_watchlist`, and
  `volatility_compression_expansion_watchlist`;
- Phase 10 paper execution realism with venue fee assumptions, min-notional and
  precision feasibility, stale-signal gating, funding alignment checks,
  missed/partial-fill modeling, `pre_cost_only_profitable` rejection, and
  evidence package summaries for notional, fees, slippage, stale signals, and
  fills;
- daily/weekly evidence reports, governance reports, paper simulation, memory,
  and rollout review artifacts with `live_execution_enabled=false`.
- AI research context, stricter experiment proposal guards, duplicate rejected
  experiment memory, design-only strategy template proposals, and weekly
  `ai-research-memo` artifacts.
- Phase 12 `governance-report` artifacts that classify families as
  `keep_collecting`, `stop`, `redesign_validator`, `add_data`, or
  `owner_decision_review` from validation, paper, source-health, cost, and
  memory evidence.
- Phase 7 `historical-bootstrap` artifacts that evaluate historical windows,
  report source collection/probe status, classify historical strategy results,
  and set forward 30/60/90 evidence targets without mutating forward evidence
  ledgers or stopped-family memory.

## Known Hard Boundaries

- No wallet keys.
- No wallet-key access.
- No live order routing.
- No exchange order submission.
- No order routing.
- No live execution.
- No live capital.
- No real-capital execution.
- No MEV, mempool, bridge-race, flash-loan, premium-RPC, private
  infrastructure, or speed-edge strategies.
- No secrets in git, logs, docs, memory, reports, screenshots, tests, or public
  GitHub.

## Known Remaining Gaps

The first complete research-loop milestone remains complete under the current
charter. Post-milestone Phase 0, Immediate Phase 1, Immediate Phase 2,
Immediate Phase 3, Immediate Phase 4, Immediate Phase 5, Phase 8, Phase 9,
Phase 10, Phase 11, Phase 12, and Phase 7 are complete after this round is
fully verified, committed, and pushed.

Future work is now the read-only effectiveness review loop:

- Phase 13: perform read-only review of generated reports, evidence packages,
  AI memos, strategy scoreboards, and finished artifacts, then write review
  reports and decision records that judge whether the system is improving
  profit research effectiveness.

Live execution remains outside the current charter until a future explicit
charter revision.

## Next Round Entry Instructions

If work continues after Phase 7:

1. Read `docs/project-charter.md` before any new plan.
2. Read `docs/goals/project-completion-goal.md` and follow its Per-Round
   Execution Protocol exactly: Smart Search deep research before design,
   local code-feasibility verification before planning, evidence-first substep
   gates for every meaningful added capability, one Phase per round,
   Superpowers workflows, subagent use, repeated review/fix/re-review cycles,
   state synchronization, a complete Phase report under
   `docs/goals/phase-reports/`, and no next Phase until the current Phase is
   clean, verified, committed, and pushed.
3. Start Phase 13: Continuous Research Review And Reporting. Phase 7 added
   historical bootstrap; do not reimplement Phase 1 through Phase 12 or
   Phase 7.
4. Treat live execution, wallet keys, exchange order routing, private RPC,
   MEV, premium-RPC, and speed-edge paths as blocked unless the owner
   explicitly revises the charter.
5. Use the Phase 1/2 model routing: research/planning/code use the configured
   strong model and report/summary use the configured fast model. Preserve fake
   LLM tests for deterministic adversarial cases, and make real positive tests
   explicit and secret-safe.
6. For Phase 13, review generated reports, evidence packages, AI memos,
   strategy scoreboards, stopped-family ledgers, source-health rows, and
   decision records. Do not add product code or live execution.
7. Keep failed evidence and rejected assumptions in memory.
8. Update this file and `docs/roadmap.md` after the next milestone.

## Round History

| Round | Date | Slice | Verification | Commit | GitHub |
| --- | --- | --- | --- | --- | --- |
| 0 | 2026-05-17 | Goal contract bootstrap | pytest 676 passed; ruff passed; diff check passed; staged secret review passed | Goal bootstrap docs slice | public repo target |
| 1 | 2026-05-17 UTC / 2026-05-18 local | Complete autonomous evidence system milestone | pytest 750 passed; ruff passed; diff check passed; focused source tests 52 passed; forbidden-path review found no production live path | `fb1635d281f33e93a6723832bdf04a115e160c86` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 2 | 2026-05-23 | Immediate Phase 0 / merged Phase 6 worktree and configuration closeout | focused Phase 0 checks 8 passed; pytest 750 passed; ruff passed; diff check passed; staged secret review passed | Phase 0 completion commit `docs: complete phase 0 closeout` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 3 | 2026-05-23 | Immediate Phase 1 real LLM adapter | tests 762 passed; ruff passed; diff check passed; staged secret review passed | Phase 1 completion commit `feat: add real llm adapter` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 4 | 2026-05-23 | Immediate Phase 2 connect LLM to research loop | tests 770 passed; ruff passed; diff check passed; staged secret review passed | `ae3e601 feat: connect llm to research loop` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 5 | 2026-05-23 | Immediate Phase 3 real LLM test policy | focused Phase 3 tests 16 passed; pytest 785 passed; ruff passed; diff check passed; staged secret review passed | `9fb1945 test: formalize real llm policy` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 6 | 2026-05-23 | Immediate Phase 4 evidence run infrastructure | focused Phase 4 runner tests 19 passed; scheduler/docs 17 passed; complete/degradation 16 passed; pytest 797 passed; ruff passed; diff/staged checks passed; staged secret scan passed | `a31bda7 feat: add evidence run infrastructure` plus `c3b6127 docs: finalize phase 4 state` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 7 | 2026-05-23 | Immediate Phase 5 data and strategy expansion preparation | focused Phase 5 tests 29 passed; pytest 802 passed; ruff passed; review re-check found no Critical or Important findings | `f6964ab feat: add expansion preparation report` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 8 | 2026-05-24 | Phase 8 data depth and quality expansion | focused Phase 8 tests 61 passed; pytest 832 passed; ruff passed; diff/staged checks passed; path and staged secret scans returned [] | Phase 8 completion commit `feat: add source qualification workflow` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 9 | 2026-05-24 | Phase 9 strategy validator library expansion | focused Phase 9 tests 157 passed; pytest 868 passed; ruff passed; diff check passed; path secret scan returned [] | Phase 9 completion commit `feat: expand strategy validator library` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 10 | 2026-05-24 | Phase 10 execution realism and cost model | focused Phase 10 tests 48 passed; pytest 881 passed, 4 skipped; ruff passed; diff check passed; path secret scan returned [] | Phase 10 completion commit `feat: add execution realism cost model` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 11 | 2026-05-24 | Phase 11 AI researcher upgrade | focused Phase 11/end-to-end tests 53 passed; pytest 893 passed, 4 skipped; ruff passed | Phase 11 completion commit `feat: upgrade ai researcher evidence guards` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 12 | 2026-05-24 | Phase 12 profit evidence review and portfolio governance | focused Phase 12 tests 28 passed; pytest 898 passed, 4 skipped; ruff passed; diff check passed; path secret scan returned [] | `e89e008 feat: add profit governance report` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 13 | 2026-05-24 | Phase 7 final evidence campaign after factory buildout | focused Phase 7 tests 59 passed; pytest 912 passed, 4 skipped; ruff passed; diff and staged secret checks passed | `feat: add historical bootstrap campaign` | `https://github.com/WW-shan/Crypto_Research_Agent` |
