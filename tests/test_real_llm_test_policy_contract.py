from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


def test_real_llm_policy_markers_are_registered() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "integration: tests that call configured external services" in pyproject
    assert "llm_integration: tests that call the configured real LLM provider" in pyproject
    assert "--strict-markers" in pyproject


@dataclass(frozen=True)
class FakeCoverageRequirement:
    category: str
    path: Path
    function: str
    required_terms: tuple[str, ...]


def test_fake_adversarial_llm_coverage_remains_bound_to_deterministic_tests() -> None:
    requirements = [
        FakeCoverageRequirement(
            category="invalid_json",
            path=Path("tests/test_llm_researcher_adapter.py"),
            function="test_invalid_json_returns_rejection_without_raising",
            required_terms=("{not json", "invalid_json", "_capturing_llm"),
        ),
        FakeCoverageRequirement(
            category="schema_violation",
            path=Path("tests/test_llm_researcher_adapter.py"),
            function="test_invalid_proposal_contract_returns_rejection",
            required_terms=("unexpected_field", "invalid_proposal", "_capturing_llm"),
        ),
        FakeCoverageRequirement(
            category="unsafe_contract_text",
            path=Path("tests/test_llm_contracts.py"),
            function="test_research_task_rejects_unsafe_text",
            required_terms=("live order", "seed phrase", "premium_rpc_router"),
        ),
        FakeCoverageRequirement(
            category="mev_and_live_order_guard",
            path=Path("tests/test_ai_experiment_planner.py"),
            function="test_planner_rejects_unsafe_llm_experiment",
            required_terms=("mev_sandwich", "live_order_routing", "charter_violation"),
        ),
        FakeCoverageRequirement(
            category="high_capital_guard",
            path=Path("tests/test_llm_researcher_adapter.py"),
            function="test_charter_guard_rejection_returns_guard_reason_codes",
            required_terms=("capital_required_usd=1_000.0", "capital_above_budget"),
        ),
        FakeCoverageRequirement(
            category="planner_memory_redaction",
            path=Path("tests/test_ai_experiment_planner.py"),
            function="test_planner_rejects_invalid_llm_json_and_persists_safe_rejection_memory",
            required_terms=(
                "private-key seed phrase",
                "live order",
                "raw_response_omitted",
                "not in persisted",
            ),
        ),
        FakeCoverageRequirement(
            category="graph_metadata_only_redaction",
            path=Path("tests/test_llm_graph_routing.py"),
            function="test_llm_graph_rejected_invalid_json_persists_only_safe_response_metadata",
            required_terms=(
                "private-key seed phrase",
                "raw_response_sha256",
                "raw_response_omitted",
                "not in state_payload",
            ),
        ),
        FakeCoverageRequirement(
            category="report_summary_redaction",
            path=Path("tests/test_evidence_reports.py"),
            function="test_report_summarizer_rejects_invalid_or_unsafe_output_without_raw_text",
            required_terms=(
                "private-key seed phrase",
                "live order",
                "raw_response_omitted",
                "not in payload",
            ),
        ),
    ]

    missing: list[str] = []
    for requirement in requirements:
        source = _test_function_source(requirement.path, requirement.function)
        decorator_source = _test_decorator_source(requirement.path, requirement.function)
        forbidden_markers = ("integration", "llm_integration", "skip", "xfail")
        if any(marker in decorator_source.lower() for marker in forbidden_markers):
            missing.append(f"{requirement.category}: deterministic test has external/skip marker")
        for term in requirement.required_terms:
            if term.lower() not in source.lower():
                missing.append(f"{requirement.category}: missing {term!r}")

    assert missing == []


def _test_function_source(path: Path, function_name: str) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            start_line = min(
                [node.lineno, *[decorator.lineno for decorator in node.decorator_list]]
            )
            return "\n".join(lines[start_line - 1 : node.end_lineno])
    raise AssertionError(f"{function_name} not found in {path}")


def _test_decorator_source(path: Path, function_name: str) -> str:
    text = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return "\n".join(
                ast.get_source_segment(text, decorator) or "" for decorator in node.decorator_list
            )
    raise AssertionError(f"{function_name} not found in {path}")
