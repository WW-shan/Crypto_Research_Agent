# Profit Evidence Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute the next charter-compliant path from public data to profit evidence after all executable funding families were stopped.

**Architecture:** Start with public Binance USD-M derivatives factor ingestion because source-probe already proves several endpoints are reachable and parseable through the local proxy. Use a report-local feasibility gate before registering any new paper-simulated strategy family, so the project does not add another weak family to the stopped ledger.

**Tech Stack:** Python 3.12, Pydantic strict models, requests, SQLite `source_records`, existing `source-probe`, `ingest`, strategy registry, paper simulation, governance report, pytest, ruff.

---

## Current Gap List

| Gap | Actual | Expected | Required fix |
| --- | --- | --- | --- |
| Approved validation | 0 rows | at least one approved validation before paper evidence | new feasible family or data-backed redesign |
| Paper outcomes | 0 closed, 5 blocked | at least 30 clean observations for rollout relevance | stop repeating stopped funding families |
| Strategy governance | all executable funding families stopped | at least one active executable family | add only after feasibility pass |
| OI source | typed ingestion exists | usable but current OI family stopped | keep as supporting data, not enough alone |
| Basis/premium/long-short/taker data | source-probe only for 3 of 4 feeds | typed persisted records | add Binance USD-M derivatives ingestion |
| Taker buy/sell source-probe | missing target | source-probe target plus parser | add target and tests |
| DeFi/DEX data | watchlist snapshots only | research context, not paper evidence yet | keep research-only until historical snapshots exist |
| Time-series validation | existing walk-forward gates | still fail for funding families | use feasibility before new strategy registration |
| Goal tool state | previous goal complete; cannot create second goal in thread | owner asked to use goal | record limitation, continue documented execution |

## Research Evidence

Use these local evidence files:

- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/01-broad-strategy-search.json`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/02-binance-market-data-search.json`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/03-crypto-momentum-paper-search.json`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/04-defi-dex-source-search.json`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/05-binance-open-interest-statistics.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/06-binance-long-short-ratio.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/07-binance-taker-buy-sell-volume.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/08-binance-premium-index-kline.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/09-binance-basis.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/11-dexscreener-api.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/12-binance-public-data.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/13-defillama-faq.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/14-crypto-momentum-reversal-hse.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/15-size-volume-momentum-reversal.md`
- `var/smart-search-evidence/2026-06-08-profit-evidence-redesign/16-sklearn-time-series-split.md`

## Completed Pre-Implementation Checks

- [x] **Step 0.1: Run Smart Search deep planner**

Run:

```bash
smart-search deep "Crypto Research Agent profit-evidence blocker: find charter-compliant low-capital public-data crypto strategy redesign solutions after funding strategies stopped; need slow public data, no live execution, no MEV, no premium infrastructure, evidence-first validation, paper simulation, walk-forward, 30/60/90 out-of-sample plan" --budget deep --format json
```

Expected: returns `mode=deep_research`, `difficulty=high`,
`evidence_policy=fetch_before_claim`.

- [x] **Step 0.2: Fetch key sources**

Run the source fetch commands recorded in the evidence directory.

Expected: Binance, DexScreener, DeFiLlama, academic paper, and TimeSeriesSplit
evidence files exist.

- [x] **Step 0.3: Probe existing Binance derivative targets**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; uv run --extra dev crypto-alpha-agent source-probe --db var/research.sqlite --target binance_usdm_premium_index_klines --allow-network --route proxy'
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; uv run --extra dev crypto-alpha-agent source-probe --db var/research.sqlite --target binance_usdm_basis --allow-network --route proxy'
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; uv run --extra dev crypto-alpha-agent source-probe --db var/research.sqlite --target binance_usdm_global_long_short_account_ratio --allow-network --route proxy'
```

Expected: all exit 0, return HTTP 200, parsed output, one typed record,
`provider_status=ResearchUsable`, `network_route=proxy`,
`uses_real_capital=false`, and `live_order_routing=false`.

## Task 1: Add Taker Buy/Sell Source-Probe Target

**Files:**

- Modify: `src/crypto_alpha_agent/data/source_probe.py`
- Modify: `tests/test_source_probe.py`

- [x] **Step 1.1: Write failing test**

Add a test in `tests/test_source_probe.py` that asserts
`binance_usdm_taker_buy_sell_volume` appears in `available_probe_targets()`
with:

```python
def test_source_probe_lists_binance_taker_buy_sell_volume_target():
    target_ids = {target.target_id for target in available_probe_targets()}

    assert "binance_usdm_taker_buy_sell_volume" in target_ids
```

Also add a target-details assertion:

```python
def test_binance_taker_buy_sell_volume_target_uses_public_endpoint():
    target = next(
        item
        for item in available_probe_targets()
        if item.target_id == "binance_usdm_taker_buy_sell_volume"
    )

    assert target.source == "binance_usdm"
    assert target.feed == "taker_buy_sell_volume"
    assert target.endpoint_family == "GET /futures/data/takerlongshortRatio"
    assert "takerlongshortRatio" in target.url
    assert target.credential_requirement == "none"
    assert target.expected_fields == ("buySellRatio", "buyVol", "sellVol", "timestamp")
```

- [x] **Step 1.2: Verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_source_probe.py::test_source_probe_lists_binance_taker_buy_sell_volume_target tests/test_source_probe.py::test_binance_taker_buy_sell_volume_target_uses_public_endpoint -q
```

Expected: FAIL because the target does not exist.

Actual: failed with assertion that
`binance_usdm_taker_buy_sell_volume` was not present and `StopIteration` in the
detail lookup.

- [x] **Step 1.3: Implement target**

Add this `SourceProbeTarget` to `_TARGETS` in
`src/crypto_alpha_agent/data/source_probe.py` near the other Binance USD-M
derivatives targets:

```python
SourceProbeTarget(
    target_id="binance_usdm_taker_buy_sell_volume",
    display_name="Binance USD-M Taker Buy/Sell Volume",
    source="binance_usdm",
    feed="taker_buy_sell_volume",
    endpoint_family="GET /futures/data/takerlongshortRatio",
    url_family="binance_usdm_taker_buy_sell_volume",
    url=(
        "https://fapi.binance.com/futures/data/takerlongshortRatio"
        "?symbol=BTCUSDT&period=1h&limit=1"
    ),
    typed_count_path=(),
    expected_fields=("buySellRatio", "buyVol", "sellVol", "timestamp"),
    rate_limit_assumption="latest 30 days and 1000 requests per 5 minutes per Binance docs",
),
```

- [x] **Step 1.4: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_source_probe.py::test_source_probe_lists_binance_taker_buy_sell_volume_target tests/test_source_probe.py::test_binance_taker_buy_sell_volume_target_uses_public_endpoint -q
```

Expected: PASS.

Actual: 2 passed.

- [x] **Step 1.5: Probe through proxy**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; uv run --extra dev crypto-alpha-agent source-probe --db var/research.sqlite --target binance_usdm_taker_buy_sell_volume --allow-network --route proxy'
```

Expected: exit 0, HTTP 200, parsed payload, `typed_record_count=1`,
`provider_status=ResearchUsable`, `uses_real_capital=false`,
`live_order_routing=false`.

Actual: exit 0, HTTP 200, `parse_status=parsed`, `typed_record_count=1`,
`provider_status=ResearchUsable`, `network_route=proxy`,
`uses_real_capital=false`, and `live_order_routing=false`.

## Task 2: Add Binance USD-M Derivatives Models

**Files:**

- Modify: `src/crypto_alpha_agent/data/models.py`
- Create or modify: `tests/test_binance_usdm_derivatives_ingestion.py`

- [x] **Step 2.1: Write model tests**

Add tests that validate these strict models and `to_source_record()` behavior:

- `PremiumIndexKlineRecord`
- `BasisRecord`
- `LongShortRatioRecord`
- `TakerBuySellVolumeRecord`

Each record must include source, venue, symbol or pair, timestamp, timeframe or
period, parsed numeric fields, research suitability, and raw payload.

- [x] **Step 2.2: Verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py -q
```

Expected: FAIL because models do not exist.

Actual: failed with missing model assertions for the four new models.

- [x] **Step 2.3: Implement models**

Extend `RecordType` with:

```python
"premium_index_kline",
"basis",
"long_short_account_ratio",
"taker_buy_sell_volume",
```

Add strict Pydantic models with nonnegative finite prices or volumes where
required. Allow signed `premium` and signed `basis_rate` where official payloads
can be negative.

- [x] **Step 2.4: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py -q
```

Expected: PASS.

Actual: 4 passed.

## Task 3: Add Public Binance USD-M Derivatives Client

**Files:**

- Create: `src/crypto_alpha_agent/data/binance_usdm_derivatives.py`
- Modify: `tests/test_binance_usdm_derivatives_ingestion.py`

- [x] **Step 3.1: Write client parser tests**

Use fake HTTP/session objects. Test methods:

- `fetch_premium_index_klines(symbol="BTCUSDT", interval="1h", limit=2)`
- `fetch_basis(pair="BTCUSDT", contract_type="PERPETUAL", period="1h", limit=2)`
- `fetch_global_long_short_account_ratio(symbol="BTCUSDT", period="1h", limit=2)`
- `fetch_taker_buy_sell_volume(symbol="BTCUSDT", period="1h", limit=2)`

Expected: returned typed records match official response fields and preserve
raw payloads.

- [x] **Step 3.2: Verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py -q
```

Expected: FAIL because client does not exist.

Actual: failed with `ModuleNotFoundError` for
`crypto_alpha_agent.data.binance_usdm_derivatives`; model tests stayed green.

- [x] **Step 3.3: Implement client**

Implement a small requests-based client with:

- default base URL `https://fapi.binance.com`
- injected session support for tests
- explicit timeout
- proxy support using the existing proxy environment variable names
- clear exceptions on non-200 or malformed payload
- no auth headers and no key handling

- [x] **Step 3.4: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py -q
```

Expected: PASS.

Actual: `uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py -q`
passed with 8 tests. `uv run --extra dev ruff check
src/crypto_alpha_agent/data/binance_usdm_derivatives.py
tests/test_binance_usdm_derivatives_ingestion.py` also passed.

## Task 4: Add Ingestion Functions And CLI

**Files:**

- Modify: `src/crypto_alpha_agent/data/ingestion.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `tests/test_binance_usdm_derivatives_ingestion.py`
- Modify: `tests/test_documentation_contract.py` if CLI docs contract requires it.

- [x] **Step 4.1: Write ingestion tests**

Test that each feed writes records to SQLite and writes source-health success:

- `ingest_binance_usdm_premium_index_klines`
- `ingest_binance_usdm_basis`
- `ingest_binance_usdm_global_long_short_account_ratio`
- `ingest_binance_usdm_taker_buy_sell_volume`

Also test fail-closed behavior without `allow_network`.

- [x] **Step 4.2: Verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py -q
```

Expected: FAIL because ingestion functions do not exist.

Actual: failed with missing ingestion function assertions and parser rejection
for unknown `--source binance-usdm`.

- [x] **Step 4.3: Implement ingestion functions**

Use `ResearchDataStore.upsert_records()`, write one source-health row per
ingestion attempt, and return a strict summary with:

- source
- db_path
- feed
- symbols or pairs
- records_fetched
- records_written
- network_allowed
- uses_real_capital false
- live_order_routing false

- [x] **Step 4.4: Add CLI flags**

Extend `ingest` with:

```text
--source binance-usdm
--binance-usdm-feed premium-index-klines|basis|global-long-short-account-ratio|taker-buy-sell-volume
--symbol BTCUSDT
--pair BTCUSDT
--contract-type PERPETUAL
--period 1h
--interval 1h
--limit 200
--start-time-ms <int>
--end-time-ms <int>
```

Validation rules:

- `--allow-network` required.
- `premium-index-klines` requires `--symbol` and `--interval`.
- `basis` requires `--pair`, `--contract-type`, and `--period`.
- long/short and taker feeds require `--symbol` and `--period`.
- `--timeframe` remains CCXT-specific and should not conflict.

- [x] **Step 4.5: Verify focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py tests/test_cli_ingest.py tests/test_documentation_contract.py -q
```

Expected: PASS.

Actual: `uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py
tests/test_cli_ingest.py tests/test_documentation_contract.py -q` passed with
37 tests. Related ruff check also passed.

## Task 5: Run Live Public-Data Smoke Ingestion

**Files:**

- Runtime only under `var/`; do not stage runtime artifacts.

- [x] **Step 5.1: Ingest premium index klines**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; uv run --extra dev crypto-alpha-agent ingest --source binance-usdm --binance-usdm-feed premium-index-klines --symbol BTCUSDT --interval 1h --limit 24 --db var/research.sqlite --current-capital-usd 300 --allow-network'
```

Expected: exit 0, writes `premium_index_kline` rows.

Actual: the original CLI command reached the LLM readiness gate and produced no
output for more than 90 seconds, so the hung process was terminated. Direct
ingestion through `ingest_binance_usdm_premium_index_klines()` succeeded with
24 fetched and 24 written rows.

- [x] **Step 5.2: Ingest basis**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; uv run --extra dev crypto-alpha-agent ingest --source binance-usdm --binance-usdm-feed basis --pair BTCUSDT --contract-type PERPETUAL --period 1h --limit 24 --db var/research.sqlite --current-capital-usd 300 --allow-network'
```

Expected: exit 0, writes `basis` rows.

Actual: direct ingestion through `ingest_binance_usdm_basis()` succeeded with
24 fetched and 24 written rows.

- [x] **Step 5.3: Ingest long/short account ratio**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; uv run --extra dev crypto-alpha-agent ingest --source binance-usdm --binance-usdm-feed global-long-short-account-ratio --symbol BTCUSDT --period 1h --limit 24 --db var/research.sqlite --current-capital-usd 300 --allow-network'
```

Expected: exit 0, writes `long_short_account_ratio` rows.

Actual: direct ingestion through
`ingest_binance_usdm_global_long_short_account_ratio()` succeeded with 24
fetched and 24 written rows.

- [x] **Step 5.4: Ingest taker buy/sell volume**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; uv run --extra dev crypto-alpha-agent ingest --source binance-usdm --binance-usdm-feed taker-buy-sell-volume --symbol BTCUSDT --period 1h --limit 24 --db var/research.sqlite --current-capital-usd 300 --allow-network'
```

Expected: exit 0, writes `taker_buy_sell_volume` rows.

Actual: direct ingestion through `ingest_binance_usdm_taker_buy_sell_volume()`
succeeded with 24 fetched and 24 written rows.

- [x] **Step 5.5: Inspect SQLite**

Run:

```bash
sqlite3 -header -column var/research.sqlite "SELECT record_type, COUNT(*) AS n, MIN(observed_at), MAX(observed_at) FROM source_records WHERE source='binance_usdm' GROUP BY record_type ORDER BY record_type;"
```

Expected: new record types appear with positive counts.

Actual: SQLite contains 24 rows each for `premium_index_kline`, `basis`,
`long_short_account_ratio`, and `taker_buy_sell_volume`; latest source-health
rows for all four feeds are successful. The CLI + real LLM readiness path still
needs a bounded-timeout investigation before it can be used as the live smoke
driver.

## Task 6: Add Report-Local Feasibility Command

**Files:**

- Create: `src/crypto_alpha_agent/pipeline/strategy_feasibility.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Create: `tests/test_strategy_feasibility.py`
- Modify docs if CLI contract requires it.

- [x] **Step 6.1: Write feasibility tests**

Seed market candles for BTC/USDT, ETH/USDT, and SOL/USDT plus optional
derivatives records. Test that the report:

- loads multiple symbols;
- rejects insufficient aligned history;
- rejects duplicate timestamps;
- produces at least 3 walk-forward split metrics when enough records exist;
- never writes validation or paper ledgers;
- returns `uses_real_capital=false` and `live_order_routing=false`.

- [x] **Step 6.2: Verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py -q
```

Expected: FAIL because the command/module does not exist.

Actual: failed with missing `crypto_alpha_agent.pipeline.strategy_feasibility`
and unknown `strategy-feasibility` CLI command.

- [x] **Step 6.3: Implement feasibility report**

Implement `build_large_liquid_momentum_feasibility_report()` with:

- 1-week and 2-week return features from OHLCV;
- recent-high distance feature;
- volume/liquidity guard from quote volume or candle volume proxy;
- optional filters from basis, premium index, long/short ratio, and taker
  buy/sell records when aligned;
- pessimistic cost assumptions;
- walk-forward split metrics;
- explicit blocked reasons.

- [x] **Step 6.4: Add CLI**

Add:

```text
crypto-alpha-agent strategy-feasibility \
  --db var/research.sqlite \
  --mode large-liquid-momentum-regime \
  --symbol BTC/USDT \
  --symbol ETH/USDT \
  --symbol SOL/USDT \
  --timeframe 1h \
  --out var/reports/strategy-feasibility/latest.md \
  --json-out var/reports/strategy-feasibility/latest.json \
  --current-capital-usd 300
```

- [x] **Step 6.5: Verify focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py tests/test_documentation_contract.py -q
```

Expected: PASS.

Actual: `uv run --extra dev pytest tests/test_strategy_feasibility.py
tests/test_documentation_contract.py -q` passed with 15 tests. Related ruff
check passed.

## Task 7: Decide Strategy Registration

**Files:**

- If feasibility fails: only docs/state/report.
- If feasibility passes: create strategy validator and paper runner files.

- [x] **Step 7.1: Run feasibility on local data**

Run:

```bash
uv run --extra dev crypto-alpha-agent strategy-feasibility --db var/research.sqlite --mode large-liquid-momentum-regime --symbol BTC/USDT --symbol ETH/USDT --symbol SOL/USDT --timeframe 1h --out var/reports/strategy-feasibility/latest.md --json-out var/reports/strategy-feasibility/latest.json --current-capital-usd 300
```

Expected: either PASS with positive feasibility or BLOCKED with exact reasons.

Actual: command exited 0 and wrote
`var/reports/strategy-feasibility/latest.md` plus
`var/reports/strategy-feasibility/latest.json`. Readiness is `blocked` with
reason `insufficient_aligned_history`: BTC/USDT has 434 local 1h candles,
ETH/USDT has 0, SOL/USDT has 0, and aligned records are 0.

- [x] **Step 7.2: If blocked, stop implementation**

Update:

- `docs/goals/project-completion-state.md`
- `docs/roadmap.md`
- new phase report under `docs/goals/phase-reports/`

Expected: blocker is documented; no weak strategy family is registered.

Actual: updated `docs/goals/project-completion-state.md`, `docs/roadmap.md`,
and `docs/goals/phase-reports/2026-06-08-profit-evidence-redesign-report.md`.
No strategy validator, paper runner, or registry entry was added.

- [x] **Step 7.3: If passed, write a new strategy plan**

Create a second plan for `large_liquid_momentum_regime` before code changes.

Expected: no strategy code is added without feasibility evidence.

Actual: not applicable because feasibility blocked. This step is closed by
explicitly not writing a strategy-registration plan.

## Task 8: Final Verification And Publish

**Files:**

- Modified tracked code/tests/docs only.

- [x] **Step 8.1: Run focused tests**

Run all focused tests touched by tasks.

Actual: `uv run --extra dev pytest tests/test_source_probe.py
tests/test_binance_usdm_derivatives_ingestion.py tests/test_cli_ingest.py
tests/test_strategy_feasibility.py tests/test_documentation_contract.py -q`
passed with 54 tests. Focused ruff check passed.

- [x] **Step 8.2: Run full project verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git status --short
```

Expected: tests pass, ruff passes, diff check passes, status shows only
intended tracked changes plus untracked ignored runtime artifacts under `var/`
if any.

Actual: full pytest passed with 1119 tests; `uv run --extra dev ruff check .`
passed; `git diff --check` passed. The first quiet pytest run was terminated
after no output while waiting on external real LLM tests; verbose rerun
identified provider-latency tests and completed successfully.

- [x] **Step 8.3: Run staged secret checks**

Run:

```bash
git diff --cached --check
git diff --cached --name-only
git diff --cached --no-ext-diff --unified=0
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

Expected: staged files contain no `.env`, secrets, local databases, `var/`
reports, caches, API keys, proxy values, wallet material, or provider headers.

Actual: `git diff --cached --check` passed; staged files were reviewed with
`git diff --cached --name-only`, `git diff --cached --stat`, and
`git diff --cached --no-ext-diff --unified=0`; staged secret scan returned
`[]`.

- [x] **Step 8.4: Commit and push**

Commit only the intended tracked files and push to `origin/main` or a feature
branch if the code change grows beyond the first safe slice.

Expected: remote contains the completed slice.

Actual: closeout commit pushed to `origin/main`.

## Stop Conditions

Stop and document a blocker if any of these occur:

- Public source cannot be reached or parsed through the documented route.
- Source only provides too little history for the intended validation.
- Feasibility report cannot produce positive cost-adjusted expectancy.
- Walk-forward behavior is unstable.
- Implementation would require live execution, wallets, order routing, private
  RPC, premium RPC, MEV, speed, or large capital.
- Secret-safety checks fail.

## Notes On Subagents

The repository Goal protocol asks for subagent use, but the available
multi-agent tool in this session only permits spawning when the user explicitly
asks for subagents, delegation, or parallel agent work. The owner asked for
deep search and goal execution, not explicit subagents, so this plan records
local review checkpoints instead of spawning a subagent.
