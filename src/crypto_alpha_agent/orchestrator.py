from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

AgentState = dict[str, Any]
Route = Literal["generate_hypothesis", "code_strategy", "human_checkpoint", "proposal_finalize", "__end__"]


def _append_trace(state: AgentState, node_name: str) -> AgentState:
    next_state = dict(state)
    next_state["trace"] = [*state.get("trace", []), node_name]
    return next_state


def scan_market(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "scan_market")
    next_state.setdefault("opportunities", [])
    return next_state


def detect_anomaly(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "detect_anomaly")
    next_state["anomaly_detected"] = True
    return next_state


def generate_hypothesis(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "generate_hypothesis")
    next_state["hypothesis_attempts"] = state.get("hypothesis_attempts", 0) + 1
    next_state["hypothesis"] = "placeholder market-neutral alpha hypothesis"
    return next_state


def score_feasibility(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "score_feasibility")
    should_reject = state.get("force_rejection_once", False) and state.get("rejected_hypotheses", 0) == 0
    if should_reject:
        next_state["feasibility_status"] = "rejected"
        next_state["rejected_hypotheses"] = state.get("rejected_hypotheses", 0) + 1
    else:
        next_state["feasibility_status"] = "accepted"
        next_state.setdefault("rejected_hypotheses", state.get("rejected_hypotheses", 0))
    return next_state


def code_strategy(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "code_strategy")
    next_state["strategy_versions"] = state.get("strategy_versions", 0) + 1
    next_state["strategy_code"] = "placeholder_strategy_v%s" % next_state["strategy_versions"]
    return next_state


def backtest(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "backtest")
    next_state["backtest_result"] = {"status": "placeholder", "passed": True}
    return next_state


def critique(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "critique")
    should_revise = state.get("force_critique_once", False) and state.get("critique_revisions", 0) == 0
    if should_revise:
        next_state["critique_status"] = "revise"
        next_state["critique_revisions"] = state.get("critique_revisions", 0) + 1
    else:
        next_state["critique_status"] = "approved"
        next_state.setdefault("critique_revisions", state.get("critique_revisions", 0))
    return next_state


def update_memory(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "update_memory")
    next_state["memory_updated"] = True
    return next_state


def risk_guard(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "risk_guard")
    next_state["risk_status"] = "requires_human" if state.get("require_human_approval") else "cleared"
    return next_state


def human_checkpoint(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "human_checkpoint")
    approval_required = state.get("require_human_approval", False) and not state.get("human_approved", False)
    next_state["approval_required"] = approval_required
    if approval_required:
        next_state["paused_at"] = "human_checkpoint"
    return next_state


def proposal_finalize(state: AgentState) -> AgentState:
    next_state = _append_trace(state, "proposal_finalize")
    next_state["proposal_finalized"] = True
    return next_state


def _route_feasibility(state: AgentState) -> Route:
    if state.get("feasibility_status") == "rejected":
        return "generate_hypothesis"
    return "code_strategy"


def _route_critique(state: AgentState) -> Route:
    if state.get("critique_status") == "revise":
        return "code_strategy"
    return "update_memory"


def _route_human_checkpoint(state: AgentState) -> Route:
    if state.get("approval_required"):
        return "__end__"
    return "proposal_finalize"


def thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    from crypto_alpha_agent.checkpointing import create_thread_config

    return create_thread_config(thread_id)


def build_checkpointed_graph(**kwargs: Any):
    from crypto_alpha_agent.checkpointing import build_checkpointed_graph as _build_checkpointed_graph

    return _build_checkpointed_graph(**kwargs)


def build_graph(
    *,
    checkpointer: Any | None = None,
    interrupt_before: Literal["*"] | Sequence[str] | None = None,
    interrupt_after: Literal["*"] | Sequence[str] | None = None,
    debug: bool = False,
):
    workflow = StateGraph(dict)
    workflow.add_node("scan_market", scan_market)
    workflow.add_node("detect_anomaly", detect_anomaly)
    workflow.add_node("generate_hypothesis", generate_hypothesis)
    workflow.add_node("score_feasibility", score_feasibility)
    workflow.add_node("code_strategy", code_strategy)
    workflow.add_node("backtest", backtest)
    workflow.add_node("critique", critique)
    workflow.add_node("update_memory", update_memory)
    workflow.add_node("risk_guard", risk_guard)
    workflow.add_node("human_checkpoint", human_checkpoint)
    workflow.add_node("proposal_finalize", proposal_finalize)

    workflow.add_edge(START, "scan_market")
    workflow.add_edge("scan_market", "detect_anomaly")
    workflow.add_edge("detect_anomaly", "generate_hypothesis")
    workflow.add_edge("generate_hypothesis", "score_feasibility")
    workflow.add_conditional_edges(
        "score_feasibility",
        _route_feasibility,
        {"generate_hypothesis": "generate_hypothesis", "code_strategy": "code_strategy"},
    )
    workflow.add_edge("code_strategy", "backtest")
    workflow.add_edge("backtest", "critique")
    workflow.add_conditional_edges(
        "critique",
        _route_critique,
        {"code_strategy": "code_strategy", "update_memory": "update_memory"},
    )
    workflow.add_edge("update_memory", "risk_guard")
    workflow.add_edge("risk_guard", "human_checkpoint")
    workflow.add_conditional_edges(
        "human_checkpoint",
        _route_human_checkpoint,
        {"proposal_finalize": "proposal_finalize", "__end__": END},
    )
    workflow.add_edge("proposal_finalize", END)

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after,
        debug=debug,
    )


def run_deterministic_research_loop(
    *,
    signal_fixtures: Sequence[dict[str, Any]],
    memory_path: str | Path,
    paper_cash_usd: float = 10_000.0,
    current_capital_usd: float | None = None,
) -> AgentState:
    from crypto_alpha_agent.agents.anomaly import AnomalyDetector
    from crypto_alpha_agent.agents.coder import StrategyCoder
    from crypto_alpha_agent.agents.hypothesis import HypothesisGenerator
    from crypto_alpha_agent.agents.scanner import MarketScanner
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult
    from crypto_alpha_agent.execution.paper import PaperAccount, PaperOrder
    from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
    from crypto_alpha_agent.risk.feasibility import score_feasibility as calculate_feasibility
    from crypto_alpha_agent.risk.guardian import PermissionScope, RiskContext, RiskGuardian, RiskPolicy

    trace: list[str] = []
    scanner = MarketScanner(providers=[lambda: signal_fixtures])

    trace.append("scan_market")
    signals = scanner.scan()
    if not signals:
        raise ValueError("deterministic loop requires at least one signal fixture")

    trace.append("detect_anomaly")
    anomalies = AnomalyDetector().rank(signals)
    executable_anomaly = next((anomaly for anomaly in anomalies if anomaly.executable), anomalies[0])
    signal = executable_anomaly.signal

    trace.append("generate_hypothesis")
    hypothesis = HypothesisGenerator().generate([executable_anomaly])[0]

    expected_net_pnl_usd = float(signal.raw.get("expected_net_pnl_usd", 60.0))
    max_downside_usd = float(signal.raw.get("max_downside_usd", 30.0))
    capital_required_usd = signal.capital_required_usd or min(paper_cash_usd, 500.0)
    available_capital_usd = current_capital_usd if current_capital_usd is not None else paper_cash_usd

    trace.append("score_feasibility")
    feasibility = calculate_feasibility(
        capital_required_usd=capital_required_usd,
        current_capital_usd=available_capital_usd,
        expected_net_pnl_usd=expected_net_pnl_usd,
        max_downside_usd=max_downside_usd,
        repeatable=True,
        speed_dependency=signal.speed_dependency,
        rpc_dependency=signal.rpc_dependency,
        action_mode="paper",
        max_allowed_downside_usd=max_downside_usd * 2.0,
    )

    trace.append("code_strategy")
    strategy = StrategyCoder().emit("execution_proposal")

    trace.append("backtest")
    backtest_result = BacktestResult(
        net_return=0.12,
        max_drawdown=-0.04,
        win_rate=0.8,
        trade_count=5,
        average_holding_time=2.0,
        fee_adjusted_expectancy=0.03,
        slippage_adjusted_expectancy=0.028,
    )

    trace.append("critique")
    critique_decision = reflect_strategy(
        hypothesis=hypothesis,
        backtest=backtest_result,
        feasibility=feasibility,
    )

    record_id = f"{signal.source}:{signal.asset}:{signal.metric}"
    store = MemoryStore(memory_path)
    memory_record = MemoryRecord(
        record_id=record_id,
        opportunity={
            "source": signal.source,
            "venue": signal.venue,
            "asset": signal.asset,
            "edge_type": signal.metric,
            "evidence": list(signal.evidence),
            "confidence": min(1.0, max(0.0, executable_anomaly.score / 100.0)),
            "capital_required_usd": capital_required_usd,
            "expected_net_pnl_usd": expected_net_pnl_usd,
            "downside_usd": max_downside_usd,
            "speed_dependency": signal.speed_dependency,
            "rpc_dependency": signal.rpc_dependency,
        },
        hypothesis=hypothesis.model_dump(),
        score=feasibility.model_dump(),
        rejected_reasons=list(critique_decision.rejection_reasons),
        backtest_artifacts={
            "engine": "deterministic_fixture",
            "metrics": backtest_result.model_dump(),
        },
        tags=[signal.asset.lower(), signal.metric, critique_decision.outcome],
    )

    trace.append("update_memory")
    stored_record = store.upsert(memory_record)

    trace.append("risk_guard")
    guardian = RiskGuardian(
        RiskPolicy(
            max_capital_per_opportunity_usd=paper_cash_usd,
            max_daily_loss_usd=max_downside_usd * 4.0,
            max_consecutive_failures=3,
            allowed_venues=[signal.venue or "synthetic"],
        )
    )
    risk_decision = guardian.evaluate(
        RiskContext(
            opportunity_id=record_id,
            execution_mode="paper",
            venue=signal.venue or "synthetic",
            capital_required_usd=capital_required_usd,
            daily_realized_pnl_usd=0.0,
            consecutive_failures=0,
            permission_scope=PermissionScope(
                venue=signal.venue or "synthetic",
                api_permissions=["read", "paper"],
                wallet_permissions=["paper-only"],
            ),
        )
    )

    paper_trade: dict[str, Any] | None = None
    if risk_decision.execution_allowed:
        trace.append("paper_execute")
        account = PaperAccount(cash=paper_cash_usd)
        entry_price = float(signal.raw.get("entry_price", 100.0))
        exit_price = float(signal.raw.get("exit_price", 108.0))
        quantity = capital_required_usd / entry_price
        buy = account.execute_order(
            PaperOrder(
                symbol=signal.asset,
                side="buy",
                quantity=quantity,
                reference_price=entry_price,
                fee_rate=0.001,
                slippage_bps=5.0,
                latency_ms=10.0,
            )
        )
        sell = account.execute_order(
            PaperOrder(
                symbol=signal.asset,
                side="sell",
                quantity=quantity,
                reference_price=exit_price,
                fee_rate=0.001,
                slippage_bps=5.0,
                latency_ms=10.0,
            )
        )
        paper_trade = {
            "status": "closed",
            "risk_decision": risk_decision.model_dump(),
            "buy": buy.model_dump(),
            "sell": sell.model_dump(),
        }
        stored_record = store.upsert(stored_record.model_copy(update={"paper_trade_outcome": paper_trade}))

    return {
        "trace": trace,
        "signals": [signal.model_dump() for signal in signals],
        "anomalies": [anomaly.model_dump() for anomaly in anomalies],
        "hypothesis": hypothesis.model_dump(),
        "feasibility": feasibility.model_dump(),
        "strategy": strategy.model_dump(),
        "backtest": backtest_result.model_dump(),
        "critique": critique_decision.model_dump(),
        "memory_record_id": stored_record.record_id,
        "risk_decision": risk_decision.model_dump(),
        "paper_trade": paper_trade,
    }
