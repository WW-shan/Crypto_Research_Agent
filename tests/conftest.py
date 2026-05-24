from __future__ import annotations

import json
from typing import Any

import pytest


class _RequiredLLMTestLLM:
    def __init__(self) -> None:
        self.tasks: list[Any] = []

    def __call__(self, task: Any) -> str:
        self.tasks.append(task)
        task_type = type(task).__name__
        if task_type == "LLMHealthCheckTask":
            return json.dumps(
                {
                    "status": "ok",
                    "schema_name": "LLMHealthCheckResult",
                    "capabilities": ["json_schema", "research_only"],
                    "uses_real_capital": False,
                    "live_order_routing": False,
                }
            )
        if task_type == "ResearchTask":
            counts = task.context.get("counts", {})
            has_evidence = any(
                int(counts.get(key, 0) or 0) > 0
                for key in (
                    "signals",
                    "anomalies",
                    "hypotheses",
                    "weak_signals",
                    "blocked_hypotheses",
                    "validation_summaries",
                )
            )
            if not has_evidence:
                return "{}"
            return json.dumps(
                {
                    "proposal_id": "test-llm-proposal",
                    "thesis": "Public funding data may reveal a bounded research setup.",
                    "hypothesis": "A public funding extremity with confirmation may be worth validation.",
                    "assumptions": ["Only public market data is used."],
                    "evidence": ["Synthetic test runtime supplied structured JSON."],
                    "disconfirmation": ["Reject if deterministic validation is not supportive."],
                    "data_needed": ["market_candle", "funding_rate"],
                    "capital_required_usd": 0.0,
                    "speed_dependency": "low",
                    "rpc_dependency": "none",
                    "action_mode": "research_only",
                }
            )
        if task_type == "ExperimentPlannerTask":
            return json.dumps(
                {
                    "strategy_family": "funding_extremity_price_confirmation",
                    "parameter_changes": {
                        "experiment_type": "collect_more_walk_forward_data",
                        "threshold_abs": 0.001,
                        "hold_bars": 2,
                        "min_walk_forward_splits": 3,
                    },
                    "evidence_refs": ["gap:collect_more_walk_forward_data"],
                    "why_it_might_improve_edge": "More public history can test whether the signal survives costs.",
                    "expected_edge_mechanism": "Larger public funding extremes may retain fee-adjusted edge.",
                    "disconfirmation_tests": ["Reject if deterministic validation remains weak."],
                    "stop_conditions": ["Stop after repeated blocked validation runs."],
                    "required_data_fields": ["market_candle", "funding_rate"],
                    "selected_validator": "funding_price_confirmation",
                    "allowed_data_sources": ["market_candle", "funding_rate"],
                    "uses_real_capital": False,
                    "live_order_routing": False,
                }
            )
        if task_type == "EvidenceReportSummaryTask":
            return json.dumps(
                {
                    "report_type": task.report_type,
                    "summary": "Deterministic evidence remains the source of truth for this report.",
                    "metric_refs": ["deterministic_report"],
                    "caveats": ["Research-only summary from structured test runtime."],
                    "uses_real_capital": False,
                    "live_order_routing": False,
                }
            )
        if task_type == "LLMJudgementTask":
            evidence_refs = list(getattr(task, "evidence_refs", []) or ["runtime:test"])
            schema_name = str(getattr(task, "schema_name", "RuntimeCommandJudgement"))
            if schema_name == "SourceResearchJudgement":
                return json.dumps(
                    {
                        "schema_name": "SourceResearchJudgement",
                        "decision": "add_data",
                        "rationale": "Source health needs another research-only check before promotion.",
                        "evidence_refs": evidence_refs,
                        "next_actions": ["Run another source probe with nonzero typed rows."],
                        "uses_real_capital": False,
                        "live_order_routing": False,
                    }
                )
            if schema_name == "DataReadinessJudgement":
                facts = getattr(task, "facts", {}) or {}
                summary = facts.get("ingestion_summary", {}) if isinstance(facts, dict) else {}
                mode = summary.get("mode") if isinstance(summary, dict) else None
                missing_fields = [] if mode == "network_declared" else ["market_candle", "funding_rate"]
                return json.dumps(
                    {
                        "schema_name": "DataReadinessJudgement",
                        "decision": "research_ready" if not missing_fields else "add_data",
                        "rationale": "Ingestion facts were reviewed by the structured test runtime.",
                        "evidence_refs": evidence_refs,
                        "missing_fields": missing_fields,
                        "next_actions": ["Continue with research-only validation."],
                        "uses_real_capital": False,
                        "live_order_routing": False,
                    }
                )
            return json.dumps(
                {
                    "schema_name": schema_name,
                    "decision": "add_data",
                    "rationale": "Command facts were reviewed by the structured test runtime.",
                    "evidence_refs": evidence_refs,
                    "next_actions": ["Continue with research-only validation."],
                    "uses_real_capital": False,
                    "live_order_routing": False,
                }
            )
        return "{}"


class _RequiredLLMTestRuntime:
    def __init__(self, *, role: str) -> None:
        self.role = role
        self.llm = _RequiredLLMTestLLM()
        self.health_commands: list[str] = []

    def health_check(self, *, command: str):
        from crypto_alpha_agent.llm.runtime import LLMHealthCheckResult

        self.health_commands.append(command)
        return LLMHealthCheckResult(
            status="ok",
            schema_name="LLMHealthCheckResult",
            capabilities=["json_schema", "research_only"],
            uses_real_capital=False,
            live_order_routing=False,
        )

    def structured_call(self, task: Any, output_model: type[Any]) -> Any:
        from crypto_alpha_agent.llm.runtime import parse_structured_llm_json

        return parse_structured_llm_json(self.llm(task), output_model)

    def metadata(self) -> dict[str, Any]:
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": self.role,
            "llm_provider_verified": True,
            "llm_model": "test-real-model",
        }


@pytest.fixture(autouse=True)
def required_real_llm_runtime_for_cli_tests(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    if request.node.get_closest_marker("llm_integration"):
        return

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="research": _RequiredLLMTestRuntime(role=role),
    )


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
