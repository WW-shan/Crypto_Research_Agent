# Round 23 Main Integration And Lab Automation Report

Date: 2026-06-09

## Scope

This closeout integrated Round 22 and Round 23 into `main` and added a
read-only `evidence-universe-lab` command that runs the data-depth campaign and
multi-hypothesis feasibility v2 lab in one operator-controlled step.

This closeout does not open event-driven backtest, paper collection, tiny-live
review, wallet access, exchange order routing, exchange order submission, or
real-capital execution.

## Main Integration

- `main` was fast-forwarded from `048daa3` to Round 23 commit `733fc1a`.
- The integration brought in evidence universe source qualification,
  candidate screens, data-depth campaign planning/collection, feasibility v2,
  candidate-state memory, Round 22/Round 23 phase reports, and the Round 23
  roadmap/state updates.

## Automation Added

New CLI:

```bash
uv run crypto-alpha-agent evidence-universe-lab ...
```

The command writes:

- `evidence-universe-lab.md`
- `data-depth-campaign.md`
- `data-depth-campaign.json`
- `multi-hypothesis-feasibility.md`
- `multi-hypothesis-feasibility.json`
- the requested summary JSON
- candidate-state memory when `--persist-candidate-state` is set

The command keeps `uses_real_capital=false` and `live_order_routing=false`.
`--collect` requires `--allow-network`.

## Evidence Index

Round 22 and Round 23 Smart Search evidence is indexed at:

`docs/goals/evidence-index/2026-06-09-round-23-smart-search-evidence-index.md`

The raw evidence remains under ignored local `var/smart-search-evidence/`.

## Runtime Result

Main workspace command:

```bash
uv run crypto-alpha-agent evidence-universe-lab \
  --db var/research.sqlite \
  --memory var/memory/candidate-state.jsonl \
  --symbol BTC/USDT \
  --symbol ETH/USDT \
  --symbol SOL/USDT \
  --symbol BNB/USDT \
  --symbol XRP/USDT \
  --timeframe 1h \
  --start-year 2026 \
  --start-month 1 \
  --end-year 2026 \
  --end-month 5 \
  --min-unique-months 3 \
  --min-asset-count 3 \
  --min-split-count 3 \
  --purge-gap-bars 24 \
  --cost-bps-grid 5 \
  --cost-bps-grid 10 \
  --cost-bps-grid 20 \
  --cost-bps-grid 50 \
  --collect \
  --allow-network \
  --persist-candidate-state \
  --out-dir var/reports/evidence-universe-lab/round-23-main \
  --json-out var/reports/evidence-universe-lab/round-23-main/evidence-universe-lab.json
```

Result:

- Collection jobs: 25.
- Collection succeeded: 25.
- Collection failed: 0.
- Data-depth readiness: `ready`.
- Candidate-state memory records: 15.
- Candidates evaluated: 11.
- Feasible candidates: 0.
- Blocked candidates: 11.
- Eligible for backtest: `false`.
- Feasibility reasons:
  `insufficient_universe_coverage`,
  `non_positive_cost_adjusted_expectancy`,
  `unstable_walk_forward_performance`,
  `cost_sensitivity_fragile`, and `watchlist_only_source`.

Main workspace SQLite after the run:

- `market_candle`: 21120 rows.
- `source_health`: 91 rows.
- BNB/USDT 1h: 3624 rows from 2026-01-01 through 2026-05-31.
- BTC/USDT 1h: 4624 rows from 2026-01-01 through 2026-06-08.
- ETH/USDT 1h: 4624 rows from 2026-01-01 through 2026-06-08.
- SOL/USDT 1h: 4624 rows from 2026-01-01 through 2026-06-08.
- XRP/USDT 1h: 3624 rows from 2026-01-01 through 2026-05-31.

## Verification

- Focused CLI/docs verification:
  `uv run --extra dev pytest tests/test_cli_evidence_universe_lab.py tests/test_documentation_contract.py tests/test_cli_data_depth_campaign.py tests/test_cli_multi_hypothesis_feasibility.py -q`
  passed with 23 tests.
- Round 23 plus lab focused suite:
  `uv run --extra dev pytest tests/test_cli_evidence_universe_lab.py tests/test_data_depth_campaign.py tests/test_cli_data_depth_campaign.py tests/test_evidence_universe.py tests/test_candidate_screens.py tests/test_multi_hypothesis_feasibility.py tests/test_candidate_state_memory.py tests/test_cli_multi_hypothesis_feasibility.py tests/test_documentation_contract.py -q`
  passed with 76 tests.
- Local non-LLM suite:
  `uv run --extra dev pytest -q -m "not llm_integration"` passed with 1204
  tests and 10 deselected real LLM integration tests.
- Full suite:
  `uv run --extra dev pytest -q` passed with 1214 tests.
- Static and patch checks:
  `uv run --extra dev ruff check .` returned `All checks passed!`;
  `git diff --check` returned no whitespace errors.

## Remaining Hard Blocker

No candidate has reached `feasibility_passed`. Backtest, paper collection, and
live readiness remain blocked until a later candidate passes feasibility v2
with positive net expectancy, stable purged walk-forward splits, sufficient
asset/month coverage, and non-fragile cost sensitivity.
