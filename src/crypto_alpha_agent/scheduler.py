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
    source: str | None = None,
    symbol: str | None = None,
    timeframe: str = "1h",
    year: int | None = None,
    month: int | None = None,
) -> DailySchedulePlan:
    if not math.isfinite(current_capital_usd) or current_capital_usd <= 0:
        raise ValueError("current_capital_usd must be finite and positive")
    if _has_network_ingestion_intent(source=source, symbol=symbol, year=year, month=month) and not allow_network:
        raise ValueError("--allow-network is required when scheduling network ingestion")

    db = str(db_path)
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
    research_argv = [
        "crypto-alpha-agent",
        "research-loop",
        "--db",
        db,
        "--current-capital-usd",
        capital,
    ]
    if include_validation:
        research_argv.append("--include-validation")
    research_argv.extend(["--report-out", report])
    if run_id is not None:
        research_argv.extend(["--run-id", run_id])
    research_argv.extend(_network_research_loop_args(source, symbol, timeframe, year, month, allow_network))

    return DailySchedulePlan(
        network_allowed=allow_network,
        memory_path=str(memory_path) if memory_path is not None else None,
        planned_commands=[
            ScheduledCommand(name="offline-ingest-check", argv=ingest_argv),
            ScheduledCommand(name="research-loop", argv=research_argv),
        ],
    )


def _has_network_ingestion_intent(
    *,
    source: str | None,
    symbol: str | None,
    year: int | None,
    month: int | None,
) -> bool:
    return bool(source == "binance-public" or symbol is not None or year is not None or month is not None)


def _network_research_loop_args(
    source: str | None,
    symbol: str | None,
    timeframe: str,
    year: int | None,
    month: int | None,
    allow_network: bool,
) -> Sequence[str]:
    if not allow_network:
        return []

    args = ["--allow-network"]
    if source is not None:
        args.extend(["--source", source])
    if symbol is not None:
        args.extend(["--symbol", symbol])
    args.extend(["--timeframe", timeframe])
    if year is not None:
        args.extend(["--year", str(year)])
    if month is not None:
        args.extend(["--month", str(month)])
    return args
