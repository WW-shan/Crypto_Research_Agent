from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.execution.hummingbot_adapter import (
    AdapterPlan,
    ExecutionIntent,
    _assert_paper_execution_allowed,
)
from crypto_alpha_agent.risk.guardian import RiskDecision


class FreqtradeAdapter(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    exchange_name: str = Field(default="binance", min_length=1)

    def build_plan(self, intent: ExecutionIntent, risk_decision: RiskDecision) -> AdapterPlan:
        _assert_paper_execution_allowed(intent, risk_decision)
        return AdapterPlan(
            engine="freqtrade",
            mode="paper",
            opportunity_id=intent.opportunity_id,
            payload={
                "dry_run": True,
                "exchange": {
                    "name": self.exchange_name,
                    "pair_whitelist": [intent.symbol],
                },
                "order": {
                    "pair": intent.symbol,
                    "side": intent.side,
                    "order_type": "limit",
                    "amount": intent.quantity,
                    "rate": intent.reference_price,
                    "stake_amount": intent.notional_usd,
                },
            },
        )
