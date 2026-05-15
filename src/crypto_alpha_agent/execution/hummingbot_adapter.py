from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.config import ActionMode
from crypto_alpha_agent.risk.guardian import RiskDecision

AdapterEngine = Literal["hummingbot", "freqtrade"]
AdapterMode = Literal["paper"]
AdapterOrderSide = Literal["buy", "sell"]

PositiveFiniteFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]


class ExecutionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    opportunity_id: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    side: AdapterOrderSide
    quantity: PositiveFiniteFloat
    reference_price: PositiveFiniteFloat
    max_capital_usd: PositiveFiniteFloat
    execution_mode: ActionMode = "paper"

    @property
    def notional_usd(self) -> float:
        return self.quantity * self.reference_price


class AdapterPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    engine: AdapterEngine
    mode: AdapterMode
    opportunity_id: str = Field(min_length=1)
    payload: dict[str, Any]


class HummingbotAdapter(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    connector: str = Field(default="binance_paper_trade", min_length=1)

    def build_plan(self, intent: ExecutionIntent, risk_decision: RiskDecision) -> AdapterPlan:
        _assert_paper_execution_allowed(intent, risk_decision)
        return AdapterPlan(
            engine="hummingbot",
            mode="paper",
            opportunity_id=intent.opportunity_id,
            payload={
                "connector": self.connector,
                "market": intent.symbol,
                "paper_trade": True,
                "order": {
                    "side": intent.side,
                    "type": "limit",
                    "amount": intent.quantity,
                    "price": intent.reference_price,
                    "notional_usd": intent.notional_usd,
                },
            },
        )


def _assert_paper_execution_allowed(intent: ExecutionIntent, risk_decision: RiskDecision) -> None:
    risk_decision.assert_can_execute()
    if risk_decision.opportunity_id != intent.opportunity_id:
        raise PermissionError("risk decision does not match execution intent")
    if risk_decision.execution_mode != intent.execution_mode:
        raise PermissionError("risk decision mode does not match execution intent")
    if intent.execution_mode != "paper" or risk_decision.live_execution_allowed:
        raise PermissionError("live execution is not implemented by this adapter boundary")
