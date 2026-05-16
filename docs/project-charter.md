# Project Charter

This charter is the persistent decision record for the Crypto Alpha Agent project.
Future plans, implementation work, and agent behavior must align with it unless the
owner explicitly changes the charter.

## Primary Objective

The primary objective is to make money through reproducible crypto alpha research.
Engineering work is useful only when it improves the system's ability to discover,
validate, reject, or safely paper-test opportunities that could fit the owner's
capital and infrastructure constraints.

This project is not a technology showcase, a generic arbitrage bot, or a MEV
experiment. The system should prefer fewer, better-evidenced opportunities over
many noisy signals.

## Owner Profile And Constraints

The current operating profile is:

- Available capital: a few hundred USD.
- Infrastructure: ordinary internet access and ordinary public APIs.
- RPC/node access: no premium private RPC, no block-builder access, no mempool
  advantage, no colocation.
- Operational preference: automated research and paper validation first; no
  autonomous live trading by default.

These constraints are not temporary implementation details. They are core design
inputs. Any opportunity that requires speed, privileged order flow, premium RPC,
or large balance sheet should be recorded as research context but rejected as a
trade candidate for this owner profile.

## Allowed Opportunity Families

The system should prioritize low-frequency to medium-frequency opportunities
that can be researched, backtested, and paper-tested with modest capital:

- Funding-rate, basis, and open-interest anomalies where execution does not
  require millisecond latency.
- Historical price/volume/funding patterns that can be tested on free or
  low-cost market data.
- DEX pool, liquidity, and volume anomalies used as discovery signals, not as
  direct execution quotes.
- DeFi fundamentals such as TVL, yield, fees, revenue, stablecoin flows, and
  protocol regime changes.
- Cross-source confirmation signals such as price momentum plus funding
  extremity plus liquidity quality.

## Excluded Opportunity Families

The following should not be built as executable strategy paths for the current
owner profile:

- MEV, mempool extraction, sandwiching, private-order-flow strategies, or
  block-builder-dependent workflows.
- Sub-second CEX-DEX arbitrage.
- Flash-loan race strategies.
- Cross-chain bridge race strategies.
- Strategies that require premium RPC, private nodes, colocation, or unusually
  fast execution.
- Strategies whose minimum viable notional is meaningfully above the owner's
  available capital.

These categories may be stored as rejected research examples so the system can
learn why they are unsuitable.

## Execution Policy

The default mode is research-only. Paper trading is allowed when a candidate has
clear evidence, bounded downside assumptions, and a repeatable validation path.

Live trading is not an implementation default. Tiny live execution can only be
considered after:

- Positive net expectancy after fees, slippage, funding/borrow costs, and
  latency assumptions.
- Sufficient paper-trade sample size for the specific strategy family.
- Stable performance across walk-forward or out-of-sample checks.
- Risk guardian approval.
- Human approval.
- Rollout gate eligibility.

No code path should load wallet private keys, submit live exchange orders, or
route real capital unless a future charter revision explicitly authorizes that
phase and the rollout gates pass.

## Data Policy

The preferred first data sources are free or low-cost and suitable for ordinary
infrastructure:

- Binance Public Data for historical candles and trades.
- CCXT REST for normalized OHLCV and funding research pulls.
- DexScreener for DEX discovery snapshots.
- DefiLlama for DeFi yield and fundamentals.

Paid datasets such as historical L2 order books, institutional market data, or
premium on-chain providers should only be considered after a strategy family
shows promise on cheaper data.

## System Behavior Principles

The system should:

- Discover broadly, then filter aggressively.
- Preserve raw evidence and explain every decision.
- Mark weak signals explicitly instead of hiding uncertainty.
- Reject opportunities that are real but unsuitable for the owner's constraints.
- Treat social/news signals as supporting context, not primary execution
  evidence.
- Prefer paper validation over theoretical profitability.
- Keep a memory of rejected ideas and failed assumptions.

## Definition Of Done For The Project Vision

The project reaches its first complete research-loop milestone when it can run:

1. Real data ingestion.
2. Normalization into durable local storage.
3. Scanner signal generation with suitability tags.
4. Anomaly detection.
5. Hypothesis generation.
6. Backtest or historical validation.
7. Reflection and rejection/acceptance reasons.
8. Memory persistence.
9. Daily report generation.
10. Paper-trade proposal or paper simulation when appropriate.

The project reaches a tiny-live-readiness milestone only after repeated paper
evidence passes the rollout gates for a narrow, low-capital strategy family.

## Authority

When there is a conflict between an older plan and this charter, this charter
wins. Older arbitrage-oriented ideas must be reinterpreted through the current
owner profile: low capital, ordinary infrastructure, research and paper
validation first.
