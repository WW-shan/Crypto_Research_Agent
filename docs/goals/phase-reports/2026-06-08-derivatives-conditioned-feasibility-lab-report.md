# Derivatives-Conditioned Feasibility Lab Report

- Date: 2026-06-08
- Status: Completed as a read-only feasibility slice
- Design:
  `docs/superpowers/specs/2026-06-08-derivatives-conditioned-feasibility-lab-design.md`
- Plan:
  `docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md`
- Lab artifact:
  `var/reports/strategy-feasibility/derivatives-conditioned-lab.json`

## Summary

This slice extended the read-only `strategy-feasibility` workflow with a
derivatives-conditioned lab before any strategy registration. The implementation
adds strict lab models, local market/derivatives alignment, coverage
diagnostics, four candidate evaluators, and Markdown/JSON CLI artifacts for
Binance USD-M derivatives context.

The first local run used BTC/USDT, ETH/USDT, and SOL/USDT 1h candles plus
recent Binance USD-M basis, long/short account ratio, premium-index kline, and
taker buy/sell volume records. The report stayed `blocked` because every
candidate failed the cost-adjusted expectancy gate. No strategy registry entry,
paper runner, wallet path, live order route, or live capital path was added.

## Smart Search Evidence

- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/00-deep-plan.json`
- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/05-fetch-binance-long-short.md`
- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/06-fetch-binance-taker.md`
- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/07-fetch-defillama-faq.md`
- `var/smart-search-evidence/2026-06-08-next-strategy-redesign/08-fetch-dexscreener-reference.md`

## Local Feasibility Findings

SQLite market candle coverage before the lab run:

- BTC/USDT `market_candle`: 1000 rows,
  2026-04-27T12:00:00+00:00 to 2026-06-08T03:00:00+00:00.
- ETH/USDT `market_candle`: 1000 rows,
  2026-04-27T12:00:00+00:00 to 2026-06-08T03:00:00+00:00.
- SOL/USDT `market_candle`: 1000 rows,
  2026-04-27T12:00:00+00:00 to 2026-06-08T03:00:00+00:00.

SQLite Binance USD-M derivatives coverage before the lab run:

- `basis`: 500 rows each for BTCUSDT, ETHUSDT, and SOLUSDT,
  2026-05-18T15:00:00+00:00 to 2026-06-08T10:00:00+00:00.
- `long_short_account_ratio`: 500 rows each for BTCUSDT, ETHUSDT, and SOLUSDT,
  2026-05-18T16:00:00+00:00 to 2026-06-08T11:00:00+00:00.
- `premium_index_kline`: 500 rows each for BTCUSDT, ETHUSDT, and SOLUSDT,
  2026-05-18T16:00:00+00:00 to 2026-06-08T11:00:00+00:00.
- `taker_buy_sell_volume`: 500 rows each for BTCUSDT, ETHUSDT, and SOLUSDT,
  2026-05-18T15:00:00+00:00 to 2026-06-08T10:00:00+00:00.

The lab artifact reports 493 aligned market/derivatives records for each of
BTC/USDT, ETH/USDT, and SOL/USDT, with zero duplicate timestamps and no
per-symbol coverage blocker. Derivatives record totals were 1500 rows for each
of `basis`, `long_short_account_ratio`, `premium_index_kline`, and
`taker_buy_sell_volume`.

## Candidate Results

- `long_short_crowding_contrarian`: readiness `blocked`; reason codes
  `non_positive_cost_adjusted_expectancy`; observations 491; gross mean
  0.0004206520152146487; net mean -0.0005793479847853515; win rate
  0.4073319755600815; selected symbols ETH/USDT 17 and SOL/USDT 474; split net
  means -0.0006046264302122882, -0.00024592520433118714, and
  -0.00009748984824635497.
- `taker_imbalance_reversal`: readiness `blocked`; reason codes
  `non_positive_cost_adjusted_expectancy`; observations 492; gross mean
  0.0005688288829166332; net mean -0.000431171117083367; win rate
  0.42276422764227645; selected symbols BTC/USDT 198, ETH/USDT 122, and
  SOL/USDT 172; split net means -0.000658372949526737,
  -0.0008965914216619971, and 0.000347163847484194.
- `premium_basis_risk_filter`: readiness `blocked`; reason codes
  `non_positive_cost_adjusted_expectancy`; observations 491; gross mean
  0.0003311674616925808; net mean -0.0006688325383074194; win rate
  0.4093686354378819; selected symbols BTC/USDT 90, ETH/USDT 188, and SOL/USDT
  213; split net means -0.0011450362603508074, -0.000411893774893493, and
  0.00033193163994549264.
- `momentum_derivatives_confirmation`: readiness `blocked`; reason codes
  `non_positive_cost_adjusted_expectancy`; observations 176; gross mean
  0.000032269799957922047; net mean -0.000967730200042078; win rate
  0.3181818181818182; selected symbols BTC/USDT 176; split net means
  -0.0001942394487509473, -0.001054052042053019, and
  -0.0008452017705897148.

## Files Changed

- `src/crypto_alpha_agent/pipeline/strategy_feasibility.py`
- `src/crypto_alpha_agent/cli.py`
- `tests/test_strategy_feasibility.py`
- `docs/superpowers/specs/2026-06-08-derivatives-conditioned-feasibility-lab-design.md`
- `docs/superpowers/plans/2026-06-08-derivatives-conditioned-feasibility-lab.md`
- `docs/goals/project-completion-state.md`
- `docs/roadmap.md`
- `docs/goals/phase-reports/2026-06-08-derivatives-conditioned-feasibility-lab-report.md`

## Verification

- `uv run --extra dev pytest tests/test_strategy_feasibility.py -k
  'derivatives_conditioned_lab and not cli' -q`: 12 passed, 7 deselected.
- `uv run --extra dev pytest tests/test_strategy_feasibility.py -q`: 21
  passed.
- `uv run --extra dev pytest tests/test_documentation_contract.py -q`: 11
  passed after CLI wiring.
- `uv run --extra dev pytest tests/test_strategy_feasibility.py
  tests/test_cli_ingest.py tests/test_documentation_contract.py -q`: 42
  passed during final closeout.
- `uv run --extra dev pytest -q`: 1136 passed in 139.63s.
- `uv run --extra dev ruff check .`: `All checks passed!`.
- `git diff --check`: passed with no output.
- `git diff --cached --check`: passed with no output; staged names and stat
  contained only intended code, test, and docs files.
- `uv run python -m crypto_alpha_agent.security.secret_scan --staged
  --fail-on-empty-with-untracked`: returned `[]`.

## Decision

Strategy registration remains blocked. The next allowed work is a separate
evidence-first hypothesis or data-window design; it is not direct registry
modification from this lab slice.
