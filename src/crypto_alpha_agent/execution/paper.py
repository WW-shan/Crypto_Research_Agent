from __future__ import annotations

from typing import Annotated, Literal

from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

OrderSide = Literal["buy", "sell"]

PositiveFiniteFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class PaperOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    side: OrderSide
    quantity: PositiveFiniteFloat
    reference_price: PositiveFiniteFloat
    fee_rate: NonNegativeFiniteFloat = 0.0
    slippage_rate: NonNegativeFiniteFloat | None = None
    slippage_bps: NonNegativeFiniteFloat | None = None
    latency_ms: NonNegativeFiniteFloat = 0.0

    @model_validator(mode="after")
    def _validate_slippage_units(self) -> PaperOrder:
        if self.slippage_rate is not None and self.slippage_bps is not None:
            raise ValueError("only one slippage unit may be provided")
        return self

    @property
    def effective_slippage_rate(self) -> float:
        if self.slippage_rate is not None:
            return self.slippage_rate
        if self.slippage_bps is not None:
            return self.slippage_bps / 10_000.0
        return 0.0


class PaperFill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: OrderSide
    quantity: PositiveFiniteFloat
    reference_price: PositiveFiniteFloat
    fill_price: PositiveFiniteFloat
    gross_value: NonNegativeFiniteFloat
    fee: NonNegativeFiniteFloat
    slippage_rate: NonNegativeFiniteFloat
    latency_ms: NonNegativeFiniteFloat
    external_order_id: None = None


class PaperTradeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fill: PaperFill
    cash: NonNegativeFiniteFloat
    inventory: dict[str, NonNegativeFiniteFloat]
    capital_used: NonNegativeFiniteFloat
    realized_gross_pnl: float = Field(strict=True, allow_inf_nan=False)
    realized_net_pnl: float = Field(strict=True, allow_inf_nan=False)
    touched_real_capital: bool = False


class PaperMarkToMarket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash: NonNegativeFiniteFloat
    inventory_value: NonNegativeFiniteFloat
    equity: NonNegativeFiniteFloat
    realized_gross_pnl: float = Field(strict=True, allow_inf_nan=False)
    realized_net_pnl: float = Field(strict=True, allow_inf_nan=False)
    unrealized_gross_pnl: float = Field(strict=True, allow_inf_nan=False)
    touched_real_capital: bool = False


class PaperAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    cash: NonNegativeFiniteFloat
    inventory: dict[str, NonNegativeFiniteFloat] = Field(default_factory=dict)
    realized_gross_pnl: float = Field(default=0.0, strict=True, allow_inf_nan=False)
    realized_net_pnl: float = Field(default=0.0, strict=True, allow_inf_nan=False)
    touched_real_capital: bool = False
    _average_entry_price: dict[str, float] = PrivateAttr(default_factory=dict)
    _entry_fees: dict[str, float] = PrivateAttr(default_factory=dict)
    _capital_used: dict[str, float] = PrivateAttr(default_factory=dict)

    def execute_order(self, order: PaperOrder) -> PaperTradeResult:
        fill_price = self._fill_price(order)
        gross_value = order.quantity * fill_price
        fee = gross_value * order.fee_rate

        if order.side == "buy":
            result = self._execute_buy(order, fill_price, gross_value, fee)
        else:
            result = self._execute_sell(order, fill_price, gross_value, fee)

        fill = PaperFill(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            reference_price=order.reference_price,
            fill_price=fill_price,
            gross_value=gross_value,
            fee=fee,
            slippage_rate=order.effective_slippage_rate,
            latency_ms=order.latency_ms,
        )
        return PaperTradeResult(
            fill=fill,
            cash=self.cash,
            inventory=dict(self.inventory),
            capital_used=result["capital_used"],
            realized_gross_pnl=result["realized_gross_pnl"],
            realized_net_pnl=result["realized_net_pnl"],
            touched_real_capital=self.touched_real_capital,
        )

    def mark_to_market(self, reference_prices: dict[str, float]) -> PaperMarkToMarket:
        inventory_value = 0.0
        unrealized_gross_pnl = 0.0

        for symbol, quantity in self.inventory.items():
            if quantity <= 0:
                continue
            if symbol not in reference_prices:
                raise ValueError(f"missing mark price for {symbol}")
            mark_price = _validate_runtime_price(symbol, reference_prices[symbol])
            inventory_value += quantity * mark_price
            entry_price = self._average_entry_price.get(symbol, 0.0)
            unrealized_gross_pnl += (mark_price - entry_price) * quantity

        return PaperMarkToMarket(
            cash=self.cash,
            inventory_value=inventory_value,
            equity=self.cash + inventory_value,
            realized_gross_pnl=self.realized_gross_pnl,
            realized_net_pnl=self.realized_net_pnl,
            unrealized_gross_pnl=unrealized_gross_pnl,
            touched_real_capital=self.touched_real_capital,
        )

    def _execute_buy(
        self,
        order: PaperOrder,
        fill_price: float,
        gross_value: float,
        fee: float,
    ) -> dict[str, float]:
        total_cost = gross_value + fee
        if total_cost > self.cash:
            raise ValueError("insufficient paper cash")

        previous_quantity = self.inventory.get(order.symbol, 0.0)
        new_quantity = previous_quantity + order.quantity
        previous_cost = self._average_entry_price.get(order.symbol, 0.0) * previous_quantity
        self._average_entry_price[order.symbol] = (previous_cost + gross_value) / new_quantity
        self._entry_fees[order.symbol] = self._entry_fees.get(order.symbol, 0.0) + fee
        self._capital_used[order.symbol] = self._capital_used.get(order.symbol, 0.0) + total_cost

        self.cash -= total_cost
        self.inventory[order.symbol] = new_quantity

        return {
            "capital_used": total_cost,
            "realized_gross_pnl": 0.0,
            "realized_net_pnl": 0.0,
        }

    def _execute_sell(
        self,
        order: PaperOrder,
        fill_price: float,
        gross_value: float,
        fee: float,
    ) -> dict[str, float]:
        current_quantity = self.inventory.get(order.symbol, 0.0)
        if order.quantity > current_quantity:
            raise ValueError("insufficient paper inventory")

        average_entry = self._average_entry_price.get(order.symbol, 0.0)
        entry_fee = self._entry_fees.get(order.symbol, 0.0)
        capital_used = self._capital_used.get(order.symbol, 0.0)
        fraction_closed = order.quantity / current_quantity
        allocated_entry_fee = entry_fee * fraction_closed
        allocated_capital_used = capital_used * fraction_closed

        realized_gross_pnl = (fill_price - average_entry) * order.quantity
        realized_net_pnl = realized_gross_pnl - allocated_entry_fee - fee
        remaining_quantity = current_quantity - order.quantity

        self.cash += gross_value - fee
        self.realized_gross_pnl += realized_gross_pnl
        self.realized_net_pnl += realized_net_pnl

        if remaining_quantity == 0:
            self.inventory[order.symbol] = 0.0
            self._average_entry_price.pop(order.symbol, None)
            self._entry_fees.pop(order.symbol, None)
            self._capital_used.pop(order.symbol, None)
        else:
            self.inventory[order.symbol] = remaining_quantity
            self._entry_fees[order.symbol] = entry_fee - allocated_entry_fee
            self._capital_used[order.symbol] = capital_used - allocated_capital_used

        return {
            "capital_used": allocated_capital_used,
            "realized_gross_pnl": realized_gross_pnl,
            "realized_net_pnl": realized_net_pnl,
        }

    @staticmethod
    def _fill_price(order: PaperOrder) -> float:
        slippage_multiplier = 1.0 + order.effective_slippage_rate
        if order.side == "sell":
            slippage_multiplier = 1.0 - order.effective_slippage_rate
        fill_price = order.reference_price * slippage_multiplier
        if fill_price <= 0:
            raise ValueError("paper fill price must be positive")
        return fill_price


def paper_round_trip_to_backtest_result(
    entry_fill: PaperFill,
    exit_fill: PaperFill,
    holding_time: float,
) -> BacktestResult:
    if entry_fill.side != "buy" or exit_fill.side != "sell":
        raise ValueError("paper round trip requires buy entry and sell exit fills")
    if entry_fill.symbol != exit_fill.symbol:
        raise ValueError("paper round trip fills must use the same symbol")
    if entry_fill.quantity != exit_fill.quantity:
        raise ValueError("paper round trip fills must use the same quantity")
    if holding_time < 0:
        raise ValueError("holding_time must be non-negative")

    entry_fee_rate = entry_fill.fee / entry_fill.gross_value
    exit_fee_rate = exit_fill.fee / exit_fill.gross_value
    gross_return = (exit_fill.reference_price - entry_fill.reference_price) / entry_fill.reference_price
    net_return = (
        (exit_fill.gross_value - exit_fill.fee)
        / (entry_fill.gross_value + entry_fill.fee)
        - 1.0
    )

    return BacktestResult(
        net_return=float(net_return),
        max_drawdown=0.0,
        win_rate=float(gross_return > 0.0),
        trade_count=1,
        average_holding_time=float(holding_time),
        fee_adjusted_expectancy=float(gross_return - entry_fee_rate - exit_fee_rate),
        slippage_adjusted_expectancy=float(
            gross_return - entry_fill.slippage_rate - exit_fill.slippage_rate
        ),
    )


def _validate_runtime_price(symbol: str, price: float) -> float:
    model = _RuntimePrice(symbol=symbol, price=price)
    return model.price


class _RuntimePrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    price: PositiveFiniteFloat
