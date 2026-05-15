from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.tools.sandbox import validate_python_code

StrategyCodeKind = Literal[
    "backtest_script",
    "data_transform",
    "indicator_definition",
    "execution_proposal",
]


class StrategyCode(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: StrategyCodeKind
    source: str = Field(min_length=1)

    _allowed_kinds: ClassVar[tuple[StrategyCodeKind, ...]] = (
        "backtest_script",
        "data_transform",
        "indicator_definition",
        "execution_proposal",
    )

    @classmethod
    def allowed_kinds(cls) -> tuple[StrategyCodeKind, ...]:
        return cls._allowed_kinds


class StrategyCoder:
    def emit(self, kind: StrategyCodeKind | str) -> StrategyCode:
        if kind not in StrategyCode.allowed_kinds():
            raise ValueError(f"Unsupported strategy code kind: {kind}")

        source = _TEMPLATES[kind]
        validate_python_code(source)
        return StrategyCode(kind=kind, source=source)


_TEMPLATES: dict[StrategyCodeKind, str] = {
    "backtest_script": """
def run_backtest(prices, threshold=0.02):
    trades = []
    if len(prices) < 2:
        return {"trades": trades, "net_return": 0.0}

    entry_price = prices[0]
    for index, price in enumerate(prices[1:], start=1):
        move = (price - entry_price) / entry_price
        if abs(move) >= threshold:
            trades.append({"index": index, "return": move})
            entry_price = price

    net_return = sum(trade["return"] for trade in trades)
    return {"trades": trades, "net_return": net_return}
""",
    "data_transform": """
def normalize_prices(rows):
    transformed = []
    for row in rows:
        transformed.append(
            {
                "timestamp": row["timestamp"],
                "price": float(row["price"]),
            }
        )
    return transformed
""",
    "indicator_definition": """
def rolling_mean(values, window):
    if window <= 0:
        return []

    means = []
    for index in range(len(values)):
        start = max(0, index - window + 1)
        sample = values[start : index + 1]
        means.append(sum(sample) / len(sample))
    return means
""",
    "execution_proposal": """
def propose_execution(signal, max_capital_usd):
    confidence = float(signal.get("confidence", 0.0))
    capital_required = float(signal.get("capital_required_usd", 0.0))
    allowed_capital = min(capital_required, max_capital_usd)
    should_paper_trade = confidence >= 0.7 and allowed_capital > 0

    return {
        "mode": "paper" if should_paper_trade else "research_only",
        "capital_usd": allowed_capital if should_paper_trade else 0.0,
        "reason": "confidence and budget gate checked",
    }
""",
}
