from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.data.models import FundingRateRecord
from crypto_alpha_agent.data.store import ResearchDataStore


class FundingExtremityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str
    symbol: str | None
    venue: str | None
    sample_count: int
    extreme_count: int
    positive_extreme_count: int
    negative_extreme_count: int
    mean_funding_rate: float
    max_abs_funding_rate: float
    threshold_abs: float
    approved: bool
    blocked_reasons: list[str]


def _require_existing_file(db_path: str | Path) -> Path:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"database path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"database path is not a file: {path}")
    return path


def _require_positive_int(name: str, value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def validate_funding_extremes(
    db_path: str | Path,
    *,
    symbol: str | None = None,
    venue: str | None = None,
    source: str | None = None,
    threshold_abs: float = 0.0005,
    min_samples: int = 10,
    min_extremes: int = 2,
) -> FundingExtremityResult:
    if not math.isfinite(threshold_abs) or threshold_abs <= 0:
        raise ValueError("threshold_abs must be finite and greater than 0")
    _require_positive_int("min_samples", min_samples)
    _require_positive_int("min_extremes", min_extremes)

    store = ResearchDataStore(_require_existing_file(db_path))
    records = store.load_records(record_type="funding_rate", source=source)

    funding_rates: list[float] = []
    positive_extreme_count = 0
    negative_extreme_count = 0

    for record in records:
        funding = FundingRateRecord.model_validate_json(json.dumps(record.payload))
        if source is not None and (funding.source != record.source or funding.source != source):
            continue
        if symbol is not None and funding.symbol != symbol:
            continue
        if venue is not None and funding.venue != venue:
            continue

        funding_rate = float(funding.funding_rate)
        if not math.isfinite(funding_rate):
            raise ValueError("funding_rate must be finite")
        funding_rates.append(funding_rate)
        if abs(funding_rate) >= threshold_abs:
            if funding_rate >= 0:
                positive_extreme_count += 1
            else:
                negative_extreme_count += 1

    sample_count = len(funding_rates)
    extreme_count = positive_extreme_count + negative_extreme_count
    mean_funding_rate = math.fsum(funding_rates) / sample_count if funding_rates else 0.0
    max_abs_funding_rate = max((abs(rate) for rate in funding_rates), default=0.0)
    blocked_reasons = _blocked_reasons(
        sample_count=sample_count,
        extreme_count=extreme_count,
        min_samples=min_samples,
        min_extremes=min_extremes,
    )

    return FundingExtremityResult(
        strategy_family="funding_extremity",
        symbol=symbol,
        venue=venue,
        sample_count=sample_count,
        extreme_count=extreme_count,
        positive_extreme_count=positive_extreme_count,
        negative_extreme_count=negative_extreme_count,
        mean_funding_rate=float(mean_funding_rate),
        max_abs_funding_rate=float(max_abs_funding_rate),
        threshold_abs=float(threshold_abs),
        approved=not blocked_reasons,
        blocked_reasons=blocked_reasons,
    )


def _blocked_reasons(
    *,
    sample_count: int,
    extreme_count: int,
    min_samples: int,
    min_extremes: int,
) -> list[str]:
    reasons: list[str] = []
    if sample_count < min_samples:
        reasons.append("insufficient_samples")
    if extreme_count == 0:
        reasons.append("no_extreme_funding")
    elif extreme_count < min_extremes:
        reasons.append("insufficient_extremes")
    return reasons
