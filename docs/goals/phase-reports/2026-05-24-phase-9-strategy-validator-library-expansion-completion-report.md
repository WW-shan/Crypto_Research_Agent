# Phase 9 Strategy Validator Library Expansion Completion Report

Date: 2026-05-24

Commit reference: Phase 9 completion commit
`feat: expand strategy validator library`.

## Objective

Complete Phase 9 by expanding the deterministic strategy-validator library from
one primary executable funding validator plus two watchlists into at least three
executable paper-simulated families and at least three research-only watchlist
families. The round preserves no wallet keys, no live order routing, no live
execution, no wallet-key access, no order routing, no live capital, and
`live_execution_enabled=false`.

## External Evidence

Smart Search evidence was written to the phase-specific
`SMART_SEARCH_EVIDENCE_DIR` local evidence workspace during execution.

Source-backed findings used:

- Binance funding-rate history is public through the futures funding-rate
  history endpoint, is returned in ascending time order, and has strict request
  limits. This supports slow historical validation, not live execution.
- Binance open-interest statistics provide public historical open-interest rows
  with limited recent lookback. This supports an OI-confirmed funding validator
  when typed records are present.
- Binance basis data is public but has recent-history limits and basis/carry
  strategies need additional cost, leverage, borrow, and liquidation-risk
  assumptions before promotion.
- Perpetual-futures research supports using funding as a price-anchor signal,
  but notes that costs materially reduce Sharpe and that there is no guaranteed
  convergence like dated futures.
- Walk-forward validation references support time-ordered train/test splits and
  fail-closed handling when there are insufficient splits.
- DefiLlama and DEX Screener expose useful public slow-data and DEX liquidity
  surfaces, but broader DeFi fundamentals and DEX migration work remain
  watchlist or source-qualification work until typed historical coverage exists.
- BIS crypto-carry evidence warns that carry can have large drawdowns,
  liquidation risk, and frictions. Basis/carry remained blocked rather than
  promoted as an executable family.

## Local Feasibility

- The registry already supported `StrategyFamilySpec`, validation routing,
  paper simulation routing, and watchlist-only `paper_simulation_not_supported`
  outcomes.
- Existing typed records covered market candles, funding rates, open interest,
  DefiLlama yields, and DEX pairs after Phase 8.
- Existing funding-price validation and paper trade extraction could be reused
  for an OI-confirmed funding family.
- Existing evidence-run ingestion could instantiate the registry and conditionally
  ingest CCXT open-interest history only when an active family requires
  `open_interest`.
- Existing expansion-preparation reports could distinguish registered adapters
  from blocked candidates.

## Substep Validation And Prototypes

- A local typed-record prototype aligned OHLCV, funding-rate, and open-interest
  records into one OI-confirmed funding trade with nonzero raw return and a
  short-price direction.
- A local typed-candle prototype produced a volatility compression and expansion
  candidate using realized volatility, expansion return, and volume-change
  thresholds.
- Funding OI crowding was accepted for implementation because required records
  were typed and present.
- Volatility compression/expansion was accepted as a watchlist-only family
  because typed candles were present but no execution-realistic cost/liquidity
  model was in scope for Phase 9.
- Basis/carry, cross-exchange dispersion, and broader DeFi fundamentals were
  kept blocked by `blocked_by_missing_data` or
  `blocked_by_unqualified_source` until qualified multi-source data, cost
  assumptions, and repeated canary evidence exist.

## Implemented

- Added `src/crypto_alpha_agent/strategy/funding_oi_crowding.py`.
- Added `src/crypto_alpha_agent/strategy/volatility_regime_watchlist.py`.
- Updated `src/crypto_alpha_agent/strategy/registry.py` to register
  `funding_open_interest_crowding` as an executable paper-simulated family and
  `volatility_compression_expansion_watchlist` as a research-only watchlist.
- Updated `src/crypto_alpha_agent/validation/funding_price.py` and
  `src/crypto_alpha_agent/strategy/funding_mean_reversion.py` with fail-closed
  stale-source, unsupported-symbol, and excessive-drawdown gates.
- Updated `src/crypto_alpha_agent/pipeline/evidence_runner.py` to ingest
  open-interest history only when an active registered family requires
  `open_interest`.
- Updated `src/crypto_alpha_agent/pipeline/expansion_preparation.py` to promote
  the registered OI-crowding validator and volatility watchlist while retaining
  blocked candidates.
- Updated tests for funding validators, the new strategy families, registry
  counts, evidence-run OI ingestion, research-loop validation, expansion
  preparation, and documentation contracts.
- Updated README, runbook, asset assessment, roadmap, project state, and this
  report.

## Rejected Or Blocked Candidates

- Basis/carry was not promoted because external evidence emphasized carry
  frictions, margin constraints, drawdowns, and liquidation risk, and local
  typed basis/carry cost models are not yet present.
- Cross-exchange funding dispersion remained blocked because normalized
  multi-exchange funding history, capital fragmentation assumptions, exchange
  fees, and transfer/settlement constraints are not qualified enough for a
  deterministic executable validator.
- Stablecoin, TVL, fees, revenue, and broader DeFi fundamentals remained
  source-qualification and watchlist work until typed historical records and
  stable schemas exist.
- DEX liquidity migration remains watchlist-only and does not route to DEX
  execution, swap quotes, wallet signing, or live capital.

## Subagents

- Documentation auditor: reviewed roadmap, project state, phase-report
  conventions, and safety wording risks before implementation.
- Code auditor: reviewed registry, funding validators, watchlists, evidence-run,
  expansion-preparation seams, and recommended a low-risk path.
- Review pass 1 found Important registry gate-forwarding, per-feed
  staleness, OI symbol validation, OI ingestion isolation, volatility duplicate
  timestamp, experiment-planner, and expansion-preparation issues. All were
  fixed and re-reviewed.
- Review pass 2 found Important registry paper-gate, volatility non-positive
  price, OI min-trades, OI source-failure cache, and paper-run identity
  issues. All were fixed and re-reviewed.
- Final re-review found no Critical or Important findings remaining.

## Verification

- Focused implementation verification after review fixes:
  `uv run --extra dev pytest tests/test_funding_price_validator.py tests/test_funding_mean_reversion_strategy.py tests/test_funding_oi_crowding_strategy.py tests/test_volatility_regime_watchlist_strategy.py tests/test_strategy_registry.py tests/test_evidence_runner.py tests/test_research_loop_strategy_validation.py tests/test_paper_sim_loop.py tests/test_expansion_preparation.py tests/test_ai_experiment_planner.py -q`
  passed with 157 tests.
- Full verification:
  `uv run --extra dev pytest -q` passed with 868 tests.
- `uv run --extra dev ruff check .` passed.
- `git diff --check` passed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests`
  returned `[]`.

## Safety

- `uses_real_capital=false`
- `live_order_routing=false`
- `live_execution_enabled=false`
- No wallet keys, exchange live order routing, MEV, premium RPC, speed-edge
  execution, wallet-key access, order routing, live execution, live capital, or
  real-capital deployment were added.

## Remaining Gaps

- Phase 10 must add more conservative execution realism: fees, spread,
  slippage, funding timestamp alignment, borrow/carry assumptions, liquidity
  constraints, and low-capital sizing.
- The new OI-crowding family still needs future out-of-sample evidence and
  stronger execution-realism before any tiny-live review discussion.
- Watchlist families remain research-only and must not be treated as paper or
  live execution candidates without a future validator-specific plan.

## Next Phase

Phase 10 should make paper and backtest outputs more execution-realistic before
comparing strategy families for evidence strength or future rollout readiness.
