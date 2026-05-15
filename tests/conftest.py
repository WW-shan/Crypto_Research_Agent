from __future__ import annotations

import pytest


@pytest.fixture
def deterministic_alpha_signal() -> dict:
    return {
        "category": "cex",
        "source": "synthetic-fixture",
        "venue": "binance",
        "asset": "ETH-USD",
        "metric": "funding_basis",
        "value": 0.042,
        "evidence": [
            "perp funding exceeded spot borrow by 420 bps annualized",
            "order book depth stayed above requested paper notional",
            "basis persisted across repeated synthetic snapshots",
        ],
        "raw": {"snapshot_id": "fixture-001"},
        "z_score": 3.4,
        "deviation": 0.042,
        "persistence_seconds": 900.0,
        "liquidity_usd": 25_000.0,
        "capital_required_usd": 500.0,
        "speed_dependency": "low",
        "rpc_dependency": "low",
        "evidence_count": 3,
        "structural_break": True,
    }
