# Phase 8 Data Depth And Quality Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source qualification, proxy-aware source health, typed open-interest history, symbol normalization, and Phase 8 documentation so the evidence factory can safely deepen public data before validator expansion.

**Architecture:** Keep Phase 8 as data infrastructure, not strategy implementation. Persist only new slow data with a typed model and quality checks; record broader providers as source-probe qualification evidence until they are reachable, parseable, and have nonzero typed records. Reuse the existing SQLite `source_records` table, argparse CLI, data-quality reports, and no-live safety flags.

**Tech Stack:** Python 3.12, Pydantic v2, SQLite via existing `ResearchDataStore`, `requests`, CCXT, pytest, ruff, Smart Search evidence.

---

## External Evidence

Smart Search evidence for this phase is stored under:

`$SMART_SEARCH_EVIDENCE_DIR/`

`SMART_SEARCH_EVIDENCE_DIR` is the local temp evidence workspace used during
this round; the exact machine-specific temp path is intentionally not recorded
in docs.

Key commands already run:

```bash
smart-search doctor --format json --output $SMART_SEARCH_EVIDENCE_DIR/00-doctor.json
smart-search deep "Phase 8 Data Depth And Quality Expansion for low-capital crypto research agent: source-probe CLI, proxy-aware source health, Binance futures metrics archive, open interest history, premium index klines, Bybit OKX public OI funding, DexScreener, DefiLlama, Dune TheGraph query catalogs, data quality thresholds, no live trading no secrets" --budget deep --format json --output $SMART_SEARCH_EVIDENCE_DIR/01-deep-plan.json
smart-search search "official Binance futures data open interest history premium index klines basis global long short account ratio public data archive" --validation strict --extra-sources 5 --format json --output $SMART_SEARCH_EVIDENCE_DIR/02-search-binance-futures.json
smart-search search "official Bybit V5 API open interest history funding rate crypto public endpoint" --validation strict --extra-sources 4 --format json --output $SMART_SEARCH_EVIDENCE_DIR/03-search-bybit.json
smart-search search "official OKX API open interest funding rate instruments public data endpoint" --validation strict --extra-sources 4 --format json --output $SMART_SEARCH_EVIDENCE_DIR/04-search-okx.json
smart-search search "official DexScreener API docs pairs tokens rate limit" --validation strict --extra-sources 3 --format json --output $SMART_SEARCH_EVIDENCE_DIR/05-search-dexscreener.json
smart-search search "official DefiLlama API docs fees revenue TVL stablecoins yields endpoints" --validation strict --extra-sources 4 --format json --output $SMART_SEARCH_EVIDENCE_DIR/06-search-defillama.json
smart-search search "official Dune API docs query execution results endpoint schema" --validation strict --extra-sources 4 --format json --output $SMART_SEARCH_EVIDENCE_DIR/07-search-dune.json
smart-search search "official The Graph docs GraphQL querying subgraph schema API docs" --validation strict --extra-sources 4 --format json --output $SMART_SEARCH_EVIDENCE_DIR/08-search-thegraph.json
smart-search context7-library "ccxt" "open interest history funding rate OHLCV fetchOpenInterestHistory fetchFundingRateHistory" --format json --output $SMART_SEARCH_EVIDENCE_DIR/09-context7-ccxt-library.json
smart-search fetch "https://github.com/binance/binance-public-data" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/10-binance-public-data.md
smart-search fetch "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/11-binance-open-interest-statistics.md
smart-search fetch "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Premium-Index-Kline-Data" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/12-binance-premium-index-klines.md
smart-search fetch "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Basis" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/13-binance-basis.md
smart-search fetch "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/14-binance-long-short-ratio.md
smart-search fetch "https://bybit-exchange.github.io/docs/v5/market/open-interest" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/15-bybit-open-interest.md
smart-search fetch "https://bybit-exchange.github.io/docs/v5/market/history-fund-rate" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/16-bybit-funding-history.md
smart-search fetch "https://www.okx.com/docs-v5/en/" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/17-okx-docs.md
smart-search fetch "https://docs.dexscreener.com/api/reference" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/18-dexscreener-reference.md
smart-search fetch "https://api-docs.defillama.com/" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/19-defillama-api.md
smart-search fetch "https://docs.dune.com/api-reference/executions/endpoint/get-execution-result" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/20-dune-execution-result.md
smart-search fetch "https://thegraph.com/docs/en/subgraphs/querying/graphql-api/" --format markdown --output $SMART_SEARCH_EVIDENCE_DIR/21-thegraph-graphql-api.md
smart-search context7-docs "/ccxt/ccxt" "fetchOpenInterestHistory fetchFundingRateHistory fetchOHLCV public market data" --format json --output $SMART_SEARCH_EVIDENCE_DIR/25-context7-ccxt-market-data.json
```

Findings used in this plan:

- Binance USD-M open-interest history is public at `GET /futures/data/openInterestHist`, limited to the latest month, with periods from `5m` through `1d`, default limit 30 and max 500.
- Binance premium-index klines, basis, and long/short ratio APIs are public market-data endpoints but should remain source-probe candidates until typed models and quality checks are added.
- Bybit V5 exposes public open-interest history at `/v5/market/open-interest` and funding-rate history at `/v5/market/funding/history`.
- OKX V5 public docs expose instruments, open interest, funding-rate, funding-rate-history, and trading-statistics surfaces.
- DexScreener documents pair/token endpoints and rate limits of 300 requests/minute for pair endpoints and 60 requests/minute for token profile/boost/meta endpoints.
- DefiLlama documents free TVL, protocol, historical chain TVL, and yields endpoints, while several broader fees/revenue/advanced metrics are API-plan or pro surfaces.
- Dune API query execution/results require an API key and return result metadata including columns, row counts, rows, pagination, and execution state.
- The Graph queries are read-only GraphQL queries against subgraph schemas; schema validation and `_meta` metadata should be part of query qualification.
- Context7 CCXT docs confirm `fetchOpenInterestHistory(symbol, timeframe, since, limit, params)` and `fetchOHLCV` with mark/index/premiumIndex parameters where exchange support exists.

## Local Feasibility

Current repo state before Phase 8 implementation:

- `git status --short --branch --untracked-files=all` is clean on `main...origin/main`.
- Existing data persistence is generic and can store new record types through `SourceRecord` and `ResearchDataStore`.
- Existing typed records cover market candles, funding rates, DEX pairs, DeFi yield snapshots, research snapshots, and source health.
- Existing source health records can be extended without a schema migration because payloads are JSON.
- Existing data-quality reports already handle duplicates, stale OHLCV, missing OHLCV bars, source failures, non-positive prices, and zero volume.
- Existing `CcxtResearchCollector` has OHLCV and funding history but no open-interest history.
- Existing CLI has `ingest`, `evidence-run`, reports, and Phase 5 `expansion-prep-report`; no `source-probe` command exists.
- Existing proxy route helper in `pipeline/evidence_run_ops.py` recognizes `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, lowercase variants, and `CRYPTO_ALPHA_AGENT_PROXY`; `NO_PROXY` exists in docs but is not a proxy indicator by itself.
- Documentation contract tests parse representative CLI examples and reject local paths, secrets, and live-routing flags.
- `docs/goals/project-completion-state.md` still has stale Phase 5 pre-commit wording and must be repaired in the Phase 8 state update.

Subagent audit findings:

- Docs must add a source coverage matrix, query catalog, source-probe runbook workflow, Phase 8 completion report, and state/roadmap updates.
- Contract tests are sensitive to CLI examples; any `source-probe` docs example must parse.
- Preserve exact safety terms: `no wallet keys`, `no live order routing`, `no live execution`, `no wallet-key access`, `no order routing`, `no live capital`, and `live_execution_enabled=false`.

## File Map

- Create `src/crypto_alpha_agent/data/symbols.py`: multi-source symbol normalization helpers for CEX spot/perp/futures and DEX chain/token IDs.
- Create `src/crypto_alpha_agent/data/source_probe.py`: source target catalog, route detection, probe classification, JSON parse/count logic, and source-health evidence persistence.
- Modify `src/crypto_alpha_agent/data/models.py`: add `open_interest` record type and `OpenInterestRecord`.
- Modify `src/crypto_alpha_agent/data/quality.py`: add open-interest quality checks and richer source-health snapshot fields.
- Modify `src/crypto_alpha_agent/data/ccxt_collector.py`: add `fetch_open_interest_history`.
- Modify `src/crypto_alpha_agent/data/ingestion.py`: add `ingest_ccxt_open_interest_history`, route-aware source-health payload fields, and open-interest record conversion.
- Modify `src/crypto_alpha_agent/cli.py`: add `source-probe` command and `--ccxt-feed open-interest-history`.
- Modify `src/crypto_alpha_agent/pipeline/markdown.py` only if Phase 8 report rendering needs a small existing renderer update.
- Create `tests/test_symbol_normalization.py`.
- Create `tests/test_source_probe.py`.
- Modify `tests/test_ccxt_collector.py`.
- Modify `tests/test_ccxt_ingestion_service.py`.
- Modify `tests/test_data_quality_reports.py`.
- Modify `tests/test_documentation_contract.py`.
- Create `docs/source-coverage-matrix.md`.
- Create `docs/source-query-catalog.md`.
- Modify `README.md`, `docs/runbook.md`, `docs/project-asset-assessment.md`, `docs/roadmap.md`, and `docs/goals/project-completion-state.md`.
- Create `docs/goals/phase-reports/2026-05-24-phase-8-data-depth-quality-expansion-completion-report.md`.

## Task 1: Symbol Normalization

**Files:**

- Create: `src/crypto_alpha_agent/data/symbols.py`
- Test: `tests/test_symbol_normalization.py`

- [ ] **Step 1: Write failing tests**

Add tests that require:

```python
from crypto_alpha_agent.data.symbols import (
    normalize_dex_identifier,
    normalize_exchange_symbol,
)


def test_normalizes_spot_and_perpetual_exchange_symbols():
    assert normalize_exchange_symbol("BTCUSDT").canonical == "BTC/USDT"
    assert normalize_exchange_symbol("BTC/USDT:USDT").canonical == "BTC/USDT:USDT"
    assert normalize_exchange_symbol("BTC-USDT-SWAP", venue="okx").canonical == "BTC/USDT:USDT"
    assert normalize_exchange_symbol("BTCUSD", instrument_type="perpetual").canonical == "BTC/USD:USD"


def test_dex_identifier_keeps_chain_and_address_scope():
    token = normalize_dex_identifier("ethereum", "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")

    assert token.canonical == "ethereum:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert token.instrument_type == "dex_token"
```

- [ ] **Step 2: Run RED test**

Run:

```bash
uv run --extra dev pytest tests/test_symbol_normalization.py -q
```

Expected: FAIL because `crypto_alpha_agent.data.symbols` does not exist.

- [ ] **Step 3: Implement minimal symbol helpers**

Create a strict Pydantic `NormalizedSymbol` model with `canonical`, `base_asset`, `quote_asset`, `settlement_asset`, `instrument_type`, `venue`, and `raw_symbol`. Implement conservative parsing for slash, colon settlement, OKX `BASE-QUOTE-SWAP`, compact symbols ending in known quotes, and DEX chain/address identifiers.

- [ ] **Step 4: Run GREEN test**

Run:

```bash
uv run --extra dev pytest tests/test_symbol_normalization.py -q
```

Expected: PASS.

## Task 2: Typed Open Interest Records And Quality Checks

**Files:**

- Modify: `src/crypto_alpha_agent/data/models.py`
- Modify: `src/crypto_alpha_agent/data/quality.py`
- Test: `tests/test_data_models_store.py`
- Test: `tests/test_data_quality_reports.py`

- [ ] **Step 1: Write failing model/store tests**

Add a test that constructs an `OpenInterestRecord`, converts it to a `SourceRecord`, persists it, and reloads it with `record_type="open_interest"`.

- [ ] **Step 2: Write failing quality tests**

Add tests that require:

- non-positive open interest produces `non_positive_open_interest`;
- duplicate semantic open-interest rows produce `duplicate_semantic_record`;
- a 1h open-interest series with a missing interval produces `missing_open_interest_bars`;
- a latest 1h open-interest row older than two intervals produces `stale_source`;
- a payload timestamp skewed from `observed_at` by more than one expected interval produces `timestamp_skew`.

- [ ] **Step 3: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_data_models_store.py tests/test_data_quality_reports.py -q
```

Expected: FAIL on missing `OpenInterestRecord` or missing reason codes.

- [ ] **Step 4: Implement records and quality logic**

Add `open_interest` to `RecordType`, add `OpenInterestRecord`, and extend data-quality helpers with open-interest semantic keys, series keys, value checks, missing-bar checks, stale checks, and timestamp-skew checks. Keep existing OHLCV behavior unchanged.

- [ ] **Step 5: Run GREEN tests**

Run:

```bash
uv run --extra dev pytest tests/test_data_models_store.py tests/test_data_quality_reports.py -q
```

Expected: PASS.

## Task 3: CCXT Open Interest Ingestion

**Files:**

- Modify: `src/crypto_alpha_agent/data/ccxt_collector.py`
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_ccxt_collector.py`
- Test: `tests/test_ccxt_ingestion_service.py`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write failing collector tests**

Add fake exchange tests for `fetch_open_interest_history("BTC/USDT:USDT", "1h", limit=1)` returning an `OpenInterestRecord`, passing exchange-specific params, and raising `NotImplementedError` when unsupported.

- [ ] **Step 2: Write failing ingestion/CLI tests**

Add tests that:

- `ingest_ccxt_open_interest_history(... allow_network=True ...)` writes `open_interest` records and source health with `feed="open_interest_history"`;
- the CLI accepts `--ccxt-feed open-interest-history --timeframe 1h`;
- the CLI rejects `open-interest-history` without `--timeframe`.

- [ ] **Step 3: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_ccxt_collector.py tests/test_ccxt_ingestion_service.py tests/test_documentation_contract.py -q
```

Expected: FAIL on missing collector method, missing ingestion function, and missing CLI choice.

- [ ] **Step 4: Implement collector/ingestion/CLI**

Add `fetch_open_interest_history`, `ingest_ccxt_open_interest_history`, `_open_interest_to_source_record`, and CLI routing. Preserve `uses_real_capital=False` and `live_order_routing=False`.

- [ ] **Step 5: Run GREEN tests**

Run:

```bash
uv run --extra dev pytest tests/test_ccxt_collector.py tests/test_ccxt_ingestion_service.py tests/test_documentation_contract.py -q
```

Expected: PASS.

## Task 4: Source Probe Workflow

**Files:**

- Create: `src/crypto_alpha_agent/data/source_probe.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/data/quality.py`
- Test: `tests/test_source_probe.py`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write failing probe tests**

Add tests for:

- listed targets include Binance OI history, Binance premium index klines, Binance basis, Bybit OI, OKX open interest, DexScreener pairs, DefiLlama yields/fundamentals, Dune query result, and TheGraph GraphQL;
- no `--allow-network` records a blocked source-health row with `network_route="blocked"`, provider status `Candidate`, and blocked reason `network_not_allowed`;
- successful fake direct HTTP response with JSON rows records `Reachable`, `Parseable`, `ResearchUsable`, HTTP status, parse status, typed count, tested URL family, schema version, and no live authority;
- successful fake proxy route records `ReachableViaProxy` without printing proxy values;
- credential-required Dune probe fails closed with `credential_required` unless a redacted local key marker is supplied;
- zero typed records stays parseable but does not become `ResearchUsable`;
- parse failure records `parse_failed` and a blocked reason.

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_source_probe.py -q
```

Expected: FAIL because `data.source_probe` and `source-probe` CLI do not exist.

- [ ] **Step 3: Implement source-probe models and classification**

Create strict models for `SourceProbeTarget`, `SourceProbeResult`, and `SourceProbeSummary`. Implement `probe_target`, `available_probe_targets`, route detection, parse/count helpers for target response families, `provider_status` classification, and source-health persistence through the existing store.

- [ ] **Step 4: Add CLI**

Add:

```bash
crypto-alpha-agent source-probe --list-targets
crypto-alpha-agent source-probe --db var/research.sqlite --target binance_usdm_open_interest_history --allow-network --route direct
crypto-alpha-agent source-probe --db var/research.sqlite --target binance_usdm_open_interest_history --allow-network --route proxy
```

The payload must include `uses_real_capital=false`, `live_order_routing=false`, target metadata, route, provider status, parse status, and `exit_code=2` for blocked/unusable probes.

- [ ] **Step 5: Run GREEN tests**

Run:

```bash
uv run --extra dev pytest tests/test_source_probe.py tests/test_documentation_contract.py -q
```

Expected: PASS.

## Task 5: Documentation Matrix And Query Catalog

**Files:**

- Create: `docs/source-coverage-matrix.md`
- Create: `docs/source-query-catalog.md`
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `docs/project-asset-assessment.md`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write failing documentation contract tests**

Update documentation contract tests to require `source-probe`, `source coverage matrix`, `query catalog`, `ReachableViaProxy`, `ProductionResearchSource`, and a representative `source-probe` CLI example that parses.

- [ ] **Step 2: Run RED docs tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: FAIL until docs and parser are updated.

- [ ] **Step 3: Write source coverage matrix**

Document provider, fields, endpoint family, rate-limit assumption, credential requirement, route/proxy notes, core/optional classification, current local status, and whether typed persistence exists.

- [ ] **Step 4: Write query catalog**

Document named Dune and TheGraph research questions, expected output columns/schema, credential requirement, blocked reason when credentials are absent, and safety notes.

- [ ] **Step 5: Update runbook/README/asset assessment**

Add source-probe operator workflow, proxy route behavior, local env variable names only, no secret values, source-health inspection, and the typed open-interest ingestion example.

- [ ] **Step 6: Run GREEN docs tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: PASS.

## Task 6: Phase State, Report, Reviews, And Verification

**Files:**

- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-24-phase-8-data-depth-quality-expansion-completion-report.md`

- [ ] **Step 1: Update roadmap and state**

Mark Phase 8 complete, record Phase 9 as next, repair stale Phase 5 commit wording, include Smart Search evidence path, verification commands, review pass outcomes, commit SHA placeholder only until after commit, and keep hard boundaries.

- [ ] **Step 2: Write Phase 8 completion report**

Include scope, external evidence, implementation summary, rejected/blocked candidates, tests, review outcomes, no-live/no-secrets safety, and next phase.

- [ ] **Step 3: Run focused verification**

Run:

```bash
uv run --extra dev pytest tests/test_source_probe.py tests/test_symbol_normalization.py tests/test_ccxt_collector.py tests/test_ccxt_ingestion_service.py tests/test_data_quality_reports.py tests/test_data_models_store.py tests/test_documentation_contract.py -q
```

Expected: PASS.

- [ ] **Step 4: Run review pass 1 and fix Critical/Important**

Use a subagent spec/safety review focused on Phase 8 requirements and charter boundaries. Fix all Critical/Important findings and rerun focused tests.

- [ ] **Step 5: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests
```

Expected: PASS.

- [ ] **Step 6: Run review pass 2 and re-review**

Use a second subagent code-quality/safety review. Fix all Critical/Important findings and rerun affected tests plus full verification if needed.

- [ ] **Step 7: Final staged safety checks, commit, and push**

Run:

```bash
git status --short --branch --untracked-files=all
git add README.md docs src tests
git diff --cached --check
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
git commit -m "feat: add source qualification workflow"
git push
```

Expected: commit and push succeed; state file is updated after the final commit SHA if needed.

## Self-Review

- Phase 8 deliverables map to tasks: source coverage matrix and query catalog in Task 5; source-probe workflow, routes, provider transitions, and qualification evidence in Task 4; local proxy support via route detection in Task 4; typed SQLite open-interest persistence and quality checks in Tasks 2 and 3; source-health thresholds in Task 2 and Task 4; symbol normalization in Task 1.
- Production promotion remains fail-closed: `ProductionResearchSource` is documented as requiring multi-day canary evidence and is not assigned by a one-shot probe.
- No task adds wallet access, live order routing, real capital, MEV, private RPC, or speed-edge behavior.
- Dune and credentialed data remain optional and redacted.
