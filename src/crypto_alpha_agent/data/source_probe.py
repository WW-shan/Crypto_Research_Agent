from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore

ProbeRoute = Literal["auto", "direct", "proxy"]
ProbeNetworkRoute = Literal["direct", "proxy", "blocked", "unavailable"]
ProviderStatus = Literal[
    "Candidate",
    "Reachable",
    "ReachableViaProxy",
    "Parseable",
    "ResearchUsable",
    "ProductionResearchSource",
]
ParseStatus = Literal["not_attempted", "blocked", "parsed", "parse_failed"]
CredentialRequirement = Literal["none", "optional_api_key", "required_api_key"]
HttpMethod = Literal["GET", "POST"]

_PROXY_ENV_NAMES = (
    "CRYPTO_ALPHA_AGENT_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


class _StrictProbeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class SourceProbeTarget(_StrictProbeModel):
    target_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    feed: str = Field(min_length=1)
    endpoint_family: str = Field(min_length=1)
    url_family: str = Field(min_length=1)
    url: str = Field(min_length=1)
    method: HttpMethod = "GET"
    typed_count_path: tuple[str, ...] = Field(default_factory=tuple)
    expected_fields: tuple[str, ...] = Field(default_factory=tuple)
    rate_limit_assumption: str = "provider_documented"
    credential_requirement: CredentialRequirement = "none"
    core_source: bool = True
    schema_version: str = "source_probe.v1"
    body: dict[str, Any] | None = None


class SourceProbeResult(_StrictProbeModel):
    target_id: str
    source: str
    feed: str
    endpoint_family: str
    url_family: str
    network_route: ProbeNetworkRoute
    provider_status: ProviderStatus
    status_transitions: list[ProviderStatus]
    http_status: int | None = None
    parse_status: ParseStatus
    typed_record_count: int = Field(ge=0)
    schema_version: str
    blocked_reason: str | None = None
    observed_at: datetime
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False
    exit_code: int = Field(ge=0)


class SourceProbeSummary(_StrictProbeModel):
    targets: list[SourceProbeTarget]
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


_TARGETS: tuple[SourceProbeTarget, ...] = (
    SourceProbeTarget(
        target_id="binance_usdm_open_interest_history",
        display_name="Binance USD-M Open Interest History",
        source="binance_usdm",
        feed="open_interest_history",
        endpoint_family="GET /futures/data/openInterestHist",
        url_family="binance_usdm_open_interest_history",
        url=(
            "https://fapi.binance.com/futures/data/openInterestHist"
            "?symbol=BTCUSDT&period=1h&limit=1"
        ),
        typed_count_path=(),
        expected_fields=("symbol", "sumOpenInterest", "timestamp"),
        rate_limit_assumption="1000 requests per 5 minutes per Binance docs",
    ),
    SourceProbeTarget(
        target_id="binance_usdm_premium_index_klines",
        display_name="Binance USD-M Premium Index Klines",
        source="binance_usdm",
        feed="premium_index_klines",
        endpoint_family="GET /fapi/v1/premiumIndexKlines",
        url_family="binance_usdm_premium_index_klines",
        url=(
            "https://fapi.binance.com/fapi/v1/premiumIndexKlines"
            "?symbol=BTCUSDT&interval=1h&limit=1"
        ),
        typed_count_path=(),
        expected_fields=("open_time", "open", "close_time"),
        rate_limit_assumption="weight depends on limit per Binance docs",
    ),
    SourceProbeTarget(
        target_id="binance_usdm_basis",
        display_name="Binance USD-M Basis",
        source="binance_usdm",
        feed="basis",
        endpoint_family="GET /futures/data/basis",
        url_family="binance_usdm_basis",
        url=(
            "https://fapi.binance.com/futures/data/basis"
            "?pair=BTCUSDT&contractType=PERPETUAL&period=1h&limit=1"
        ),
        typed_count_path=(),
        expected_fields=("pair", "basis", "timestamp"),
        rate_limit_assumption="latest 30 days per Binance docs",
    ),
    SourceProbeTarget(
        target_id="binance_usdm_global_long_short_account_ratio",
        display_name="Binance USD-M Global Long/Short Account Ratio",
        source="binance_usdm",
        feed="global_long_short_account_ratio",
        endpoint_family="GET /futures/data/globalLongShortAccountRatio",
        url_family="binance_usdm_global_long_short_account_ratio",
        url=(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
            "?symbol=BTCUSDT&period=1h&limit=1"
        ),
        typed_count_path=(),
        expected_fields=("symbol", "longShortRatio", "timestamp"),
        rate_limit_assumption="latest 30 days and 1000 requests per 5 minutes per Binance docs",
    ),
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
    SourceProbeTarget(
        target_id="bybit_open_interest_history",
        display_name="Bybit Open Interest History",
        source="bybit",
        feed="open_interest_history",
        endpoint_family="GET /v5/market/open-interest",
        url_family="bybit_open_interest_history",
        url=(
            "https://api.bybit.com/v5/market/open-interest"
            "?category=linear&symbol=BTCUSDT&intervalTime=1h&limit=1"
        ),
        typed_count_path=("result", "list"),
        expected_fields=("openInterest", "timestamp"),
        rate_limit_assumption="Bybit V5 public market-data limits",
    ),
    SourceProbeTarget(
        target_id="okx_open_interest",
        display_name="OKX Open Interest",
        source="okx",
        feed="open_interest",
        endpoint_family="GET /api/v5/public/open-interest",
        url_family="okx_open_interest",
        url=(
            "https://www.okx.com/api/v5/public/open-interest"
            "?instType=SWAP&instId=BTC-USDT-SWAP"
        ),
        typed_count_path=("data",),
        expected_fields=("instId", "oi", "oiUsd"),
        rate_limit_assumption="20 requests per 2 seconds for public data family",
    ),
    SourceProbeTarget(
        target_id="dexscreener_pairs",
        display_name="DEX Screener Pair Search",
        source="dexscreener",
        feed="pairs",
        endpoint_family="GET /latest/dex/search",
        url_family="dexscreener_pairs",
        url="https://api.dexscreener.com/latest/dex/search?q=ETH%20USDC",
        typed_count_path=("pairs",),
        expected_fields=("chainId", "dexId", "pairAddress"),
        rate_limit_assumption="300 requests per minute for pair endpoints",
    ),
    SourceProbeTarget(
        target_id="defillama_yield_pools",
        display_name="DefiLlama Yield Pools",
        source="defillama",
        feed="yield_pools",
        endpoint_family="GET /pools",
        url_family="defillama_yield_pools",
        url="https://yields.llama.fi/pools",
        typed_count_path=("data",),
        expected_fields=("chain", "project", "symbol", "tvlUsd", "apy"),
        rate_limit_assumption="free public endpoint, reasonable-use limits",
    ),
    SourceProbeTarget(
        target_id="defillama_fundamentals",
        display_name="DefiLlama Protocol Fundamentals",
        source="defillama",
        feed="fundamentals",
        endpoint_family="GET /protocols",
        url_family="defillama_fundamentals",
        url="https://api.llama.fi/protocols",
        typed_count_path=(),
        expected_fields=("name", "symbol", "tvl"),
        rate_limit_assumption="free public endpoint, reasonable-use limits",
    ),
    SourceProbeTarget(
        target_id="dune_query_result",
        display_name="Dune Latest Query Result",
        source="dune",
        feed="query_result",
        endpoint_family="GET /v1/query/{query_id}/results",
        url_family="dune_query_result",
        url="https://api.dune.com/api/v1/query/123456/results?limit=1",
        typed_count_path=("result", "rows"),
        expected_fields=(),
        rate_limit_assumption="credentialed Dune API read scope",
        credential_requirement="required_api_key",
        core_source=False,
    ),
    SourceProbeTarget(
        target_id="thegraph_pool_snapshot",
        display_name="The Graph Pool Snapshot",
        source="thegraph",
        feed="pool_snapshot",
        endpoint_family="POST GraphQL subgraph query",
        url_family="thegraph_pool_snapshot",
        url="https://gateway.thegraph.com/api/subgraphs/id/example",
        method="POST",
        typed_count_path=("data", "pools"),
        expected_fields=("id",),
        rate_limit_assumption="subgraph and gateway dependent",
        credential_requirement="optional_api_key",
        core_source=False,
        body={"query": "{ pools(first: 1) { id } _meta { hasIndexingErrors } }"},
    ),
)


def available_probe_targets() -> list[SourceProbeTarget]:
    return list(_TARGETS)


def probe_target(
    *,
    db_path: str | Path,
    target_id: str,
    allow_network: bool,
    route: ProbeRoute = "auto",
    env: dict[str, str] | None = None,
    session: Any | None = None,
    credential_configured: bool = False,
    now: datetime | None = None,
) -> SourceProbeResult:
    target = _target_by_id(target_id)
    observed_at = now or datetime.now(tz=UTC)
    session = session or requests.Session()

    if not allow_network:
        return _persist_result(
            db_path,
            _blocked_result(
                target,
                observed_at=observed_at,
                network_route="blocked",
                blocked_reason="network_not_allowed",
            ),
        )
    if (
        target.credential_requirement == "required_api_key"
        and not credential_configured
    ):
        return _persist_result(
            db_path,
            _blocked_result(
                target,
                observed_at=observed_at,
                network_route="blocked",
                blocked_reason="credential_required",
            ),
        )

    network_route = _resolve_network_route(route, env=env)
    if network_route == "blocked":
        return _persist_result(
            db_path,
            _blocked_result(
                target,
                observed_at=observed_at,
                network_route="blocked",
                blocked_reason="proxy_not_configured",
            ),
        )

    transitions: list[ProviderStatus] = ["Candidate"]
    route_kwargs = _request_route_kwargs(network_route, env=env)
    try:
        response = _request_target(target, session=session, route_kwargs=route_kwargs)
    except Exception as exc:
        return _persist_result(
            db_path,
            SourceProbeResult(
                target_id=target.target_id,
                source=target.source,
                feed=target.feed,
                endpoint_family=target.endpoint_family,
                url_family=target.url_family,
                network_route="unavailable",
                provider_status="Candidate",
                status_transitions=transitions,
                http_status=None,
                parse_status="not_attempted",
                typed_record_count=0,
                schema_version=target.schema_version,
                blocked_reason=f"request_failed:{exc.__class__.__name__}",
                observed_at=observed_at,
                exit_code=2,
            ),
        )

    http_status = int(getattr(response, "status_code", 0) or 0)
    reachable_status: ProviderStatus = (
        "ReachableViaProxy" if network_route == "proxy" else "Reachable"
    )
    transitions.append(reachable_status)
    if http_status < 200 or http_status >= 300:
        return _persist_result(
            db_path,
            SourceProbeResult(
                target_id=target.target_id,
                source=target.source,
                feed=target.feed,
                endpoint_family=target.endpoint_family,
                url_family=target.url_family,
                network_route=network_route,
                provider_status=reachable_status,
                status_transitions=transitions,
                http_status=http_status,
                parse_status="not_attempted",
                typed_record_count=0,
                schema_version=target.schema_version,
                blocked_reason=f"http_{http_status}",
                observed_at=observed_at,
                exit_code=2,
            ),
        )

    try:
        payload = response.json()
        typed_count, schema_blocked_reason = _typed_record_count(
            payload,
            target.typed_count_path,
            expected_fields=target.expected_fields,
        )
    except Exception:
        return _persist_result(
            db_path,
            SourceProbeResult(
                target_id=target.target_id,
                source=target.source,
                feed=target.feed,
                endpoint_family=target.endpoint_family,
                url_family=target.url_family,
                network_route=network_route,
                provider_status=reachable_status,
                status_transitions=transitions,
                http_status=http_status,
                parse_status="parse_failed",
                typed_record_count=0,
                schema_version=target.schema_version,
                blocked_reason="parse_failed",
                observed_at=observed_at,
                exit_code=2,
            ),
        )

    transitions.append("Parseable")
    provider_status: ProviderStatus = "Parseable"
    blocked_reason = schema_blocked_reason or "no_typed_records"
    exit_code = 2
    if typed_count > 0 and schema_blocked_reason is None:
        transitions.append("ResearchUsable")
        provider_status = "ResearchUsable"
        blocked_reason = None
        exit_code = 0

    return _persist_result(
        db_path,
        SourceProbeResult(
            target_id=target.target_id,
            source=target.source,
            feed=target.feed,
            endpoint_family=target.endpoint_family,
            url_family=target.url_family,
            network_route=network_route,
            provider_status=provider_status,
            status_transitions=transitions,
            http_status=http_status,
            parse_status="parsed",
            typed_record_count=typed_count,
            schema_version=target.schema_version,
            blocked_reason=blocked_reason,
            observed_at=observed_at,
            exit_code=exit_code,
        ),
    )


def _target_by_id(target_id: str) -> SourceProbeTarget:
    for target in _TARGETS:
        if target.target_id == target_id:
            return target
    raise ValueError(f"unknown source-probe target: {target_id}")


def _blocked_result(
    target: SourceProbeTarget,
    *,
    observed_at: datetime,
    network_route: ProbeNetworkRoute,
    blocked_reason: str,
) -> SourceProbeResult:
    return SourceProbeResult(
        target_id=target.target_id,
        source=target.source,
        feed=target.feed,
        endpoint_family=target.endpoint_family,
        url_family=target.url_family,
        network_route=network_route,
        provider_status="Candidate",
        status_transitions=["Candidate"],
        parse_status="blocked",
        typed_record_count=0,
        schema_version=target.schema_version,
        blocked_reason=blocked_reason,
        observed_at=observed_at,
        exit_code=2,
    )


def _persist_result(db_path: str | Path, result: SourceProbeResult) -> SourceProbeResult:
    payload = {
        "source": result.source,
        "feed": result.feed,
        "success": result.exit_code == 0,
        "attempts": 0 if result.network_route == "blocked" else 1,
        "failure": result.blocked_reason,
        "observed_at": result.observed_at.isoformat(),
        "records_fetched": result.typed_record_count,
        "records_written": 0,
        "network_route": result.network_route,
        "provider_status": result.provider_status,
        "status_transitions": result.status_transitions,
        "http_status": result.http_status,
        "parse_status": result.parse_status,
        "typed_record_count": result.typed_record_count,
        "endpoint_family": result.endpoint_family,
        "url_family": result.url_family,
        "schema_version": result.schema_version,
        "blocked_reason": result.blocked_reason,
    }
    store = ResearchDataStore(db_path)
    safe_route = result.network_route.replace("/", "-")
    store.upsert_records(
        [
            SourceRecord(
                record_id=(
                    f"{result.source}:{result.feed}:source_probe:{safe_route}:"
                    f"{result.observed_at.isoformat()}"
                ),
                source=result.source,
                record_type="source_health",
                observed_at=result.observed_at,
                payload=payload,
            )
        ]
    )
    return result


def _resolve_network_route(
    route: ProbeRoute,
    *,
    env: dict[str, str] | None,
) -> ProbeNetworkRoute:
    if route == "direct":
        return "direct"
    if route == "proxy":
        return "proxy" if _proxy_value(env) else "blocked"
    return "proxy" if _proxy_value(env) else "direct"


def _request_route_kwargs(
    network_route: ProbeNetworkRoute,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    if network_route == "proxy":
        proxy = _proxy_value(env)
        if proxy:
            return {"proxies": {"http": proxy, "https": proxy}}
    if network_route == "direct":
        return {"proxies": {"http": None, "https": None}}
    return {}


def _proxy_value(env: dict[str, str] | None) -> str | None:
    source = env if env is not None else os.environ
    for name in _PROXY_ENV_NAMES:
        value = source.get(name)
        if value:
            return value
    return None


def _request_target(
    target: SourceProbeTarget,
    *,
    session: Any,
    route_kwargs: dict[str, Any],
):
    if target.method == "POST":
        return session.post(target.url, json=target.body or {}, timeout=30, **route_kwargs)
    return session.get(target.url, timeout=30, **route_kwargs)


def _typed_record_count(
    payload: Any,
    path: tuple[str, ...],
    *,
    expected_fields: tuple[str, ...],
) -> tuple[int, str | None]:
    rows = _typed_rows(payload, path)
    if not rows:
        return 0, "no_typed_records"

    valid_rows = [row for row in rows if _row_matches_expected_fields(row, expected_fields)]
    if valid_rows:
        return len(valid_rows), None

    if expected_fields and all(isinstance(row, dict) for row in rows):
        observed_fields = sorted({field for row in rows for field in row.keys()})
        missing_fields = [field for field in expected_fields if field not in observed_fields]
        if missing_fields:
            return 0, f"missing_expected_fields:{','.join(missing_fields)}"
    return 0, "unexpected_schema"


def _typed_rows(payload: Any, path: tuple[str, ...]) -> list[Any]:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return []
        current = current.get(key, [])
    if isinstance(current, list):
        return current
    if isinstance(current, dict):
        return [current] if current else []
    return []


def _row_matches_expected_fields(row: Any, expected_fields: tuple[str, ...]) -> bool:
    if not expected_fields:
        return True
    if isinstance(row, dict):
        return all(field in row and row[field] is not None for field in expected_fields)
    if isinstance(row, (list, tuple)):
        return len(row) >= len(expected_fields)
    return False
