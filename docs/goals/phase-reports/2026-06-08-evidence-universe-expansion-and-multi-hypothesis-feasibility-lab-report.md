# Evidence Universe Expansion And Multi-Hypothesis Feasibility Lab Report

Date: 2026-06-08

## Scope

This phase expanded the upstream evidence funnel before any strategy
registration, paper queue handoff, or live-readiness review. The work added:

- Binance Public Data USD-M monthly kline support and ingestion.
- Source qualification for DefiLlama and DexScreener discovery routes.
- A point-in-time evidence universe builder.
- A read-only candidate screen catalog.
- A read-only multi-hypothesis feasibility lab.
- Explicit candidate state memory for pass/block/fail outcomes.
- A persistent backtest and paper handoff path map.

This phase did not add live execution, wallet access, exchange order routing,
exchange order submission, real-capital deployment, MEV, premium RPC, or any
speed-edge path.

## Research Evidence

Smart Search evidence path:

`var/smart-search-evidence/2026-06-08-expand-profit-evidence-loop/`

The source-backed constraints from that research pass remain binding:

- Binance global long/short and taker buy/sell data are recent derivatives
  context only because the official endpoints are latest-30-day limited.
- Binance Public Data is the public long-history route for historical klines,
  trades, and aggregate trades.
- DefiLlama and DexScreener are discovery or regime inputs until accumulated
  point-in-time snapshots and feasibility/backtest gates prove otherwise.
- Time-series validation must preserve chronological ordering.
- Cost realism, slippage/spread/liquidity assumptions, latency buffers, and
  lookahead checks are required before any later paper queue handoff.

## Source Qualification

The product `source-probe` and `ingest` CLI entry points fail closed in this
environment before source side effects because real LLM configuration is
missing. The observed CLI failure payloads reported
`llm_configuration_missing`, `side_effects_started=false`,
`uses_real_capital=false`, and `live_order_routing=false`.

To complete the read-only source evidence step, the lower-level source probe
functions were run directly and wrote source-health records to
`var/research.sqlite`:

| Source | Feed | Result | Route | Typed records | Notes |
| --- | --- | --- | --- | ---: | --- |
| DexScreener | pairs | blocked | unavailable | 0 | `request_failed:ConnectTimeout`; parse not attempted |
| DefiLlama | yield pools | success | direct | 15941 | HTTP 200, parsed, `ResearchUsable` |
| DefiLlama | fundamentals | success | direct | 6702 | HTTP 200, parsed, `ResearchUsable` |

DexScreener was therefore not treated as a qualified watchlist dataset in this
run. DefiLlama was source-qualified, but it was not promoted to executable
evidence.

## Market Data Coverage

Bounded Binance Public Data collection was run for USD-M futures monthly
klines, 1h timeframe, May 2026:

| Symbol | Records written | First timestamp | Latest timestamp |
| --- | ---: | --- | --- |
| BTC/USDT | 744 | 2026-05-01T00:00:00Z | 2026-05-31T23:00:00Z |
| ETH/USDT | 744 | 2026-05-01T00:00:00Z | 2026-05-31T23:00:00Z |
| SOL/USDT | 744 | 2026-05-01T00:00:00Z | 2026-05-31T23:00:00Z |

SQLite coverage after collection:

| Record type | Count |
| --- | ---: |
| `market_candle` | 2232 |
| `source_health` | 9 |

The first live collection attempt exposed that Binance Public Data monthly CSV
archives can include a kline header row. The parser initially failed with
`invalid literal for int() with base 10: 'open_time'`. A focused regression test
and parser fix now skip `open_time` header rows. After the fix, each symbol
collected 744 records successfully.

This is still only a bounded one-month evidence run. It is enough to exercise
the universe, candidate, cost, and memory pipeline, but it is not a 12-24 month
historical proof.

## Multi-Hypothesis Lab

Command output artifacts:

- Markdown: `var/reports/strategy-feasibility/multi-hypothesis-lab.md`
- JSON: `var/reports/strategy-feasibility/multi-hypothesis-lab.json`
- Candidate memory: `var/memory/candidate-state.jsonl`

Lab configuration:

- Mode: `multi-hypothesis-lab`
- Symbols: BTC/USDT, ETH/USDT, SOL/USDT
- Timeframe: 1h
- Walk-forward splits: 3 minimum
- Cost grid: 5, 10, 20, and 50 bps
- Real capital: false
- Live order routing: false

Overall result:

- Readiness: `blocked`
- Report reason codes:
  `non_positive_cost_adjusted_expectancy`,
  `unstable_walk_forward_performance`,
  `cost_sensitivity_fragile`,
  `insufficient_universe_coverage`,
  `watchlist_only_source`.

## Candidate Outcomes

| Candidate | Samples | Splits | Net mean at 10 bps | State target | Result reasons |
| --- | ---: | ---: | ---: | --- | --- |
| `short_horizon_momentum_volatility_filter` | 1078 | 3 | -0.00116133 | `redesign_required` | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `short_horizon_reversal_volatility_filter` | 1078 | 3 | -0.00101746 | `redesign_required` | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `perp_spot_basis_funding_deviation` | 0 | 0 | n/a | `candidate` | `insufficient_universe_coverage` |
| `derivatives_crowding_price_action` | 0 | 0 | n/a | `candidate` | `insufficient_universe_coverage` |
| `defi_dex_regime_discovery` | 0 | 0 | n/a | `redesign_required` | `watchlist_only_source`, `insufficient_universe_coverage` |
| `cross_asset_ranking_turnover_cap` | 356 | 3 | -0.00101732 | `redesign_required` | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |

The derivatives basis and crowding candidates were blocked by missing
derivatives universe coverage in this bounded run. They should not be recorded
as disproven strategies; they remain data-insufficient candidates.

## Cost Sensitivity

| Candidate | 5 bps net mean | 10 bps net mean | 20 bps net mean | 50 bps net mean |
| --- | ---: | ---: | ---: | ---: |
| `short_horizon_momentum_volatility_filter` | -0.00066133 | -0.00116133 | -0.00216133 | -0.00516133 |
| `short_horizon_reversal_volatility_filter` | -0.00051746 | -0.00101746 | -0.00201746 | -0.00501746 |
| `cross_asset_ranking_turnover_cap` | -0.00051732 | -0.00101732 | -0.00201732 | -0.00501732 |

All computed candidates were negative at every tested cost level. No computed
candidate passed the positive cost-adjusted expectancy gate.

## Candidate State Memory

The explicit `--persist-candidate-state` run wrote 10 candidate-state memory
records:

- 6 current screen candidates from the multi-hypothesis lab.
- 4 legacy derivatives-conditioned candidates from the previous feasibility
  lab:
  `long_short_crowding_contrarian`,
  `taker_imbalance_reversal`,
  `premium_basis_risk_filter`, and
  `momentum_derivatives_confirmation`.

The four legacy derivatives candidates were persisted as `redesign_required`
with `non_positive_cost_adjusted_expectancy`.

## Backtest And Paper Decision

No candidate entered `feasibility_passed`.

No candidate is eligible for the later event-driven backtest phase from this
run. Because no candidate passed feasibility, no candidate may enter
`backtest_passed`, `paper_collecting`, paper simulation, tiny-live review, or
live readiness.

The next evidence step is not trade execution. It is either:

- longer market-history collection and wider point-in-time universe coverage;
- source-qualified derivatives and DeFi/DEX snapshots sufficient to re-run the
  lab; or
- redesigned candidate hypotheses that can pass the same feasibility gates.

## Data Quality And Lookahead Notes

- The universe report preserved `point_in_time_universe=true`.
- The bounded lab universe had no reported quality issues for the available
  Binance Public Data market-candle records.
- DefiLlama and DexScreener data were not used as historical execution evidence.
- Today's discovery lists were not backfilled into historical tests.
- The one-month data window is a hard evidence limitation and must not be
  overrepresented as long-history validation.
- The next backtest phase remains gated on a future `feasibility_passed`
  candidate and must include double-sided fees, slippage, spread or liquidity
  assumptions, latency buffers, min notional, precision, partial or missed fill
  handling, monthly/yearly breakdowns, and lookahead-analysis style checks.

## Verification

Focused verification already completed during implementation:

- `uv run --extra dev pytest tests/test_binance_public_data.py -q`
  passed with 4 tests after the CSV-header fix.
- `uv run --extra dev ruff check src/crypto_alpha_agent/data/binance_public.py tests/test_binance_public_data.py`
  returned `All checks passed!`.
- The multi-hypothesis lab command exited 0 and wrote Markdown, JSON, and 10
  candidate-state records.

Final closeout verification:

- `uv run --extra dev pytest tests/test_binance_public_data.py tests/test_source_probe.py tests/test_evidence_universe.py tests/test_candidate_screens.py tests/test_multi_hypothesis_feasibility.py tests/test_candidate_state_memory.py tests/test_strategy_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py tests/test_documentation_contract.py -q`
  passed with 98 tests.
- `uv run --extra dev pytest tests/test_llm_researcher_adapter.py::test_research_task_can_include_ai_research_context tests/test_llm_researcher_adapter.py tests/test_llm_contracts.py -q`
  passed with 30 tests after the prompt-context field-name sanitization fix.
- `set -a; source /Users/ww/Project/Crypto_Research_Agent/.env; set +a; uv run --extra dev pytest -q`
  passed with 1197 tests. The `.env` file was sourced only for the command and
  was not copied, printed, staged, or committed.
- `uv run --extra dev ruff check .` returned `All checks passed!`.
- `git diff --check` passed.
- Staged diff check and staged secret scan passed before the final closeout
  commit.

## Safety Confirmation

This phase remains research-only:

- `uses_real_capital=false`
- `live_order_routing=false`
- no wallet keys
- no wallet-key access
- no exchange order routing
- no exchange order submission
- no live order path
- no live capital
- no strategy registry promotion from this lab
- no paper queue promotion from this lab
