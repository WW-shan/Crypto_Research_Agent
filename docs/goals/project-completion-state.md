# Project Completion State

This file is the working memory for the long-running Codex Goal defined in
`docs/goals/project-completion-goal.md`. Update it at the end of every completed
round.

## Current Round

- Round: 19
- Status: Evidence Recovery Campaign completed as an operations/documentation
  round with a documented profit-evidence blocker: public-data ingestion,
  open-interest ingestion, validation, paper simulation, and governance paths
  ran successfully, but both active funding families tested in this round were
  stopped by deterministic governance after blocked paper outcomes and weak
  validation.
- Started: 2026-06-08
- Completed: 2026-06-08 operations/docs closeout; final ruff, diff, staged
  diff, and staged secret checks passed; closeout commits pushed to
  `origin/main`
- Active slice: Evidence Recovery Campaign
- Active design source:
  `docs/superpowers/specs/2026-06-08-evidence-recovery-campaign-design.md`
- Active plan source:
  `docs/superpowers/plans/2026-06-08-evidence-recovery-campaign.md`
- Phase report:
  `docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md`

## Completed This Round

- Added and committed the Evidence Recovery Campaign design spec:
  `docs/superpowers/specs/2026-06-08-evidence-recovery-campaign-design.md`.
- Added and committed the Evidence Recovery Campaign implementation plan:
  `docs/superpowers/plans/2026-06-08-evidence-recovery-campaign.md`.
- Confirmed the baseline evidence gap:
  `funding_extremity_price_confirmation` had 3 old validation records and 3
  old blocked paper outcomes, while no `open_interest` records existed before
  this campaign.
- Confirmed latest pre-campaign run `proxy-fixed-20260607T142806Z` restored
  public-data collection through the proxy route but wrote no new validation
  evidence and no paper outcomes because the default stopped family was
  skipped.
- Qualified Binance USD-M open-interest history through `source-probe`:
  no-network probing failed closed with `network_not_allowed`; proxy-route
  probing returned HTTP 200, parsed output, `typed_record_count=1`, and
  `provider_status=ResearchUsable`.
- Qualified local CCXT open-interest ingestion by writing 24
  `BTC/USDT:USDT` open-interest records through the proxy route, then
  confirmed positive open-interest values and a 2026-06-07T02:00:00Z through
  2026-06-08T01:00:00Z observed window.
- Ran active-family evidence recovery for
  `funding_open_interest_crowding` with run id
  `evidence-recovery-oi-20260608T015547Z`. The run succeeded through the proxy
  route, wrote 200 OHLCV records, 200 funding records, 200 open-interest
  records, 1 validation evidence item, and 1 blocked paper outcome. No stopped
  family override was used.
- Ran fallback active-family evidence recovery for
  `funding_mean_reversion_after_extreme` with run id
  `evidence-recovery-mean-reversion-20260608T020000Z`. The run succeeded
  through the proxy route, wrote 200 OHLCV records, 200 funding records, 1
  validation evidence item, and 1 blocked paper outcome. No stopped-family
  override was used.
- Confirmed both new validation rows are not approved and share these blocked
  reasons: `no_extreme_funding`, `insufficient_trades`,
  `non_positive_expectancy`, `non_positive_net_return`, and
  `unstable_walk_forward_performance`.
- Generated `var/reports/evidence-recovery/governance-latest.md`. Governance
  now marks all three executable funding families as `stop`; DeFi, DEX, and
  volatility watchlists remain `add_data`; the paper-only portfolio selector
  has no candidate.
- Added this round's campaign report documenting the blocker and next safe
  action.

## Verification Evidence

- `uv run --extra dev crypto-alpha-agent source-probe --list-targets` exited 0
  and listed `binance_usdm_open_interest_history`.
- `uv run --extra dev crypto-alpha-agent source-probe --db
  var/research.sqlite --target binance_usdm_open_interest_history` exited 2
  with `blocked_reason=network_not_allowed`, `network_route=blocked`,
  `uses_real_capital=false`, and `live_order_routing=false`.
- Proxy-routed source probe exited 0 with HTTP 200, parsed payload,
  `typed_record_count=1`, `provider_status=ResearchUsable`,
  `uses_real_capital=false`, and `live_order_routing=false`.
- Proxy-routed CCXT open-interest ingestion exited 0 and wrote 24
  `open_interest` records for `BTC/USDT:USDT`.
- SQLite inspection after OI ingestion showed 24 rows for `BTC/USDT:USDT` on
  `binance`, observed between 2026-06-07T02:00:00+00:00 and
  2026-06-08T01:00:00+00:00, with open interest values from 98293.307 to
  103160.276.
- `evidence-recovery-oi-20260608T015547Z` exited 0 and wrote 1 validation
  evidence item plus 1 blocked paper outcome for
  `funding_open_interest_crowding`.
- `evidence-recovery-mean-reversion-20260608T020000Z` exited 0 and wrote 1
  validation evidence item plus 1 blocked paper outcome for
  `funding_mean_reversion_after_extreme`.
- SQLite ledger inspection showed both new families have blocked validation
  reasons `no_extreme_funding`, `insufficient_trades`,
  `non_positive_expectancy`, `non_positive_net_return`, and
  `unstable_walk_forward_performance`.
- `uv run --extra dev crypto-alpha-agent governance-report --db
  var/research.sqlite --memory var/memory/evidence.jsonl --out
  var/reports/evidence-recovery/governance-latest.md --current-capital-usd
  300` exited 0. The report kept `Real capital: false` and
  `Live order routing: false`, stopped all executable funding families, and
  produced no paper portfolio candidate.
- `uv run --extra dev ruff check .` passed.
- `git diff --check` passed.
- Staged file review included only:
  `docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md`,
  `docs/goals/project-completion-state.md`, `docs/roadmap.md`, and
  `docs/superpowers/plans/2026-06-08-evidence-recovery-campaign.md`.
- `git diff --cached --check` passed.
- `git diff --cached --no-ext-diff --unified=0` was reviewed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --staged
  --fail-on-empty-with-untracked` returned `[]`.
- Closeout commits were pushed to `origin/main` after staged checks passed.

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
