# Project Completion State

This file is the working memory for the long-running Codex Goal defined in
`docs/goals/project-completion-goal.md`. Update it at the end of every completed
round.

## Current Round

- Round: 21
- Status: Derivatives-Conditioned Feasibility Lab completed as a read-only
  feasibility slice. The lab tested Binance USD-M derivatives-conditioned
  candidates before strategy registration; all four candidates were blocked by
  `non_positive_cost_adjusted_expectancy`, so no strategy registry entry, paper
  runner, wallet path, live order route, or live-capital path was added.
- Started: 2026-06-08
- Completed: 2026-06-08 after focused feasibility and CLI tests,
  documentation contract tests, full pytest, ruff, diff checks, staged diff
  review, and staged secret scan.
- Active slice: Derivatives-Conditioned Feasibility Lab
- Active design source:
  `docs/superpowers/specs/2026-06-08-derivatives-conditioned-feasibility-lab-design.md`
- Active plan source:
  `docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md`
- Phase report:
  `docs/goals/phase-reports/2026-06-08-derivatives-conditioned-feasibility-lab-report.md`

## Next Planned Round

- Round: 22
- Status: Planned and not implemented. Owner requested full persistence of the
  next path after deep research confirmed that the project must expand the
  upstream research funnel rather than trading execution.
- Planned slice:
  Evidence Universe Expansion and Multi-Hypothesis Feasibility Lab.
- Planned design source: the research-backed design is embedded in the plan
  and roadmap until a separate spec is written for the implementation slice.
- Planned plan source:
  `docs/superpowers/plans/2026-06-08-evidence-universe-expansion-and-multi-hypothesis-feasibility-lab.md`
- Smart Search evidence path:
  `var/smart-search-evidence/2026-06-08-expand-profit-evidence-loop/`
- Current actual state: the evidence factory, real LLM gates, source-health
  workflow, strategy feasibility modes, paper simulation, governance reports,
  and safe Codex creation loop are present, but no candidate has passed
  cost-adjusted feasibility or produced enough paper evidence for a profit
  decision.
- Current blocker: strategy evidence quality. The latest derivatives lab tested
  `long_short_crowding_contrarian`, `taker_imbalance_reversal`,
  `premium_basis_risk_filter`, and `momentum_derivatives_confirmation`; all
  four are blocked by `non_positive_cost_adjusted_expectancy`.
- Expected next state: a read-only upstream funnel that builds a wider
  point-in-time evidence universe, evaluates a larger candidate screen catalog,
  reports multi-hypothesis feasibility with cost sensitivity and walk-forward
  stability, persists pass/block/fail state memory, and sends only candidates
  that pass feasibility to a later backtest phase.

### Persisted Round 22 Research Conclusions

The next phase must expand every upstream evidence layer in this order:

1. **Data layer:** expand Binance Public Data long-history klines/trades and
   aggregate trades for a wider liquid universe. Keep Binance USD-M global
   long/short and taker buy/sell volume as recent derivatives context because
   the official docs limit those endpoints to recent history with max
   `limit=500`. Add DefiLlama TVL, fees/revenue, DEX/perp volume, yields, and
   stablecoin data plus DexScreener pair/liquidity/volume/trending metadata as
   discovery and regime inputs, not direct execution evidence.
2. **Data quality layer:** add coverage, staleness, duplicate, timestamp
   alignment, point-in-time universe, source-health, and proxy/direct route
   diagnostics. The universe builder must fail closed on survivorship or
   lookahead risk, especially when today's DEX or token discovery list would be
   backfilled into historical tests.
3. **Signal generation layer:** expand beyond the current four derivatives
   candidates into short-horizon momentum/reversal with volatility filters,
   perp/spot basis and funding deviation, derivatives crowding plus price
   action, DeFi/DEX discovery as watchlist or regime input, and cross-asset
   ranking with turnover caps.
4. **Feasibility layer:** add a read-only multi-hypothesis lab before any
   strategy registry change. Each candidate must report sample count, asset
   coverage, split coverage, gross mean, net mean, win rate, turnover,
   walk-forward net expectancy, cost sensitivity at 5/10/20/50 bps, and
   blocked reason codes.
5. **Backtest layer:** after feasibility passes, a separate phase must add
   event-driven cost-realistic backtests with double-sided fees, slippage,
   spread/liquidity assumptions, latency buffers, min notional, precision,
   partial/missed fill handling, timeframe-detail checks, monthly/yearly
   breakdowns, and lookahead-analysis style validation.
6. **Paper layer:** only candidates that pass feasibility and backtest gates
   may enter paper. Paper must record backtest expectation versus paper actual,
   30/60/90 observations, closed trades, failed trades, missed trades, net PnL,
   drawdown, cost drag, signal decay, and paper failure reasons.
7. **Governance layer:** every candidate moves through
   `candidate`, `source_qualified`, `feasibility_passed`, `backtest_passed`,
   `paper_collecting`, `stopped`, or `redesign_required`. The current four
   derivatives candidates should be persisted as rejected memory with
   `non_positive_cost_adjusted_expectancy` when the candidate-memory switch is
   implemented.
8. **Automation layer:** daily operation should update long-history and recent
   derivatives data, run candidate discovery, run multi-hypothesis feasibility,
   generate pass/fail rankings, and send only passed candidates to a later
   backtest or paper queue. Stopped families must not be silently rerun.

### Persisted Round 22 Path Map

1. **Source and universe expansion:** expand public long-history market data
   first, then qualify DefiLlama and DexScreener discovery inputs as
   watchlist/regime context rather than execution evidence.
2. **Data-quality and lookahead-risk gate:** require coverage, staleness,
   duplicate, timestamp-alignment, point-in-time universe, source-health, and
   proxy/direct route diagnostics before candidate scoring.
3. **Candidate screen registry:** keep the candidate screen registry read-only
   and separate from the strategy registry.
4. **Multi-hypothesis feasibility lab:** score multiple candidates with sample
   count, asset coverage, split coverage, gross/net mean, win rate, turnover,
   selected symbol counts, per-split net expectancy, and cost sensitivity.
5. **Event-driven backtest readiness and cost realism:** only candidates with
   `feasibility_passed` may enter a later backtest design, and that backtest
   must include double-sided fees, slippage, spread/liquidity assumptions,
   latency buffers, min notional, precision, partial/missed fills,
   monthly/yearly breakdowns, and lookahead-analysis style checks.
6. **Paper queue only after feasibility plus backtest pass:** only candidates
   with `backtest_passed` may enter `paper_collecting`.
7. **30/60/90 paper observation tracking:** paper must compare backtest
   expected versus actual at 30/60/90 observations and track closed trades,
   failed trades, missed trades, net PnL, drawdown, cost drag, signal decay,
   and paper failure reasons.
8. **Governance state machine and stopped/redesign memory:** persist
   `candidate`, `source_qualified`, `feasibility_passed`, `backtest_passed`,
   `paper_collecting`, `stopped`, and `redesign_required` state plus rejection
   reasons.
9. **Automated daily collection and ranking reports:** daily automation may
   update long-history and recent derivatives data, run discovery, run the
   multi-hypothesis lab, write pass/fail rankings, and send only state-qualified
   candidates to later backtest or paper queues.

Live execution remains blocked. Round 22 does not add wallet access, exchange
order routing, real-capital deployment, live orders, or any live execution
surface.

### Persisted Round 22 Non-Goals

- Do not directly register the current four derivatives candidates.
- Do not send a one-split or single-asset positive result to paper.
- Do not add live execution, wallet access, exchange order routing, live
  orders, or real-capital paths.
- Do not add MEV, CEX-DEX speed arbitrage, bridge races, flash loans, premium
  RPC, private order flow, colocation, or high-capital assumptions.
- Do not treat LLM autonomy expansion as the solution to the profit-evidence
  blocker; the current bottleneck is strategy evidence quality.

### Persisted Round 22 Source Evidence

- Binance long/short ratio:
  `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio`
- Binance taker buy/sell volume:
  `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Taker-BuySell-Volume`
- Binance public data:
  `https://github.com/binance/binance-public-data`
- DefiLlama docs:
  `https://docs.llama.fi/`
- DexScreener API:
  `https://docs.dexscreener.com/api/reference`
- Time-series split guidance:
  `https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html`
- Backtesting cost guidance:
  `https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/`
- Lookahead-bias check reference:
  `https://www.freqtrade.io/en/stable/lookahead-analysis/`
- Perpetual futures research:
  `https://arxiv.org/html/2212.06888v5`

## Completed This Round

- Added RED tests for a derivatives-conditioned feasibility lab covering
  missing derivatives history, blocked candidate diagnostics, feasible and
  rejected candidate combinations, duplicate timestamp fail-closed behavior,
  default candidates, period filtering, custom symbol maps, and CLI artifacts.
- Added strict lab models, symbol normalization, Binance USD-M derivatives row
  alignment, per-symbol coverage diagnostics, and four read-only candidate
  evaluators:
  `long_short_crowding_contrarian`, `taker_imbalance_reversal`,
  `premium_basis_risk_filter`, and `momentum_derivatives_confirmation`.
- Added `strategy-feasibility --mode derivatives-conditioned-lab` with
  Markdown and JSON artifacts, lab-only derivative symbol mapping,
  candidate-selection, period, split-count, and cost controls.
- Collected 500 recent rows for BTCUSDT, ETHUSDT, and SOLUSDT across each
  Binance USD-M derivatives feed:
  `basis`, `long_short_account_ratio`, `premium_index_kline`, and
  `taker_buy_sell_volume`.
- Re-ran local feasibility on BTC/USDT, ETH/USDT, and SOL/USDT 1h candles. Each
  symbol had 1000 market candles and 493 aligned market/derivatives records.
- The lab report stayed `blocked` with report reason
  `non_positive_cost_adjusted_expectancy`.
- Candidate outcomes:
  `long_short_crowding_contrarian`, `taker_imbalance_reversal`,
  `premium_basis_risk_filter`, and `momentum_derivatives_confirmation` were all
  blocked with `non_positive_cost_adjusted_expectancy`.
- Added this round's phase report documenting Smart Search evidence, local
  coverage, candidate metrics, verification, and the registration decision.

## Verification Evidence

- `uv run --extra dev pytest tests/test_strategy_feasibility.py -k
  'derivatives_conditioned_lab and not cli' -q` passed with 12 tests and 7
  deselected tests after the model implementation.
- `uv run --extra dev pytest tests/test_strategy_feasibility.py -q` passed with
  21 tests after CLI wiring.
- `uv run --extra dev pytest tests/test_documentation_contract.py -q` passed
  with 11 tests after CLI wiring.
- `uv run --extra dev pytest tests/test_strategy_feasibility.py
  tests/test_cli_ingest.py tests/test_documentation_contract.py -q` passed
  with 42 tests during final closeout.
- `uv run --extra dev pytest -q` passed with 1136 tests during final closeout.
- `uv run --extra dev ruff check .` returned `All checks passed!`.
- Diff checks, staged diff review, and staged secret scan passed before
  closeout commit.
- Each Task 4 network ingestion command exited 0 and reported
  `records_fetched=500` and `records_written=500`.
- SQLite inspection showed 1500 rows per derivatives record type across
  BTCUSDT, ETHUSDT, and SOLUSDT.
- Local market candle coverage remained 1000 rows each for BTC/USDT, ETH/USDT,
  and SOL/USDT.
- `strategy-feasibility --mode derivatives-conditioned-lab` exited 0 and wrote
  `var/reports/strategy-feasibility/derivatives-conditioned-lab.md` and
  `var/reports/strategy-feasibility/derivatives-conditioned-lab.json`.
- The local lab artifact reports `readiness=blocked`, report reason
  `non_positive_cost_adjusted_expectancy`, and `uses_real_capital=false` plus
  `live_order_routing=false`.

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
live public-data smoke evidence. The initial `insufficient_aligned_history`
blocker was resolved by collecting 1000 aligned BTC/ETH/SOL 1h candles, but
the large-liquid momentum regime still failed feasibility with
`non_positive_cost_adjusted_expectancy` across all three walk-forward splits.
The previous CLI `ingest` LLM readiness stall was not reproduced under bounded
diagnostics and should be treated as provider-latency risk rather than a
confirmed product bug.

The 2026-06-08 Derivatives-Conditioned Feasibility Lab then tested four
derivatives-conditioned hypotheses against the available BTC/ETH/SOL market and
Binance USD-M context. Strategy registration remains blocked because every
candidate failed the positive cost-adjusted expectancy gate with
`non_positive_cost_adjusted_expectancy`. The next smallest useful work is not a
strategy registry change; it is a new evidence-first hypothesis, a different
charter-compliant family, or a data-window design that can pass the feasibility
gate before product strategy code is added.

The persisted next path is now Round 22,
Evidence Universe Expansion and Multi-Hypothesis Feasibility Lab. That path
expands the upstream evidence funnel rather than execution: longer Binance
Public Data history, wider liquid universe construction, source-qualified
DefiLlama and DexScreener discovery inputs, point-in-time data-quality checks,
a read-only candidate screen registry, multi-hypothesis feasibility with
5/10/20/50 bps cost sensitivity, candidate state memory, and a later backtest
and paper handoff only for candidates that pass feasibility. The full plan is
`docs/superpowers/plans/2026-06-08-evidence-universe-expansion-and-multi-hypothesis-feasibility-lab.md`.

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
   fresh source evidence and local feasibility checks. The owner-approved next
   plan is Round 22, Evidence Universe Expansion and Multi-Hypothesis
   Feasibility Lab, persisted at
   `docs/superpowers/plans/2026-06-08-evidence-universe-expansion-and-multi-hypothesis-feasibility-lab.md`.
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
| 20 | 2026-06-08 | Profit Evidence Redesign | focused tests 54 passed; full pytest 1119 passed; follow-up pytest 1120 passed; ruff passed; diff/staged checks passed; staged secret scan returned []; Binance USD-M derivatives ingest wrote 24 rows per new feed; follow-up OHLCV ingest wrote 1000 rows each for BTC/ETH/SOL; strategy feasibility blocked with `non_positive_cost_adjusted_expectancy` | Profit Evidence Redesign closeout and follow-up commits pushed to `main` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 21 | 2026-06-08 | Derivatives-Conditioned Feasibility Lab | focused feasibility tests 21 passed; final focused suite 42 passed; documentation contract tests 11 passed; full pytest 1136 passed; ruff passed; diff/staged checks passed; staged secret scan returned []; Binance USD-M derivatives lab ingested 500 rows per feed/symbol and blocked all four candidates with `non_positive_cost_adjusted_expectancy` before strategy registration | Derivatives-Conditioned Feasibility Lab closeout commits pushed to `main` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 22 | 2026-06-08 | Evidence Universe Expansion and Multi-Hypothesis Feasibility Lab | planned only; Smart Search evidence persisted at `var/smart-search-evidence/2026-06-08-expand-profit-evidence-loop/`; plan persisted at `docs/superpowers/plans/2026-06-08-evidence-universe-expansion-and-multi-hypothesis-feasibility-lab.md`; implementation and verification pending | pending | `https://github.com/WW-shan/Crypto_Research_Agent` |
