from __future__ import annotations

from collections.abc import Sequence
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
    return {"configurable": {"thread_id": thread_id}}


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
