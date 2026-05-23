# Phase 5 Data And Strategy Expansion Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Phase 5 preparation layer that ranks next data-source and strategy-family expansion candidates, fails closed with stable reasons, and makes weekly family reports identify continue/stop/redesign/add-data actions.

**Architecture:** Keep Phase 5 as preparation for Phase 8 and Phase 9. Reuse the existing strategy registry, source-health records, data-quality reports, and weekly evidence reports; do not add live trading, wallet access, source probing, paid-data dependency, or new exchange routing. Add a small `expansion_preparation` pipeline and CLI report that catalogs candidate sources and strategy families while leaving actual data-depth ingestion and validator implementation to later phases.

**Tech Stack:** Python 3.12, Pydantic v2, SQLite-backed existing data/evidence stores, argparse CLI, Markdown rendering, pytest, ruff, Smart Search evidence.

---

## External Evidence

Smart Search evidence for this phase is stored under:

`/tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/`

Commands already run:

```bash
smart-search doctor --format json --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/00-doctor.json
smart-search deep "Immediate Phase 5 Data And Strategy Expansion preparation for a low-capital crypto alpha research agent: open interest, funding plus OI crowding, liquidation data if reliable, cross-exchange funding dispersion, DefiLlama stablecoin TVL watchlists, DEX liquidity migration watchlists, source-health and fail-closed validators, no live trading no MEV no premium RPC" --budget deep --format json --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/01-deep-plan.json
smart-search search "crypto public API open interest funding rate liquidation data DefiLlama stablecoins DexScreener API docs low cost research" --validation balanced --extra-sources 3 --format json --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/02-broad-search.json
smart-search context7-library "ccxt" "open interest funding rates" --format json --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/03-context7-ccxt-library.json
smart-search context7-docs "/ccxt/ccxt" "open interest funding rates liquidation public market data methods" --format json --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/04-context7-ccxt-docs.json
smart-search fetch "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/05-binance-open-interest.md
smart-search fetch "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/06-binance-open-interest-statistics.md
smart-search fetch "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/07-binance-funding-rate-history.md
smart-search fetch "https://api-docs.defillama.com/" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/09-defillama-api-docs.md
smart-search fetch "https://docs.dexscreener.com/api/reference" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/10-dexscreener-api-reference.md
smart-search fetch "https://api.coinalyze.net/v1/doc/" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/11-coinalyze-api-docs.md
```

Findings used in this plan:

- Binance USD-M futures has public current open-interest endpoint `GET /fapi/v1/openInterest` and open-interest history endpoint `GET /futures/data/openInterestHist`; funding-rate history is `GET /fapi/v1/fundingRate`.
- CCXT documents public methods for funding-rate history, current open interest, open-interest history, and liquidation methods where exchange support exists.
- Coinalyze documents an API-key route with current and historical open interest, funding-rate history, predicted funding-rate history, liquidation history, and long/short ratio history. It is useful only as an optional source because it requires a local API key and rate-limit handling.
- DefiLlama documents TVL/protocol/chains, stablecoins, yields, volumes, fees, revenue, and perps/open-interest overview data. Existing code only ingests yield pools, so Phase 5 must treat broader DefiLlama fundamentals as future data-depth candidates.
- DEX Screener documents pair, token-pair, token-address, liquidity, and volume endpoints with documented request-rate limits. Existing code already ingests pair snapshots, but local history and quality checks are still required before stronger watchlist evidence.
- A Smart Search fetch for Binance `All Force Orders` produced an empty file, and a follow-up Smart Search search for the force-orders docs failed with an empty provider result. For Phase 5, Binance liquidation docs remain unverified; Coinalyze liquidation-history docs are the current source-backed liquidation candidate.

## Local Feasibility

Current repo state:

- `git status --short --branch --untracked-files=all` is clean on `main...origin/main`.
- `default_strategy_registry(current_capital_usd=300.0).list_families()` returns:
  - `defi_yield_regime_watchlist`
  - `dex_liquidity_volume_watchlist`
  - `funding_extremity_price_confirmation`
  - `funding_mean_reversion_after_extreme`
- Watchlist-only adapters already exist:
  - `src/crypto_alpha_agent/strategy/defi_yield_regime.py`
  - `src/crypto_alpha_agent/strategy/dex_liquidity_watchlist.py`
  - registry wiring in `src/crypto_alpha_agent/strategy/registry.py`
- Source-health records already exist in ingestion and evidence-run paths:
  - `src/crypto_alpha_agent/data/ingestion.py`
  - `src/crypto_alpha_agent/pipeline/evidence_runner.py`
  - `src/crypto_alpha_agent/data/quality.py`
- Weekly reports already compare family evidence in `src/crypto_alpha_agent/pipeline/evidence_reports.py`, but `FamilyEvidenceSummary` does not yet expose a per-family action of `continue`, `stop`, `redesign`, or `add_data`.
- The experiment planner intentionally filters to executable funding/price families; subagent audit identified this as the wrong seam for watchlist expansion preparation.

Subagent findings:

- Codebase audit recommended a new read-only sibling module beside `evidence_reports.py`, not widening `plan_next_experiments`.
- Docs audit found stale Phase 5 wording and a source-health vocabulary mismatch: state instructions should align to the implemented `direct`, `proxy`, `blocked`, `not_applicable`, and failure-reason split.

Small validation/prototype already run:

```bash
uv run --extra dev python - <<'PY'
from crypto_alpha_agent.strategy import default_strategy_registry
from crypto_alpha_agent.pipeline.evidence_reports import build_weekly_evidence_report
from pathlib import Path
from tempfile import TemporaryDirectory

registry = default_strategy_registry(current_capital_usd=300.0)
print('families', registry.list_families())
with TemporaryDirectory() as tmp:
    report = build_weekly_evidence_report(db_path=Path(tmp)/'research.sqlite', memory_path=Path(tmp)/'memory.jsonl')
    print('weekly_fields', sorted(report.model_dump(mode='json').keys()))
PY
```

Result:

```text
families ('defi_yield_regime_watchlist', 'dex_liquidity_volume_watchlist', 'funding_extremity_price_confirmation', 'funding_mean_reversion_after_extreme')
weekly_fields ['best_improving_family', 'degraded_families', 'family_summaries', 'live_order_routing', 'llm_summary', 'llm_summary_metadata', 'llm_summary_rejected_reason_codes', 'near_paper_eligibility', 'near_tiny_live_review', 'reason_codes', 'sample_size_progress', 'should_collect_more_data', 'should_continue', 'should_stop_family', 'top_rejected_reasons', 'uses_real_capital']
```

## File Map

- Modify `src/crypto_alpha_agent/pipeline/evidence_reports.py`: add per-family recommended actions and stable action reason codes to weekly family summaries.
- Modify `src/crypto_alpha_agent/pipeline/markdown.py`: render weekly family actions and render the new expansion-preparation Markdown report.
- Create `src/crypto_alpha_agent/pipeline/expansion_preparation.py`: read-only source/strategy expansion catalog and report builder.
- Modify `src/crypto_alpha_agent/cli.py`: add `expansion-prep-report` command.
- Create `tests/test_expansion_preparation.py`: focused TDD for the Phase 5 prep report and CLI.
- Modify `tests/test_evidence_reports.py`: assert weekly family action decisions and Markdown output.
- Modify `docs/runbook.md`: document the read-only Phase 5 report command.
- Modify `docs/roadmap.md`: mark Immediate Phase 5 complete and clean up stale Phase 5/sequence wording.
- Modify `docs/goals/project-completion-state.md`: move to Round 7 / Phase 5 completion and align source-health vocabulary.
- Create `docs/goals/phase-reports/2026-05-23-phase-5-data-strategy-expansion-preparation-completion-report.md`: Phase completion report.

## Task 1: Weekly Family Action Decisions

**Files:**

- Modify: `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Test: `tests/test_evidence_reports.py`

- [ ] **Step 1: Write failing weekly action tests**

Add this test near the existing weekly report tests in `tests/test_evidence_reports.py`:

```python
def test_weekly_report_assigns_family_actions_and_reasons(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_weekly_fixture(db_path, memory_path)

    report = build_weekly_evidence_report(db_path=db_path, memory_path=memory_path)
    markdown = render_weekly_evidence_report_markdown(report)
    summaries = {summary.strategy_family: summary for summary in report.family_summaries}

    assert summaries[STRATEGY_FAMILY].recommended_action == "add_data"
    assert "sample_below_target" in summaries[STRATEGY_FAMILY].action_reason_codes
    assert summaries["dex_liquidity_watchlist"].recommended_action == "stop"
    assert "degraded_family" in summaries["dex_liquidity_watchlist"].action_reason_codes
    assert "| Strategy | Action |" in markdown
    assert "add_data" in markdown
    assert "stop" in markdown
```

- [ ] **Step 2: Run RED test**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_reports.py::test_weekly_report_assigns_family_actions_and_reasons -q
```

Expected: FAIL because `FamilyEvidenceSummary` lacks `recommended_action` and `action_reason_codes`.

- [ ] **Step 3: Implement family action fields**

In `src/crypto_alpha_agent/pipeline/evidence_reports.py`:

1. Add this type alias near the constants:

```python
FamilyRecommendedAction = Literal["continue", "stop", "redesign", "add_data"]
```

2. Add fields to `FamilyEvidenceSummary`:

```python
    recommended_action: FamilyRecommendedAction
    action_reason_codes: list[str] = Field(default_factory=list)
```

3. In `_family_summary(...)`, compute and pass the fields:

```python
    recommended_action, action_reason_codes = _family_recommended_action(
        sample_size=sample_size,
        closed_count=0 if package is None else package.closed_count,
        failed_count=0 if package is None else package.failed_count,
        blocked_count=0 if package is None else package.blocked_count,
        net_pnl_usd=0.0 if package is None else package.net_pnl_usd,
        validation_count=len(validation),
        rejected_reasons=rejected_reasons,
        memory_records=memory_records,
    )
```

4. Add this helper near `_family_is_degraded(...)`:

```python
def _family_recommended_action(
    *,
    sample_size: int,
    closed_count: int,
    failed_count: int,
    blocked_count: int,
    net_pnl_usd: float,
    validation_count: int,
    rejected_reasons: list[str],
    memory_records: list[MemoryRecord],
) -> tuple[FamilyRecommendedAction, list[str]]:
    reason_codes: list[str] = []
    if any(_has_degraded_marker(record) for record in memory_records):
        return "stop", ["degraded_family"]
    if failed_count >= 3 and failed_count >= closed_count:
        return "stop", ["too_many_failed_outcomes"]
    if blocked_count >= 3:
        return "redesign", ["too_many_blocked_outcomes"]
    if any(reason in {"insufficient_walk_forward", "non_positive_expectancy", "fee_killed_edge", "slippage_killed_edge"} for reason in rejected_reasons):
        reason_codes.append("validator_redesign_signal")
    if validation_count == 0:
        reason_codes.append("missing_validation_evidence")
    if sample_size < PAPER_SAMPLE_TARGET:
        reason_codes.append("sample_below_target")
    if reason_codes:
        action = "redesign" if "validator_redesign_signal" in reason_codes and sample_size >= PAPER_SAMPLE_TARGET else "add_data"
        return action, _dedupe(reason_codes)
    if net_pnl_usd <= 0.0 and closed_count > 0:
        return "redesign", ["non_positive_weekly_pnl"]
    return "continue", ["evidence_progressing"]
```

5. Pass `recommended_action` and `action_reason_codes` into the `FamilyEvidenceSummary(...)` constructor.

- [ ] **Step 4: Render family actions in weekly Markdown**

In `src/crypto_alpha_agent/pipeline/markdown.py`, replace the weekly strategy-family table header with:

```python
        "| Strategy | Action | Action reasons | Sample size | Closed | Failed | Blocked | Net PnL USD | Validation | Near tiny-live review | Rejected reasons |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
```

In the row values, insert:

```python
                        _escape_table_cell(summary.recommended_action),
                        _escape_table_cell(", ".join(summary.action_reason_codes) or "none"),
```

before `summary.sample_size`.

Update the empty row to:

```python
        lines.append("| none | add_data | no_family_evidence | 0 | 0 | 0 | 0 | 0 | 0 | false | none |")
```

- [ ] **Step 5: Run GREEN tests**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_reports.py::test_weekly_report_summarizes_rejections_improvement_degradation_and_sample_progress tests/test_evidence_reports.py::test_weekly_report_assigns_family_actions_and_reasons -q
```

Expected: PASS.

## Task 2: Expansion Preparation Report Model

**Files:**

- Create: `src/crypto_alpha_agent/pipeline/expansion_preparation.py`
- Test: `tests/test_expansion_preparation.py`

- [ ] **Step 1: Write failing report-builder tests**

Create `tests/test_expansion_preparation.py` with:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.expansion_preparation import build_expansion_preparation_report
from crypto_alpha_agent.pipeline.markdown import render_expansion_preparation_markdown


def _source_health_record(
    source: str,
    feed: str,
    *,
    success: bool = True,
    records_written: int = 1,
) -> SourceRecord:
    observed_at = datetime(2026, 5, 23, tzinfo=UTC)
    return SourceRecord(
        record_id=f"{source}:{feed}:source_health:{observed_at.isoformat()}",
        source=source,
        record_type="source_health",
        observed_at=observed_at,
        payload={
            "source": source,
            "feed": feed,
            "success": success,
            "attempts": 1,
            "failure": None if success else "provider unavailable",
            "observed_at": observed_at.isoformat(),
            "records_fetched": records_written,
            "records_written": records_written,
            "network_route": "direct",
        },
    )


def test_expansion_preparation_report_prioritizes_sources_and_fails_closed_without_health(tmp_path):
    report = build_expansion_preparation_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )

    source_ids = [source.source_id for source in report.source_candidates]
    assert source_ids[:3] == [
        "binance_usdm_open_interest",
        "binance_usdm_open_interest_history",
        "coinalyze_derivatives_history",
    ]
    assert report.source_candidates[0].readiness == "needs_source_probe"
    assert report.source_candidates[0].blocked_reasons == [
        "source_health_missing",
        "source_probe_required",
    ]
    assert report.source_candidates[2].credential_requirement == "required_api_key"
    assert "credential_required" in report.source_candidates[2].blocked_reasons
    assert report.uses_real_capital is False
    assert report.live_order_routing is False


def test_expansion_preparation_report_uses_registry_weekly_actions_and_source_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records([
        _source_health_record("dexscreener", "pairs"),
        _source_health_record("defillama", "yield_pools"),
    ])

    report = build_expansion_preparation_report(
        db_path=db_path,
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )
    sources = {source.source_id: source for source in report.source_candidates}
    strategies = {strategy.strategy_family: strategy for strategy in report.strategy_candidates}

    assert sources["dexscreener_liquidity_snapshots"].source_health_present is True
    assert sources["dexscreener_liquidity_snapshots"].readiness == "health_recorded"
    assert sources["defillama_yield_pools"].source_health_present is True
    assert strategies["funding_mean_reversion_after_extreme"].adapter_kind == "deterministic_validator"
    assert strategies["defi_yield_regime_watchlist"].adapter_kind == "watchlist_only_adapter"
    assert strategies["dex_liquidity_volume_watchlist"].adapter_kind == "watchlist_only_adapter"
    assert strategies["funding_oi_crowding_candidate"].readiness == "blocked"
    assert "validator_or_watchlist_not_registered" in strategies["funding_oi_crowding_candidate"].blocked_reasons
    assert report.reason_codes
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_expansion_preparation.py::test_expansion_preparation_report_prioritizes_sources_and_fails_closed_without_health tests/test_expansion_preparation.py::test_expansion_preparation_report_uses_registry_weekly_actions_and_source_health -q
```

Expected: FAIL because `pipeline.expansion_preparation` and the renderer do not exist.

- [ ] **Step 3: Implement report models and catalog**

Create `src/crypto_alpha_agent/pipeline/expansion_preparation.py`:

```python
from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.evidence_reports import WeeklyEvidenceReport, build_weekly_evidence_report
from crypto_alpha_agent.strategy import default_strategy_registry

SourceReadiness = Literal["health_recorded", "needs_source_probe", "blocked"]
StrategyReadiness = Literal["registered", "blocked"]
AdapterKind = Literal["deterministic_validator", "watchlist_only_adapter", "blocked"]
CredentialRequirement = Literal["none", "optional_api_key", "required_api_key"]
NextPhase = Literal["phase_8_data_depth", "phase_9_strategy_validators"]


class _StrictExpansionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExpansionSourceCandidate(_StrictExpansionModel):
    priority: int = Field(ge=1)
    source_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    feed: str = Field(min_length=1)
    endpoint_family: str = Field(min_length=1)
    data_fields: list[str] = Field(min_length=1)
    credential_requirement: CredentialRequirement
    source_health_source: str = Field(min_length=1)
    source_health_feed: str = Field(min_length=1)
    source_health_present: bool
    latest_source_health_route: str = "unknown"
    readiness: SourceReadiness
    blocked_reasons: list[str] = Field(default_factory=list)
    next_phase: NextPhase = "phase_8_data_depth"
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class ExpansionStrategyCandidate(_StrictExpansionModel):
    priority: int = Field(ge=1)
    strategy_family: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    adapter_kind: AdapterKind
    readiness: StrategyReadiness
    required_data_fields: list[str] = Field(min_length=1)
    recommended_action: Literal["continue", "stop", "redesign", "add_data"]
    action_reason_codes: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    next_phase: NextPhase = "phase_9_strategy_validators"
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class ExpansionPreparationReport(_StrictExpansionModel):
    source_candidates: list[ExpansionSourceCandidate]
    strategy_candidates: list[ExpansionStrategyCandidate]
    weekly_report: WeeklyEvidenceReport
    source_readiness_counts: dict[str, int]
    strategy_action_counts: dict[str, int]
    reason_codes: list[str] = Field(default_factory=list)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False
```

Add catalog constants below the models:

```python
_SOURCE_CATALOG = [
    {
        "priority": 1,
        "source_id": "binance_usdm_open_interest",
        "display_name": "Binance USD-M Current Open Interest",
        "provider": "binance_usdm",
        "feed": "open_interest",
        "endpoint_family": "GET /fapi/v1/openInterest",
        "data_fields": ["symbol", "open_interest", "observed_at"],
        "credential_requirement": "none",
        "source_health_source": "binance_usdm",
        "source_health_feed": "open_interest",
    },
    {
        "priority": 2,
        "source_id": "binance_usdm_open_interest_history",
        "display_name": "Binance USD-M Open Interest History",
        "provider": "binance_usdm",
        "feed": "open_interest_history",
        "endpoint_family": "GET /futures/data/openInterestHist",
        "data_fields": ["symbol", "open_interest", "open_interest_value", "timestamp"],
        "credential_requirement": "none",
        "source_health_source": "binance_usdm",
        "source_health_feed": "open_interest_history",
    },
    {
        "priority": 3,
        "source_id": "coinalyze_derivatives_history",
        "display_name": "Coinalyze Derivatives History",
        "provider": "coinalyze",
        "feed": "derivatives_history",
        "endpoint_family": "open-interest-history, funding-rate-history, liquidation-history, long-short-ratio-history",
        "data_fields": ["open_interest", "funding_rate", "liquidation_long", "liquidation_short", "long_short_ratio"],
        "credential_requirement": "required_api_key",
        "source_health_source": "coinalyze",
        "source_health_feed": "derivatives_history",
    },
    {
        "priority": 4,
        "source_id": "ccxt_open_interest_history",
        "display_name": "CCXT Open Interest History",
        "provider": "ccxt",
        "feed": "open_interest_history",
        "endpoint_family": "fetchOpenInterestHistory when exchange-supported",
        "data_fields": ["exchange", "symbol", "open_interest", "timestamp"],
        "credential_requirement": "none",
        "source_health_source": "ccxt",
        "source_health_feed": "open_interest_history",
    },
    {
        "priority": 5,
        "source_id": "defillama_yield_pools",
        "display_name": "DefiLlama Yield Pools",
        "provider": "defillama",
        "feed": "yield_pools",
        "endpoint_family": "GET /pools",
        "data_fields": ["chain", "project", "symbol", "tvl_usd", "apy"],
        "credential_requirement": "none",
        "source_health_source": "defillama",
        "source_health_feed": "yield_pools",
    },
    {
        "priority": 6,
        "source_id": "defillama_fundamentals",
        "display_name": "DefiLlama TVL, Stablecoins, Fees, And Revenue",
        "provider": "defillama",
        "feed": "fundamentals",
        "endpoint_family": "TVL, stablecoins, fees, revenue, volumes",
        "data_fields": ["tvl", "stablecoin_supply", "fees", "revenue", "dex_volume"],
        "credential_requirement": "none",
        "source_health_source": "defillama",
        "source_health_feed": "fundamentals",
    },
    {
        "priority": 7,
        "source_id": "dexscreener_liquidity_snapshots",
        "display_name": "DEX Screener Liquidity Snapshots",
        "provider": "dexscreener",
        "feed": "pairs",
        "endpoint_family": "latest/dex/search, latest/dex/pairs, tokens/v1",
        "data_fields": ["chain", "dex", "pair_address", "liquidity_usd", "volume_24h_usd"],
        "credential_requirement": "none",
        "source_health_source": "dexscreener",
        "source_health_feed": "pairs",
    },
]
```

Add strategy catalog and builder functions:

```python
_STRATEGY_CATALOG = [
    {
        "priority": 1,
        "strategy_family": "funding_mean_reversion_after_extreme",
        "display_name": "Funding Mean Reversion After Extreme",
        "required_data_fields": ["market_candle", "funding_rate", "open_interest"],
    },
    {
        "priority": 2,
        "strategy_family": "funding_oi_crowding_candidate",
        "display_name": "Funding Plus OI Crowding Candidate",
        "required_data_fields": ["market_candle", "funding_rate", "open_interest"],
    },
    {
        "priority": 3,
        "strategy_family": "cross_exchange_funding_dispersion_candidate",
        "display_name": "Cross-Exchange Funding Dispersion Candidate",
        "required_data_fields": ["multi_exchange_funding_rate", "symbol_normalization"],
    },
    {
        "priority": 4,
        "strategy_family": "defi_yield_regime_watchlist",
        "display_name": "DefiLlama Yield Regime Watchlist",
        "required_data_fields": ["defi_yield", "tvl_usd", "apy"],
    },
    {
        "priority": 5,
        "strategy_family": "defi_stablecoin_tvl_regime_candidate",
        "display_name": "DeFi Stablecoin And TVL Regime Candidate",
        "required_data_fields": ["stablecoin_supply", "protocol_tvl", "fees", "revenue"],
    },
    {
        "priority": 6,
        "strategy_family": "dex_liquidity_volume_watchlist",
        "display_name": "DEX Liquidity And Volume Regime Watchlist",
        "required_data_fields": ["dex_pair", "liquidity_usd", "volume_24h_usd"],
    },
]


def build_expansion_preparation_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    current_capital_usd: float = 300.0,
) -> ExpansionPreparationReport:
    store = ResearchDataStore(db_path)
    source_health_records = store.load_records(record_type="source_health")
    weekly_report = build_weekly_evidence_report(db_path=db_path, memory_path=memory_path)
    registry = default_strategy_registry(current_capital_usd=current_capital_usd)
    weekly_by_family = {
        summary.strategy_family: summary for summary in weekly_report.family_summaries
    }
    sources = [
        _source_candidate(definition, source_health_records)
        for definition in _SOURCE_CATALOG
    ]
    strategies = [
        _strategy_candidate(definition, registry=registry, weekly_by_family=weekly_by_family)
        for definition in _STRATEGY_CATALOG
    ]
    return ExpansionPreparationReport(
        source_candidates=sources,
        strategy_candidates=strategies,
        weekly_report=weekly_report,
        source_readiness_counts=dict(Counter(source.readiness for source in sources)),
        strategy_action_counts=dict(Counter(strategy.recommended_action for strategy in strategies)),
        reason_codes=_report_reason_codes(sources, strategies),
    )
```

Add helpers:

```python
def _source_candidate(definition: dict[str, object], records: list[object]) -> ExpansionSourceCandidate:
    latest = _latest_source_health(
        records,
        source=str(definition["source_health_source"]),
        feed=str(definition["source_health_feed"]),
    )
    blocked_reasons: list[str] = []
    route = "unknown"
    if latest is None:
        blocked_reasons.extend(["source_health_missing", "source_probe_required"])
        readiness: SourceReadiness = "needs_source_probe"
    else:
        payload = latest.payload
        route = str(payload.get("network_route", "unknown"))
        if not bool(payload.get("success")):
            blocked_reasons.append("source_health_failed")
        if int(payload.get("records_written", 0)) <= 0:
            blocked_reasons.append("no_typed_records")
        readiness = "health_recorded" if not blocked_reasons else "blocked"
    if definition["credential_requirement"] == "required_api_key":
        blocked_reasons.append("credential_required")
    return ExpansionSourceCandidate(
        **definition,
        source_health_present=latest is not None,
        latest_source_health_route=route,
        readiness=readiness if blocked_reasons[:1] != ["source_health_failed"] else "blocked",
        blocked_reasons=_dedupe(blocked_reasons),
    )


def _strategy_candidate(
    definition: dict[str, object],
    *,
    registry: object,
    weekly_by_family: dict[str, object],
) -> ExpansionStrategyCandidate:
    family = str(definition["strategy_family"])
    blocked_reasons: list[str] = []
    try:
        spec = registry.get(family)
    except KeyError:
        spec = None
    summary = weekly_by_family.get(family)
    if spec is None:
        adapter_kind: AdapterKind = "blocked"
        readiness: StrategyReadiness = "blocked"
        blocked_reasons.append("validator_or_watchlist_not_registered")
    else:
        adapter_kind = "deterministic_validator" if spec.supports_paper_simulation else "watchlist_only_adapter"
        readiness = "registered"
        blocked_reasons.extend(spec.blocked_reasons)
    if family == "funding_mean_reversion_after_extreme":
        blocked_reasons.append("open_interest_confirmation_missing")
    recommended_action = getattr(summary, "recommended_action", "add_data")
    action_reason_codes = list(getattr(summary, "action_reason_codes", ["no_weekly_family_evidence"]))
    if blocked_reasons and "validator_or_watchlist_not_registered" in blocked_reasons:
        recommended_action = "add_data"
        action_reason_codes = _dedupe([*action_reason_codes, "register_validator_or_watchlist"])
    return ExpansionStrategyCandidate(
        **definition,
        adapter_kind=adapter_kind,
        readiness=readiness,
        recommended_action=recommended_action,
        action_reason_codes=action_reason_codes,
        blocked_reasons=_dedupe(blocked_reasons),
    )


def _latest_source_health(records: list[object], *, source: str, feed: str):
    matches = [
        record
        for record in records
        if record.source == source and str(record.payload.get("feed", "")) == feed
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda record: record.observed_at)[-1]


def _report_reason_codes(
    sources: list[ExpansionSourceCandidate],
    strategies: list[ExpansionStrategyCandidate],
) -> list[str]:
    codes: list[str] = ["phase_5_expansion_preparation"]
    if any(source.blocked_reasons for source in sources):
        codes.append("source_candidates_need_probe")
    if any(strategy.blocked_reasons for strategy in strategies):
        codes.append("strategy_candidates_need_data_or_adapter")
    if any(strategy.adapter_kind == "watchlist_only_adapter" for strategy in strategies):
        codes.append("watchlist_adapters_registered")
    return _dedupe(codes)


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
```

- [ ] **Step 4: Run GREEN report tests**

Run:

```bash
uv run --extra dev pytest tests/test_expansion_preparation.py::test_expansion_preparation_report_prioritizes_sources_and_fails_closed_without_health tests/test_expansion_preparation.py::test_expansion_preparation_report_uses_registry_weekly_actions_and_source_health -q
```

Expected: PASS.

## Task 3: Expansion Preparation Markdown And CLI

**Files:**

- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_expansion_preparation.py`

- [ ] **Step 1: Write failing Markdown and CLI tests**

Append to `tests/test_expansion_preparation.py`:

```python
def test_expansion_preparation_markdown_lists_sources_strategies_and_blockers(tmp_path):
    report = build_expansion_preparation_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )

    markdown = render_expansion_preparation_markdown(report)

    assert markdown.startswith("# Phase 5 Expansion Preparation Report")
    assert "## Source Candidates" in markdown
    assert "binance_usdm_open_interest" in markdown
    assert "source_health_missing" in markdown
    assert "## Strategy Candidates" in markdown
    assert "funding_oi_crowding_candidate" in markdown
    assert "validator_or_watchlist_not_registered" in markdown
    assert "Real capital: false" in markdown
    assert "Live order routing: false" in markdown


def test_expansion_preparation_cli_writes_markdown_without_live_authority(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    out = tmp_path / "phase5.md"

    exit_code = main(
        [
            "expansion-prep-report",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--out",
            str(out),
            "--current-capital-usd",
            "300",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    markdown = out.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["command"] == "expansion-prep-report"
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["report"]["source_candidates"][0]["source_id"] == "binance_usdm_open_interest"
    assert payload["expansion_prep_report_out"] == str(out)
    assert "Phase 5 Expansion Preparation Report" in markdown
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_expansion_preparation.py::test_expansion_preparation_markdown_lists_sources_strategies_and_blockers tests/test_expansion_preparation.py::test_expansion_preparation_cli_writes_markdown_without_live_authority -q
```

Expected: FAIL because the renderer and CLI command do not exist.

- [ ] **Step 3: Add Markdown renderer**

In `src/crypto_alpha_agent/pipeline/markdown.py`, import `ExpansionPreparationReport`:

```python
from crypto_alpha_agent.pipeline.expansion_preparation import ExpansionPreparationReport
```

Add this function before `_llm_summary_lines(...)`:

```python
def render_expansion_preparation_markdown(report: ExpansionPreparationReport) -> str:
    lines = [
        "# Phase 5 Expansion Preparation Report",
        "",
        "## Safety",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        "",
        "## Decision",
        f"Reason codes: {_escape_text(', '.join(report.reason_codes) or 'none')}",
        "",
        "## Source Readiness",
        "| Readiness | Count |",
        "| --- | ---: |",
    ]
    for readiness, count in sorted(report.source_readiness_counts.items()):
        lines.append(f"| {_escape_table_cell(readiness)} | {count:g} |")
    if not report.source_readiness_counts:
        lines.append("| none | 0 |")
    lines.extend(
        [
            "",
            "## Source Candidates",
            "| Priority | Source | Provider | Feed | Credentials | Health | Route | Readiness | Blocked reasons | Next phase |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for source in report.source_candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{source.priority:g}",
                    _escape_table_cell(source.source_id),
                    _escape_table_cell(source.provider),
                    _escape_table_cell(source.feed),
                    _escape_table_cell(source.credential_requirement),
                    _bool_text(source.source_health_present),
                    _escape_table_cell(source.latest_source_health_route),
                    _escape_table_cell(source.readiness),
                    _escape_table_cell(", ".join(source.blocked_reasons) or "none"),
                    _escape_table_cell(source.next_phase),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Strategy Actions",
            "| Action | Count |",
            "| --- | ---: |",
        ]
    )
    for action, count in sorted(report.strategy_action_counts.items()):
        lines.append(f"| {_escape_table_cell(action)} | {count:g} |")
    if not report.strategy_action_counts:
        lines.append("| none | 0 |")
    lines.extend(
        [
            "",
            "## Strategy Candidates",
            "| Priority | Strategy | Adapter | Readiness | Action | Action reasons | Blocked reasons | Next phase |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for strategy in report.strategy_candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{strategy.priority:g}",
                    _escape_table_cell(strategy.strategy_family),
                    _escape_table_cell(strategy.adapter_kind),
                    _escape_table_cell(strategy.readiness),
                    _escape_table_cell(strategy.recommended_action),
                    _escape_table_cell(", ".join(strategy.action_reason_codes) or "none"),
                    _escape_table_cell(", ".join(strategy.blocked_reasons) or "none"),
                    _escape_table_cell(strategy.next_phase),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Add CLI parser and handler**

In `src/crypto_alpha_agent/cli.py`, add imports:

```python
from crypto_alpha_agent.pipeline.expansion_preparation import build_expansion_preparation_report
```

and add `render_expansion_preparation_markdown` to the existing `pipeline.markdown` import list.

In `build_parser()`, after the `evidence-report` parser block, add:

```python
    expansion_prep_parser = subparsers.add_parser(
        "expansion-prep-report",
        help="Generate the read-only Phase 5 data and strategy expansion preparation report.",
    )
    expansion_prep_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    expansion_prep_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    expansion_prep_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown report.")
    expansion_prep_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used to evaluate registry constraints.",
    )
    expansion_prep_parser.set_defaults(handler=_handle_expansion_prep_report)
```

Add handler near `_handle_evidence_report(...)`:

```python
def _handle_expansion_prep_report(args: argparse.Namespace) -> dict[str, Any]:
    report = build_expansion_preparation_report(
        db_path=args.db,
        memory_path=args.memory,
        current_capital_usd=args.current_capital_usd,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_expansion_preparation_markdown(report), encoding="utf-8")
    return {
        "command": "expansion-prep-report",
        "expansion_prep_report_out": str(args.out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
    }
```

- [ ] **Step 5: Run GREEN CLI tests**

Run:

```bash
uv run --extra dev pytest tests/test_expansion_preparation.py -q
```

Expected: PASS.

## Task 4: Documentation And Phase Records

**Files:**

- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-23-phase-5-data-strategy-expansion-preparation-completion-report.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Update runbook**

In `docs/runbook.md`, after the weekly evidence report example, add:

```markdown
### Phase 5 Expansion Preparation Report

The Phase 5 report is read-only. It ranks future data-source and strategy-family
expansion candidates for Phase 8 and Phase 9, checks whether source-health
records exist, and records stable blocked reasons for missing probes, missing
typed records, optional credentials, and unregistered validators or watchlists.
It does not probe providers, place orders, read wallet keys, or enable live
execution.

```bash
uv run --extra dev crypto-alpha-agent expansion-prep-report \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/phase5/expansion-prep.md \
  --current-capital-usd 300
```
```

- [ ] **Step 2: Update roadmap**

In `docs/roadmap.md`:

- Rename the old top-level `## Phase 5: Tiny Live Readiness Review - Artifact Only` heading to `## Completed Legacy Phase 5: Tiny Live Readiness Review - Artifact Only`.
- In the immediate sequence text around the Phase 0-5 section, state that Immediate Phases 0-4 are complete and Immediate Phase 5 is the current preparation slice before Phases 8-12.
- Under `#### Immediate Phase 5: Data And Strategy Expansion`, add a completion note:

```markdown
Status as of 2026-05-23: complete.

Implemented:

- Weekly family summaries now include a recommended action of `continue`,
  `stop`, `redesign`, or `add_data` with stable reason codes.
- Added a read-only `expansion-prep-report` command that ranks source and
  strategy expansion candidates for Phase 8 and Phase 9.
- Source candidates fail closed when source-health records are missing,
  failed, credential-gated, or have no typed records.
- Strategy candidates fail closed when a deterministic validator or
  watchlist-only adapter is not registered.
- The phase did not add live trading, wallet-key access, exchange order
  routing, MEV, speed-edge execution, premium RPC dependency, or real-capital
  authority.
```

- [ ] **Step 3: Update project completion state**

Rewrite the current round section in `docs/goals/project-completion-state.md` for Round 7 / Immediate Phase 5:

```markdown
## Current Round

- Round: 7
- Status: Immediate Phase 5 complete; committed and pushed
- Started: 2026-05-23
- Completed: 2026-05-23
- Active slice: Immediate Phase 5: Data And Strategy Expansion preparation
- Active plan source:
  `docs/superpowers/plans/2026-05-23-phase-5-data-strategy-expansion-preparation.md`
- Phase report:
  `docs/goals/phase-reports/2026-05-23-phase-5-data-strategy-expansion-preparation-completion-report.md`
```

Also update "Known Remaining Gaps" so Immediate Phase 5 is listed as complete and Phase 8 is next. Replace the stale next-round source-health instruction with:

```markdown
8. Use the local proxy variables in `.env` for public-data endpoints that fail
   direct probing, and record source health with route `direct`, `proxy`,
   `blocked`, or `not_applicable`; record provider failures as separate
   failure reasons.
```

Add Round 7 to the round history after verification.

- [ ] **Step 4: Add Phase 5 completion report**

Create `docs/goals/phase-reports/2026-05-23-phase-5-data-strategy-expansion-preparation-completion-report.md` with:

```markdown
# Phase 5 Data And Strategy Expansion Preparation Completion Report

Date: 2026-05-23

## Objective

Complete Immediate Phase 5 by preparing the data-source and strategy-family
expansion path for Phase 8 and Phase 9 without implementing live trading,
wallet access, exchange order routing, MEV, speed-edge execution, premium RPC,
or real-capital authority.

## External Evidence

Smart Search evidence is stored at
`/tmp/smart-search-evidence/2026-05-23-phase5-data-strategy-expansion/`.

Source-backed findings:

- Binance USD-M futures documents public open-interest and funding endpoints.
- CCXT documents public derivatives-market methods where exchange support is
  available.
- Coinalyze documents open-interest, funding, liquidation, and long/short
  history behind an API-key route, so it remains optional.
- DefiLlama documents TVL, stablecoins, yields, fees, revenue, volumes, and
  perps/open-interest overview data.
- DEX Screener documents pair/token liquidity and volume endpoints.
- Binance force-order/liquidation docs were not successfully fetched in this
  round, so liquidation expansion relies only on the verified Coinalyze docs.

## Local Feasibility

- Existing watchlist adapters covered DeFi yield regimes and DEX liquidity
  migration.
- Existing source-health, data-quality, weekly report, and registry seams could
  support a read-only preparation report.
- The experiment planner was not widened because it intentionally filters to
  executable funding/price families.

## Implemented

- Added weekly family action decisions with stable action reason codes.
- Added a read-only expansion preparation report builder and Markdown renderer.
- Added `crypto-alpha-agent expansion-prep-report`.
- Added focused tests for source-candidate fail-closed behavior, registry
  adapter classification, weekly action decisions, CLI output, and Markdown.
- Updated runbook, roadmap, state, and this completion report.

## Verification

Record final focused tests, full pytest, ruff, diff checks, staged diff checks,
and secret scan results here after they are run.

## Safety

- `uses_real_capital=false`
- `live_order_routing=false`
- No wallet keys, exchange live order routing, MEV, premium RPC, speed-edge
  execution, or real-capital deployment were added.
```

- [ ] **Step 5: Run documentation check**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: PASS.

## Task 5: Review, Verification, Commit, And Push

**Files:**

- All changed files from Tasks 1-4.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_expansion_preparation.py tests/test_evidence_reports.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
```

Expected: all pass.

- [ ] **Step 3: Request review pass 1**

Spawn at least one subagent for requirements/spec review:

- Verify Phase 5 completion standards from `docs/roadmap.md`.
- Verify no Phase 8 source-probe implementation or Phase 9 validator implementation leaked into this phase.
- Verify all new source/strategy candidates fail closed with stable reasons.
- Verify hard boundaries remain blocked.

Fix all Critical and Important findings.

- [ ] **Step 4: Request review pass 2**

Spawn at least one subagent for code-quality/safety review:

- Review `expansion_preparation.py`, weekly action logic, Markdown, CLI output, docs, and tests.
- Check strict Pydantic models, deterministic ordering, safe flags, redaction/secret-safety, and compatibility with existing weekly reports.

Fix all Critical and Important findings and rerun focused tests.

- [ ] **Step 5: Stage and run staged checks**

Run:

```bash
git add src/crypto_alpha_agent/pipeline/evidence_reports.py \
  src/crypto_alpha_agent/pipeline/markdown.py \
  src/crypto_alpha_agent/pipeline/expansion_preparation.py \
  src/crypto_alpha_agent/cli.py \
  tests/test_expansion_preparation.py \
  tests/test_evidence_reports.py \
  docs/runbook.md \
  docs/roadmap.md \
  docs/goals/project-completion-state.md \
  docs/goals/phase-reports/2026-05-23-phase-5-data-strategy-expansion-preparation-completion-report.md \
  docs/superpowers/plans/2026-05-23-phase-5-data-strategy-expansion-preparation.md
git diff --cached --check
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

Expected: both pass and secret scan outputs no findings.

- [ ] **Step 6: Commit and push**

Run:

```bash
git commit -m "feat: add expansion preparation report"
git push
git status --short --branch --untracked-files=all
```

Expected: commit and push succeed, and status is clean on `main...origin/main`.

## Plan Self-Review

- Spec coverage: The plan covers Smart Search evidence, local feasibility, subagent findings, weekly family actions, source-health preparation, strategy adapter readiness, read-only CLI reporting, docs, verification, reviews, commit, and push.
- Placeholder scan: No `TBD`, `TODO`, or unspecified test/implementation steps remain.
- Type consistency: The plan consistently uses `recommended_action`, `action_reason_codes`, `ExpansionPreparationReport`, `ExpansionSourceCandidate`, `ExpansionStrategyCandidate`, and `expansion-prep-report`.
- Scope check: This is one Phase 5 preparation slice only. It does not implement Phase 8 source probes or Phase 9 validators.
