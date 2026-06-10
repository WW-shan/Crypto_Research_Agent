# Derivatives PIT Coverage And Basis/Funding Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add canonical point-in-time execution-history handling, first-party Binance USD-M funding/open-interest ingestion, endpoint metadata, and read-only derivatives feasibility observations.

**Architecture:** Extend the existing Round 24 evidence lab rather than creating a new execution path. Canonicalize market candles before universe quality checks, add focused Binance USD-M record models/client methods/CLI choices, extend source coverage metadata, and add derivatives observation builders inside `multi_hypothesis_feasibility` while preserving cost-aware v2 gates.

**Tech Stack:** Python 3.12, Pydantic v2 strict models, argparse CLI, SQLite through `ResearchDataStore`, pytest, ruff, Markdown/JSON artifacts, existing candidate-state JSONL memory.

---

## File Structure

- Modify: `src/crypto_alpha_agent/data/models.py`
  - Add `FundingRateRecord.to_source_record()` and ensure first-party funding records share the existing `funding_rate` type.
- Modify: `src/crypto_alpha_agent/data/binance_usdm_derivatives.py`
  - Add `fetch_funding_rate_history()` and `fetch_open_interest_history()`.
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
  - Add `ingest_binance_usdm_funding_rate_history()` and `ingest_binance_usdm_open_interest_history()`.
- Modify: `src/crypto_alpha_agent/data/source_probe.py`
  - Ensure source-health feed names match the new ingestion feeds.
- Modify: `src/crypto_alpha_agent/pipeline/evidence_universe.py`
  - Add canonical market candle selection, endpoint metadata, funding/open-interest coverage, and refined duplicate handling.
- Modify: `src/crypto_alpha_agent/pipeline/candidate_screens.py`
  - Include first-party Binance USD-M `funding_rate` and `open_interest` where relevant without changing strategy registry state.
- Modify: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
  - Add derivatives temporal observation builders for basis/funding and crowding candidates.
- Modify: `src/crypto_alpha_agent/cli.py`
  - Add Binance USD-M feed choices for funding and open-interest history.
- Modify: `tests/test_binance_usdm_derivatives_ingestion.py`
- Modify: `tests/test_evidence_universe.py`
- Modify: `tests/test_candidate_screens.py`
- Modify: `tests/test_multi_hypothesis_feasibility.py`
- Modify: `tests/test_cli_ingest.py`
- Create at closeout: `docs/goals/phase-reports/2026-06-10-derivatives-pit-coverage-and-basis-funding-redesign-report.md`
- Modify at closeout: `docs/goals/project-completion-state.md`
- Modify at closeout: `docs/roadmap.md`
- Modify at closeout: `docs/runbook.md`

## Task 1: Canonical Market Candle Coverage

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/evidence_universe.py`
- Modify: `tests/test_evidence_universe.py`

- [ ] **Step 1: Write RED test for redundant source overlap**

Add this test to `tests/test_evidence_universe.py`:

```python
def test_evidence_universe_does_not_flag_redundant_qualified_market_sources_as_duplicates(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, close=100, source="binance_public", record_id_suffix="public-0"),
            _market_candle("BTC/USDT", START, close=101, source="ccxt", record_id_suffix="ccxt-0"),
            _market_candle("BTC/USDT", START + timedelta(hours=1), close=102, source="binance_public", record_id_suffix="public-1"),
            _market_candle("BTC/USDT", START + timedelta(hours=1), close=103, source="ccxt", record_id_suffix="ccxt-1"),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health("ccxt", "ohlcv", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import build_evidence_universe_report

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=START + timedelta(hours=2),
        min_history_records=2,
    )

    reason_codes = {issue.reason_code for issue in report.quality_issues}
    assert report.assets[0].market_records == 2
    assert "duplicate_timestamps" not in reason_codes
```

Run:

```bash
uv run --extra dev pytest tests/test_evidence_universe.py::test_evidence_universe_does_not_flag_redundant_qualified_market_sources_as_duplicates -q
```

Expected: FAIL because current universe logic counts both sources at the same timestamp.

- [ ] **Step 2: Implement canonical selection**

In `src/crypto_alpha_agent/pipeline/evidence_universe.py`, add a helper that keeps one market candle per `(symbol, timeframe, observed_at)` key with priority `binance_public`, then `ccxt`, then lexical source order. Use it before `_asset_report`, `_duplicate_market_timestamp_issues`, and `_timestamp_alignment_issues`.

- [ ] **Step 3: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_universe.py::test_evidence_universe_does_not_flag_redundant_qualified_market_sources_as_duplicates -q
uv run --extra dev pytest tests/test_evidence_universe.py -q
```

Expected: PASS.

## Task 2: Binance USD-M Funding And Open-Interest Ingestion

**Files:**
- Modify: `src/crypto_alpha_agent/data/models.py`
- Modify: `src/crypto_alpha_agent/data/binance_usdm_derivatives.py`
- Modify: `src/crypto_alpha_agent/data/ingestion.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `tests/test_binance_usdm_derivatives_ingestion.py`
- Modify: `tests/test_cli_ingest.py`

- [ ] **Step 1: Write RED tests for client/model ingestion**

Add tests that use fake sessions/clients and assert:

```python
summary = ingest_binance_usdm_funding_rate_history(
    db_path,
    symbol="BTCUSDT",
    limit=2,
    allow_network=True,
    client=fake_client,
)
assert summary.feed == "funding_rate_history"
assert summary.records_written == 2
```

and:

```python
summary = ingest_binance_usdm_open_interest_history(
    db_path,
    symbol="BTCUSDT",
    period="1h",
    limit=2,
    allow_network=True,
    client=fake_client,
)
assert summary.feed == "open_interest_history"
assert summary.records_written == 2
```

Run:

```bash
uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py -q
```

Expected: FAIL because the new ingestion functions and client methods do not exist.

- [ ] **Step 2: Implement model/source-record support**

Add `FundingRateRecord.to_source_record()` in `src/crypto_alpha_agent/data/models.py` using record id shape:

```python
f"{self.source}:{safe_venue}:{safe_symbol}:funding_rate:{timestamp}"
```

Keep `record_type="funding_rate"`.

- [ ] **Step 3: Implement Binance client methods**

Add to `BinanceUsdmDerivativesClient`:

```python
def fetch_funding_rate_history(...):
    payload = self._get_json("/fapi/v1/fundingRate", params=...)
    return [_funding_rate_record(row, fallback_symbol=symbol) for row in _list_payload(payload, "/fapi/v1/fundingRate")]
```

and:

```python
def fetch_open_interest_history(...):
    payload = self._get_json("/futures/data/openInterestHist", params=...)
    return [_open_interest_record(row, fallback_symbol=symbol, timeframe=period) for row in _list_payload(payload, "/futures/data/openInterestHist")]
```

Parse `fundingTime` for funding records and `timestamp` for open-interest records.

- [ ] **Step 4: Implement ingestion and CLI choices**

Add feed choices:

- `funding-rate-history`
- `open-interest-history`

Validate required args:

- funding: `--symbol`
- open interest: `--symbol --period`

Reject unrelated `--pair`, `--contract-type`, and `--interval` for both.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py tests/test_cli_ingest.py -q
```

Expected: PASS.

## Task 3: Endpoint Metadata And Source Coverage

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/evidence_universe.py`
- Modify: `tests/test_evidence_universe.py`

- [ ] **Step 1: Write RED tests for endpoint metadata and coverage**

Add tests that seed `funding_rate` and `open_interest` from `binance_usdm` plus matching source-health rows. Assert source coverage includes both record types and that long/short/taker are `latest_30_day_limited=True` while funding/open-interest are not hard-coded to that flag.

Run:

```bash
uv run --extra dev pytest tests/test_evidence_universe.py::test_evidence_universe_reports_funding_and_open_interest_source_coverage -q
```

Expected: FAIL because coverage currently ignores funding and open-interest.

- [ ] **Step 2: Add coverage role and feed mapping**

Update `_DERIVATIVES_TYPES`, `_source_role`, `_coverage_feed`, `_required_health_feeds`, and `_record_matches_universe` to include:

- `funding_rate`
- `open_interest`

Use feed names `funding_rate_history` and `open_interest_history` for Binance USD-M source-health.

- [ ] **Step 3: Add endpoint metadata fields without breaking existing JSON**

Extend `UniverseSourceCoverage` with safe default fields:

```python
endpoint_family: str | None = None
max_limit: int | None = None
start_end_pagination: bool = False
latest_30_day_limited: bool = False
```

Fill them from a small metadata map.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_universe.py -q
```

Expected: PASS.

## Task 4: Derivatives Temporal Observations

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/multi_hypothesis_feasibility.py`
- Modify: `tests/test_multi_hypothesis_feasibility.py`

- [ ] **Step 1: Write RED tests for basis/funding observations**

Add a test that seeds market candles plus aligned premium, basis, and funding records. Run feasibility for `perp_spot_basis_funding_deviation` and assert `raw_sample_count > 0`, `sample_count > 0`, and `split_coverage >= 1` under a low `min_split_count`.

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py::test_derivatives_basis_funding_candidate_builds_temporal_observations -q
```

Expected: FAIL because derivatives screens currently return no historical observations.

- [ ] **Step 2: Write RED tests for crowding observations**

Add a test that seeds market candles plus long/short and taker records. Run feasibility for `derivatives_crowding_price_action` and assert nonzero raw/sample counts.

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py::test_derivatives_crowding_candidate_builds_temporal_observations -q
```

Expected: FAIL for the same reason.

- [ ] **Step 3: Implement record loaders and alignment**

Add helpers in `multi_hypothesis_feasibility.py`:

- `_records_by_symbol_time(records, record_type, symbols, timeframe)`;
- `_latest_market_index_at_or_before(rows, timestamp)`;
- `_derivatives_basis_funding_observations(records, market_by_symbol)`;
- `_derivatives_crowding_observations(records, market_by_symbol)`.

Each observation uses the next market candle return and a finite positive
`signal_score` based on absolute deviation.

- [ ] **Step 4: Thread raw records into `_historical_observations`**

Change `_historical_observations(screen_id, market_by_symbol)` to accept the
loaded `records` list and dispatch derivatives screens to the new builders.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_multi_hypothesis_feasibility.py -q
```

Expected: PASS.

## Task 5: Candidate Screen Source Qualification

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/candidate_screens.py`
- Modify: `tests/test_candidate_screens.py`

- [ ] **Step 1: Write RED tests for first-party funding/open-interest records**

Add a test that seeds `funding_rate` from `binance_usdm` and asserts
`perp_spot_basis_funding_deviation` can count it as qualified. Add a test that
`open_interest` from `binance_usdm` is accepted for future derivatives coverage.

Run:

```bash
uv run --extra dev pytest tests/test_candidate_screens.py -q
```

Expected: FAIL if `binance_usdm` is not included for a required record type.

- [ ] **Step 2: Update qualified sources**

Set:

```python
"funding_rate": frozenset({"ccxt", "binance_usdm"})
"open_interest": frozenset({"ccxt", "binance_usdm"})
```

Keep all candidate screens read-only and avoid importing strategy registry modules.

- [ ] **Step 3: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_candidate_screens.py -q
```

Expected: PASS.

## Task 6: Bounded Round 25 Lab And Docs Closeout

**Files:**
- Create: `docs/goals/phase-reports/2026-06-10-derivatives-pit-coverage-and-basis-funding-redesign-report.md`
- Modify: `docs/goals/project-completion-state.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/runbook.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --extra dev pytest \
  tests/test_binance_usdm_derivatives_ingestion.py \
  tests/test_evidence_universe.py \
  tests/test_candidate_screens.py \
  tests/test_multi_hypothesis_feasibility.py \
  tests/test_cli_ingest.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run bounded lab**

Run a read-only lab first, then optionally collect first-party Binance USD-M
funding/open-interest data only if needed and network succeeds. The lab command
must keep `uses_real_capital=false` and `live_order_routing=false`.

```bash
uv run crypto-alpha-agent evidence-universe-lab \
  --db var/research.sqlite \
  --memory var/memory/candidate-state.jsonl \
  --universe-preset liquid-usdm-top20 \
  --max-symbols 8 \
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
  --cost-aware-execution \
  --min-edge-over-cost-multiplier 2 \
  --max-turnover 0.5 \
  --persist-candidate-state \
  --out-dir var/reports/evidence-universe-lab/round-25-derivatives-pit-main \
  --json-out var/reports/evidence-universe-lab/round-25-derivatives-pit-main/evidence-universe-lab.json
```

Expected: command exits 0 and writes artifacts. Feasible candidate count may be
0.

- [ ] **Step 3: Persist actual results**

Write the phase report from actual JSON/SQLite values. Update project state,
roadmap, and runbook with the Round 25 result and remaining blockers.

- [ ] **Step 4: Full verification**

Run:

```bash
uv run --extra dev pytest -m "not llm_integration" -q
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git diff --cached --check
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

Expected: PASS, or record exact environment failures without claiming success.

- [ ] **Step 5: Commit and push**

```bash
git status --short
git add docs src tests
git commit -m "feat: add derivatives PIT coverage redesign"
git push origin main
```

Expected: commit succeeds and `origin/main` receives the Round 25 changes.
