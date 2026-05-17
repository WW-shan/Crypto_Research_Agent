from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field


class ScheduledCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    name: str
    argv: list[str]


class DailySchedulePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    command: str = "schedule"
    execution_model: str = "external_operator_cron_calls_evidence_run"
    scheduler_executes_commands: bool = False
    dry_run: bool = True
    runs_subprocesses: bool = False
    sleeps: bool = False
    uses_real_capital: bool = False
    live_order_routing: bool = False
    network_allowed: bool = False
    planned_commands: list[ScheduledCommand] = Field(default_factory=list)
    memory_path: str | None = None


def build_daily_schedule_plan(
    *,
    db_path: str | Path,
    report_out: str | Path,
    memory_path: str | Path | None = None,
    current_capital_usd: float = 300.0,
    run_id: str | None = None,
    include_validation: bool = True,
    allow_network: bool = False,
    symbol: str | None = None,
    funding_symbol: str | None = None,
    timeframe: str = "1h",
    limit: int = 200,
    ccxt_exchange: str = "binance",
    strategy_families: Sequence[str] = (),
    include_offline_check: bool = True,
    include_defillama: bool = False,
    include_dexscreener: bool = False,
    dex_query: str | None = None,
    min_tvl_usd: float | None = None,
    include_dune: bool = False,
    dune_query_id: int | None = None,
    dune_api_key: str | None = None,
    dune_params: Sequence[str] = (),
    include_thegraph: bool = False,
    subgraph_url: str | None = None,
    graph_query: str | None = None,
    graph_variables: Sequence[str] = (),
) -> DailySchedulePlan:
    if not math.isfinite(current_capital_usd) or current_capital_usd <= 0:
        raise ValueError("current_capital_usd must be finite and positive")
    if limit <= 0:
        raise ValueError("limit must be positive")
    if symbol is None or not symbol.strip():
        raise ValueError("--symbol is required when scheduling evidence-run")
    if funding_symbol is None or not funding_symbol.strip():
        raise ValueError("--funding-symbol is required when scheduling evidence-run")
    if not timeframe.strip():
        raise ValueError("--timeframe cannot be blank")
    if not ccxt_exchange.strip():
        raise ValueError("--ccxt-exchange cannot be blank")

    db = str(db_path)
    memory = str(memory_path) if memory_path is not None else str(Path(report_out).with_suffix(".memory.jsonl"))
    report = str(report_out)
    capital = str(current_capital_usd)
    ingest_argv = [
        "crypto-alpha-agent",
        "ingest",
        "--offline-check",
        "--db",
        db,
        "--current-capital-usd",
        capital,
    ]
    evidence_argv = [
        "crypto-alpha-agent",
        "evidence-run",
        "--db",
        db,
        "--memory",
        memory,
        "--report-out",
        report,
        "--current-capital-usd",
        capital,
    ]
    if allow_network:
        evidence_argv.append("--allow-network")
    evidence_argv.extend(
        [
            "--ccxt-exchange",
            ccxt_exchange,
            "--symbol",
            symbol,
            "--funding-symbol",
            funding_symbol,
            "--timeframe",
            timeframe,
            "--limit",
            str(limit),
        ]
    )
    for strategy_family in strategy_families:
        evidence_argv.extend(["--strategy-family", strategy_family])
    if run_id is not None:
        evidence_argv.extend(["--run-id", run_id])
    evidence_argv.extend(
        _optional_evidence_source_args(
            include_defillama=include_defillama,
            include_dexscreener=include_dexscreener,
            dex_query=dex_query,
            min_tvl_usd=min_tvl_usd,
            include_dune=include_dune,
            dune_query_id=dune_query_id,
            dune_api_key=dune_api_key,
            dune_params=dune_params,
            include_thegraph=include_thegraph,
            subgraph_url=subgraph_url,
            graph_query=graph_query,
            graph_variables=graph_variables,
        )
    )

    planned_commands = [ScheduledCommand(name="evidence-run", argv=evidence_argv)]
    if include_offline_check:
        planned_commands.insert(0, ScheduledCommand(name="offline-ingest-check", argv=ingest_argv))

    return DailySchedulePlan(
        network_allowed=allow_network,
        memory_path=memory,
        planned_commands=planned_commands,
    )


def _optional_evidence_source_args(
    *,
    include_defillama: bool,
    include_dexscreener: bool,
    dex_query: str | None,
    min_tvl_usd: float | None,
    include_dune: bool,
    dune_query_id: int | None,
    dune_api_key: str | None,
    dune_params: Sequence[str],
    include_thegraph: bool,
    subgraph_url: str | None,
    graph_query: str | None,
    graph_variables: Sequence[str],
) -> Sequence[str]:
    args: list[str] = []
    if include_defillama:
        args.append("--include-defillama")
    if include_dexscreener:
        args.append("--include-dexscreener")
    if dex_query is not None:
        args.extend(["--dex-query", dex_query])
    if min_tvl_usd is not None:
        args.extend(["--min-tvl-usd", str(min_tvl_usd)])
    if include_dune:
        args.append("--include-dune")
    if dune_query_id is not None:
        args.extend(["--dune-query-id", str(dune_query_id)])
    if dune_api_key is not None:
        args.extend(["--dune-api-key", dune_api_key])
    for dune_param in dune_params:
        args.extend(["--dune-param", dune_param])
    if include_thegraph:
        args.append("--include-thegraph")
    if subgraph_url is not None:
        args.extend(["--subgraph-url", subgraph_url])
    if graph_query is not None:
        args.extend(["--graph-query", graph_query])
    for graph_variable in graph_variables:
        args.extend(["--graph-variable", graph_variable])
    return args
