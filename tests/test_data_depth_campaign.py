from __future__ import annotations

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.pipeline.data_depth_campaign import (
    CampaignMonth,
    DataDepthCampaignSpec,
    expand_campaign_months,
)


def test_expand_campaign_months_is_inclusive_and_chronological():
    months = expand_campaign_months(
        CampaignMonth(year=2026, month=1),
        CampaignMonth(year=2026, month=3),
    )

    assert [(month.year, month.month) for month in months] == [
        (2026, 1),
        (2026, 2),
        (2026, 3),
    ]


def test_campaign_spec_normalizes_symbols_and_preserves_safety_flags():
    spec = DataDepthCampaignSpec(
        symbols=["btcusdt", "ETH/USDT", "ethusdt"],
        timeframe="1h",
        market="um-futures",
        start=CampaignMonth(year=2026, month=1),
        end=CampaignMonth(year=2026, month=3),
        min_unique_months=3,
    )

    assert spec.symbols == ("BTC/USDT", "ETH/USDT")
    assert spec.uses_real_capital is False
    assert spec.live_order_routing is False


def test_campaign_spec_rejects_empty_symbols_and_reversed_ranges():
    with pytest.raises(ValueError, match="symbols"):
        DataDepthCampaignSpec(
            symbols=[],
            timeframe="1h",
            market="um-futures",
            start=CampaignMonth(year=2026, month=1),
            end=CampaignMonth(year=2026, month=3),
            min_unique_months=3,
        )

    with pytest.raises(ValueError, match="end.*before.*start"):
        DataDepthCampaignSpec(
            symbols=["BTC/USDT"],
            timeframe="1h",
            market="um-futures",
            start=CampaignMonth(year=2026, month=4),
            end=CampaignMonth(year=2026, month=3),
            min_unique_months=3,
        )


def test_campaign_models_are_strict():
    with pytest.raises(ValidationError):
        CampaignMonth(year="2026", month=1)

    with pytest.raises(ValidationError):
        CampaignMonth(year=2026, month=1, unexpected="field")

    with pytest.raises(ValidationError):
        DataDepthCampaignSpec(
            symbols=["BTC/USDT"],
            timeframe="1h",
            market="spot",
            start=CampaignMonth(year=2026, month=1),
            end=CampaignMonth(year=2026, month=3),
            min_unique_months=3,
        )
