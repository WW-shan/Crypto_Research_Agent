# Project Completion State

This file is the working memory for the long-running Codex Goal defined in
`docs/goals/project-completion-goal.md`. Update it at the end of every completed
round.

## Current Round

- Round: 20
- Status: Profit Evidence Redesign completed as a data/feasibility slice. New
  public Binance USD-M derivatives ingestion works, but the proposed
  large-liquid momentum regime is blocked before strategy registration because
  local multi-symbol aligned 1h candle history is missing for ETH/USDT and
  SOL/USDT.
- Started: 2026-06-08
- Completed: 2026-06-08 data/feasibility closeout; focused tests, full pytest,
  ruff, diff check, staged diff, and staged secret checks passed; closeout
  commit pushed to `origin/main`.
- Active slice: Profit Evidence Redesign
- Active design source:
  `docs/superpowers/specs/2026-06-08-profit-evidence-redesign-design.md`
- Active plan source:
  `docs/superpowers/plans/2026-06-08-profit-evidence-redesign.md`
- Phase report:
  `docs/goals/phase-reports/2026-06-08-profit-evidence-redesign-report.md`

## Completed This Round

- Added the Profit Evidence Redesign design spec and implementation plan.
- Used deep Smart Search evidence to choose public Binance USD-M derivatives
  data as the next safe data upgrade after stopped funding-family governance.
- Added `binance_usdm_taker_buy_sell_volume` source-probe coverage and verified
  it through the proxy route with HTTP 200, parsed payload, one typed row,
  `provider_status=ResearchUsable`, `uses_real_capital=false`, and
  `live_order_routing=false`.
- Added strict typed records and public ingestion for Binance USD-M
  premium-index klines, basis, global long/short account ratio, and taker
  buy/sell volume.
- Added `ingest --source binance-usdm` CLI support and source-health writes for
  all four derivatives feeds.
- Live public-data smoke ingestion wrote 24 rows each for
  `premium_index_kline`, `basis`, `long_short_account_ratio`, and
  `taker_buy_sell_volume`.
- Added the read-only `strategy-feasibility` command for
  `large-liquid-momentum-regime`.
- Ran local feasibility and blocked strategy registration with
  `insufficient_aligned_history`: the database has 434 BTC/USDT 1h candles but
  0 ETH/USDT and 0 SOL/USDT 1h candles.
- Added this round's phase report documenting the data upgrade, blocker, and
  next safe action.

## Verification Evidence

- `uv run --extra dev pytest tests/test_source_probe.py -q` passed.
- `uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py
  tests/test_cli_ingest.py tests/test_documentation_contract.py -q` passed
  with 37 tests.
- `uv run --extra dev pytest tests/test_strategy_feasibility.py
  tests/test_documentation_contract.py -q` passed with 15 tests.
- Related ruff checks for new and touched files passed.
- Proxy-routed `binance_usdm_taker_buy_sell_volume` source-probe exited 0 with
  HTTP 200, parsed payload, `typed_record_count=1`,
  `provider_status=ResearchUsable`, `uses_real_capital=false`, and
  `live_order_routing=false`.
- Direct live ingestion through the new functions wrote 24 rows per new
  Binance USD-M derivatives feed and successful source-health rows for all
  four feeds.
- SQLite inspection showed 24 rows each for `premium_index_kline`, `basis`,
  `long_short_account_ratio`, and `taker_buy_sell_volume`.
- `strategy-feasibility` exited 0 and produced
  `var/reports/strategy-feasibility/latest.md` plus
  `var/reports/strategy-feasibility/latest.json`; the report is blocked with
  reason `insufficient_aligned_history`.

## Current Project Target

The prior Phase 13 completion state described a deterministic evidence factory.
The active next project line changes the runtime target: product commands must
be LLM-native and must not succeed through deterministic-only fallback.

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
- Phase 13 read-only review artifacts that inspect generated reports, evidence
  packages, AI memos, strategy scoreboards, stopped-family ledgers, and
  finished artifacts, then record explicit family and major-cycle decisions
  tied to evidence references instead of AI narrative.
- Phase 15 VPS operations layer that runs the LLM-native evidence factory as
  host-controlled Docker Compose jobs scheduled by systemd timers, with durable
  `var/` mounts, latest pointers, failed markers, logs, and backups.
- Phase 16 GHCR container publishing that lets VPS deployments pull
  `ghcr.io/ww-shan/crypto-alpha-agent:main` by default, while local builds can
  explicitly use `CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local`.
- Phase 17 creation-first Codex autonomy that stores creation backlog and task
  artifacts, asks the configured planning LLM for creation objects, runs Codex
  in isolated git worktrees, accepts only pytest verification commands, runs
  verification in a Docker sandbox, exports patches, promotes passing task
  worktrees to the persistent autonomy worktree, and writes latest creation
  reports.
- Bounded retries for real LLM structured-output schema drift in runtime
  judgement calls and experiment planning, without accepting live capital,
  live order routing, charter violations, unsupported validators, unsupported
  data fields, or missing evidence refs.
- Safe diagnostics for real LLM Responses payloads that return HTTP success but
  no extractable output text, while keeping raw provider payloads and secrets
  out of logs, reports, memory, and tests.

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

The Phase 0 through Phase 17 charter-compliant evidence-factory and autonomy
roadmap is implemented locally. The LLM-native runtime follow-up removed
deterministic-only product success paths. Phase 15 adds the VPS
Docker/systemd operations layer for unattended evidence collection, Phase 16
makes that runtime pullable from GHCR by default, and Phase 17 adds the
Codex-backed creation loop.

The previous hard operational blocker was the configured real LLM provider's
Responses route returning successful envelopes with no extractable model
output. The adapter now retries those empty Responses payloads and then uses the
same provider/model through Chat Completions as a compatibility fallback while
preserving strict schema requests and fail-closed parsing. `llm-health-check`
now passes against the real configured provider. Broad unattended product
operation still depends on the external provider continuing to respond within
reasonable time limits.

The latest public-data blocker was also remediated locally. The operator proxy
was present in `.env`, but ad hoc shell commands did not export it, and
auto-created CCXT exchange instances did not receive a ccxt `proxies` config.
`CcxtResearchCollector` now forwards local proxy environment values to ccxt,
and the successful `proxy-fixed-20260607T142806Z` evidence run confirms that
CCXT OHLCV/funding, DexScreener, and DefiLlama collection work through the
proxy route.

The 2026-06-08 Evidence Recovery Campaign removed the next ingestion blocker:
Binance USD-M open-interest history is reachable through the proxy route, CCXT
open-interest ingestion wrote typed `open_interest` records, and active-family
evidence runs for `funding_open_interest_crowding` and
`funding_mean_reversion_after_extreme` both reached validation and paper
simulation. The remaining blocker is profit-evidence quality, not ingestion:
all executable funding families are now stopped by governance because paper
outcomes are blocked, sample sizes are below target, walk-forward stability is
weak, and cost-adjusted expectancy is not positive. Do not use
`--allow-stopped-family` without explicit owner review. The next safe product
work requires a new evidence-first design for strategy redesign or a different
public-data-backed family; repeating the stopped funding families is not a
valid progress path.

The 2026-06-08 Profit Evidence Redesign added the next data slice: Binance
USD-M premium-index klines, basis, global long/short account ratio, and taker
buy/sell volume now have typed models, ingestion, source-health, tests, and
live public-data smoke evidence. Strategy registration remains blocked. The
new `strategy-feasibility` report found `insufficient_aligned_history` for the
large-liquid momentum regime because local storage has BTC/USDT 1h candles but
no ETH/USDT or SOL/USDT 1h candles for the same window. The next smallest
useful work is aligned multi-symbol OHLCV collection and then another
feasibility run, not strategy code. The CLI `ingest` real LLM readiness gate
also stalled during this slice and needs a bounded-timeout investigation before
it can be relied on as a smoke driver.

Reality audit: `docs/goals/project-reality-audit-2026-05-29.md` records that
the owner's broader autonomy target is larger than the completed Phase 0
through Phase 13 roadmap. Relative to that owner autonomy target, these
implementation gaps remain:

- `iteration-cycle` starts the closed auto-iteration loop by asking the
  configured real planning LLM for strict `IterationCandidate` records and
  guarding them against uncited evidence, missing tests, missing source probes,
  direct code-write authority, live capital, and live order routing.
- `creation-cycle` now starts the code-writing loop by asking the configured
  planning LLM for a strict `CreationObject`, running Codex in an isolated
  worktree, running pytest-only verification in a Docker sandbox, exporting a
  patch, and promoting passing task worktrees to an autonomy worktree. It still
  does not merge to `main`, push to GitHub, trade, route orders, or access
  wallets by itself.
- The autonomous code-writing loop is therefore implemented only as an
  isolated, reviewable worktree-and-patch loop; it is not an unattended
  production merge, publish, or live-execution loop.
- VPS unattended operation is available through Docker Compose and systemd
  timers with a GHCR-published container default, but it only repeats the
  existing LLM-native evidence/report/review/creation jobs and does not create
  an internal daemon or live execution path.
- autonomous new data source discovery remains probe-gated beyond the curated
  source-probe and query catalogs;
- accepted iteration candidates still require review and separate TDD
  implementation before any source, strategy, experiment, or code-change
  candidate can become `main` product code;
- the Phase 17 closeout commit is ready to publish after final staged review
  and secret scan; product runtime still requires a healthy LLM route before it
  can be declared fully green.

Operational evidence collection also remains necessary:

- collect ordinary public source data;
- run daily `evidence-run`, evidence reports, AI memos, governance reports, and
  review reports over time;
- accumulate 30/60/90 out-of-sample paper observations before any
  profit/no-profit owner decision;
- update the Phase 13 decision log when evidence changes.

Live execution remains outside the current charter until a future explicit
charter revision.

## Future Operation Instructions

If work continues after Phase 13:

1. Read `docs/project-charter.md` before any new plan.
2. Read `docs/goals/project-completion-goal.md` and follow its Per-Round
   Execution Protocol exactly: Smart Search deep research before design,
   local code-feasibility verification before planning, evidence-first substep
   gates for every meaningful added capability, one Phase per round,
   Superpowers workflows, subagent use, repeated review/fix/re-review cycles,
   state synchronization, a complete Phase report under
   `docs/goals/phase-reports/`, and no next Phase until the current Phase is
   clean, verified, committed, and pushed.
3. Do not start a new product-code phase unless the owner revises the roadmap
   or approves a new evidence-first strategy redesign plan. Current useful work
   is no longer repeating the stopped funding-family evidence runs; it is
   designing the next charter-compliant strategy or data-campaign slice from
   fresh source evidence and local feasibility checks.
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
8. Update this file and `docs/roadmap.md` only when the public roadmap or final
   project state changes.

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
| 14 | 2026-05-24 | Phase 13 continuous research review and reporting | deterministic pytest 912 passed, 4 skipped; ruff passed; diff and staged secret checks passed; local real LLM provider test failed schema and is non-gating | `9ca8966 docs: add phase 13 review records` plus final state sync | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 15 | 2026-05-29 | Phase 14 LLM-native autonomous iteration controller | focused Phase 14 tests 16 passed; pytest 965 passed; ruff passed; diff check passed; staged secret scan required before commit | Phase 14 implementation commit | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 16 | 2026-05-29 | Phase 15 VPS Docker operations runtime | focused VPS/docs contracts 24 passed; pytest 982 passed; final ruff, diff, staged diff, and staged secret checks required before commit | Phase 15 implementation commit | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 17 | 2026-05-29 | Phase 16 GHCR container publishing | focused GHCR/docs/runtime/planner contracts 81 passed; real LLM planner smoke 1 passed; pytest 990 passed; final ruff, diff, staged diff, and staged secret checks required before commit | Phase 16 implementation commit | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 18 | 2026-06-06 | Phase 17 creation-first Codex autonomy closeout | non-LLM pytest 1080 passed; focused Phase 17 tests 120 passed; adapter diagnostics and retry checks passed; focused LLM non-integration tests 46 passed, 1 deselected; real LLM health check passed after provider compatibility fallback; full real-provider suites remain sensitive to provider stalls | `22df14c docs: close out creation autonomy phase` plus remediation follow-up | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 19 | 2026-06-08 | Evidence Recovery Campaign | source-probe OI list/proxy qualification passed; CCXT OI ingest wrote 24 records; OI crowding run wrote 1 validation and 1 blocked paper outcome; mean-reversion fallback wrote 1 validation and 1 blocked paper outcome; governance report stopped all executable funding families; ruff, diff, staged diff, and staged secret checks passed | Evidence Recovery Campaign closeout commits pushed to `main` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 20 | 2026-06-08 | Profit Evidence Redesign | focused tests 54 passed; full pytest 1119 passed; ruff passed; diff/staged checks passed; staged secret scan returned []; Binance USD-M derivatives ingest wrote 24 rows per new feed; strategy feasibility blocked with `insufficient_aligned_history` | Profit Evidence Redesign closeout commit pushed to `main` | `https://github.com/WW-shan/Crypto_Research_Agent` |
