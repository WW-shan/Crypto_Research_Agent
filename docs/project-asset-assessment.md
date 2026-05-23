# Project Asset Assessment And Experiment Priority

This document records how existing project assets should be prioritized for
future experiments. It is not a permanent rejection list. Lower-priority items
remain available for later testing when higher-priority evidence, data, and
safety gates are in place.

Use this assessment when planning future Phases. If a future idea conflicts
with this document, resolve it through the current charter, Smart Search
evidence, local code/data feasibility checks, and the evidence-first substep
gate.

## Priority Rule

Prioritize work that can produce useful profit evidence under the owner's
current constraints:

- a few hundred USD of capital;
- ordinary public APIs and local proxy routing;
- no speed edge;
- no premium RPC or private infrastructure requirement;
- research, validation, paper simulation, and review before live capital.

Lower priority means "test later after prerequisites exist," not "delete
forever."

## P0: Core Evidence Factory Assets

These are the foundation for every future experiment and should be preserved
and strengthened first.

- `docs/project-charter.md`, `docs/roadmap.md`, `docs/goals/`: preserve the
  low-capital, no-speed-edge, no-live-execution operating profile.
- `src/crypto_alpha_agent/data/store.py`, `models.py`, `quality.py`: durable
  SQLite records, typed data models, and data-quality reporting.
- Binance Public Data and CCXT ingestion: historical OHLCV, funding, and
  typed open-interest history where the exchange supports public market data.
- `source-probe`, `docs/source-coverage-matrix.md`, and
  `docs/source-query-catalog.md`: source qualification, proxy-aware
  source-health evidence, and query inventory for Phase 9 validator work.
- `research-loop`: stored data to scanner, anomaly, hypothesis, validation, and
  report.
- `paper-sim-loop` and `execution/cost_model.py`: deterministic historical
  and paper simulation outcomes with Phase 10 execution-realism assumptions.
  Paper outcomes now record `cost_model_mode`, pessimistic maker/taker fee
  assumptions, min-notional and precision feasibility, stale-signal status,
  `pre_cost_only_profitable`, `missed_fill_assumed`, and `partial_fill`
  evidence before any rollout review.
- `evidence-run`: daily evidence pipeline foundation.
- `evidence-report`: daily and weekly reporting foundation.
- `validation/funding.py`, `validation/funding_price.py`,
  `validation/walk_forward.py`: first strategy family and validator templates.
- `strategy/funding_oi_crowding.py`: executable funding validator that uses
  typed open-interest history as a crowding confirmation before paper
  simulation.
- `strategy/volatility_regime_watchlist.py`: research-only volatility
  compression and expansion watchlist; it must remain paper-disabled unless a
  future phase adds a separate executable validator.
- `evidence/ledger.py`, `evidence/validation_ledger.py`, `evidence/paper.py`:
  evidence accumulation, validation records, and paper evidence packages.
- `memory/store.py` and `pipeline/memory.py`: durable memory for failed
  assumptions, blocked reasons, and future AI retrieval.
- `risk/charter_guard.py`, `risk/paper_gate.py`, `risk/guardian.py`: safety
  boundaries against live execution, wallet access, MEV, high capital, and
  unsupported paper promotion.
- `strategy/registry.py`: required registry boundary for future validators.
- The existing test suite: the main safety net for future evidence-factory
  work.

## P1: Upgrade Next

These assets are useful soon, but need stronger data, real LLM integration,
or better evidence contracts before they become central.

- `agents/llm_contracts.py`, `agents/llm_researcher.py`,
  `pipeline/ai_research_context.py`, and `pipeline/experiment_planner.py`:
  now form the Phase 11 AI researcher contract. Continue hardening with real
  positive LLM tests, but keep proposals evidence-grounded, schema constrained,
  and unable to create paper outcomes or route orders.
- `strategy/funding_mean_reversion.py`: continue testing with richer funding,
  open-interest context, cost, and out-of-sample evidence.
- `data/dexscreener.py`: prioritize storing local snapshots over time before
  treating it as historical evidence.
- `data/defillama.py`: expand from existing yield snapshots and Phase 8
  source-probe fundamentals into typed slow fundamentals, TVL, stablecoins,
  fees, and revenue.
- `tools/dune.py` and `tools/thegraph.py`: promote only after their query
  catalog entries pass source-specific schema checks and repeated canary runs.
- `scheduler.py`: upgrade with run manifests, locks, failed-run markers, and
  artifact retention.
- `observability/` and `tools/http.py`: reuse for source probes, retries,
  redaction, replay, and long-running evidence operations.

## P2: Watchlist And Later Experiment Assets

These are useful, but should follow P0/P1 work because they are less directly
connected to immediate low-capital profit evidence.

- `strategy/defi_yield_regime.py`: useful as a watchlist and regime input.
  Test after DefiLlama, Dune, or TheGraph slow-data quality is stronger.
- `strategy/dex_liquidity_watchlist.py`: useful for liquidity migration
  watchlists. Test after DexScreener snapshots have enough local history.
- Strategy code sandbox: useful later for AI-assisted validator drafts, but
  only after deterministic tests, data feasibility, and human review.
- Generic multi-agent role expansion: test only when a new role improves data
  quality, validation quality, or review quality.
- Early paper execution code: useful as simulation infrastructure, not as proof
  of executable liquidity.

## P3: Safety Boundary And Future Optional Assets

These remain in the project as safety boundaries or future references. They are
not near-term experiment priorities under the current owner profile.

- `execution/freqtrade_adapter.py` and `execution/hummingbot_adapter.py`: keep
  as adapter boundaries and future references. Do not develop live routing in
  the current roadmap.
- `evidence/live_readiness.py`, `docs/tiny-live-readiness.md`, and
  `rollout-review`: keep as safety/review artifacts. Do not make them the main
  project focus before profit evidence exists.
- CEX-DEX speed arbitrage, bridge-race arbitrage, mempool/MEV extraction,
  sandwiching, flash-loan races, and sub-second execution games: experiment
  only if future constraints change enough to provide speed and infrastructure
  edge.
- Premium RPC, private nodes, colocated infrastructure, private order flow, or
  large-balance strategies: experiment only if a future owner profile supports
  those costs and risks.
- Wallet private-key loading, exchange live order routing, automatic live
  execution, or real-capital deployment: only after an explicit future charter
  revision and a separate implementation plan.
- AI-generated strategy code that bypasses deterministic validators, evidence
  gates, review, and tests: never promote directly. It may only become a draft
  for a reviewed and tested validator.
- DeFi narrative-only alpha: test only after it is tied to qualified data and a
  validator or watchlist evidence contract.

## Experiment Rule

Future Phases should preserve and strengthen this path:

1. Qualify public data sources.
2. Normalize and store data durably.
3. Validate strategy families deterministically.
4. Apply realistic costs and low-capital constraints.
5. Record blocked, failed, and rejected assumptions.
6. Produce daily, weekly, and Phase review reports.
7. Let AI propose bounded experiments only through available data, evidence
   refs, supported data gaps, registered validators, or design-only validator
   templates that still require deterministic tests and human review.
8. Use Phase 13 as read-only review and decision-record writing.

When lower-priority ideas are tested, they must still pass the same
evidence-first gate: Smart Search evidence, local data/code feasibility, small
prototype or historical validation, and only then project implementation.
