from __future__ import annotations

import json

import pytest

from crypto_alpha_agent.config import LLMSettings
from crypto_alpha_agent.llm.runtime import RealLLMRuntime
from crypto_alpha_agent.pipeline.llm_judgements import (
    BootstrapInterpretation,
    DataReadinessJudgement,
    SourceResearchJudgement,
    run_source_research_judgement,
)


class CapturingLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []
        self.settings = LLMSettings(
            base_url="https://llm.example/v1",
            api_key="secret-test-key",
            model="test-real-model",
            role="research",
        )

    def __call__(self, task):
        self.calls.append(task)
        return self.response


def test_source_research_judgement_requires_real_evidence_ref() -> None:
    llm = CapturingLLM(
        json.dumps(
            {
                "schema_name": "SourceResearchJudgement",
                "decision": "add_data",
                "rationale": "Source needs another canary before research use.",
                "evidence_refs": ["source-health:binance_usdm_open_interest_history"],
                "next_actions": ["Run one more source probe with nonzero typed rows."],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )
    )
    runtime = RealLLMRuntime._for_test_double(llm=llm, role="research")

    result = run_source_research_judgement(
        runtime,
        command="source-probe",
        source_health={"target_id": "binance_usdm_open_interest_history"},
        evidence_refs=["source-health:binance_usdm_open_interest_history"],
    )

    assert result.decision == "add_data"
    assert result.evidence_refs == ["source-health:binance_usdm_open_interest_history"]
    assert llm.calls[0].schema_name == "SourceResearchJudgement"


def test_source_research_judgement_rejects_unknown_ref() -> None:
    with pytest.raises(ValueError, match="unknown evidence refs"):
        SourceResearchJudgement(
            schema_name="SourceResearchJudgement",
            decision="add_data",
            rationale="bad ref",
            evidence_refs=["missing"],
            next_actions=["collect data"],
            uses_real_capital=False,
            live_order_routing=False,
        ).validate_refs({"known"})


def test_data_readiness_judgement_schema_is_strict() -> None:
    with pytest.raises(ValueError):
        DataReadinessJudgement.model_validate(
            {
                "schema_name": "DataReadinessJudgement",
                "decision": "research_ready",
                "rationale": "ok",
                "evidence_refs": ["data-quality:ccxt"],
                "missing_fields": [],
                "next_actions": ["run research-loop"],
                "uses_real_capital": False,
                "live_order_routing": False,
                "extra": "not allowed",
            }
        )


def test_judgements_accept_context_specific_research_decisions() -> None:
    source = SourceResearchJudgement.model_validate(
        {
            "schema_name": "SourceResearchJudgement",
            "decision": "useful_for_research",
            "rationale": "The listed target can support public-data research.",
            "evidence_refs": ["source-health:list-targets"],
            "next_actions": ["Probe the target before using it in paper evidence."],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )
    readiness = DataReadinessJudgement.model_validate(
        {
            "schema_name": "DataReadinessJudgement",
            "decision": "ready_for_offline_research",
            "rationale": "Offline check created storage but did not ingest typed rows.",
            "evidence_refs": ["ingest:offline_check"],
            "missing_fields": ["market_candle", "funding_rate"],
            "next_actions": ["Collect the missing public datasets first."],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )
    bootstrap = BootstrapInterpretation.model_validate(
        {
            "schema_name": "BootstrapInterpretation",
            "decision": "research_only",
            "rationale": "Historical bootstrap is useful context but not profit proof.",
            "evidence_refs": ["historical-bootstrap:run"],
            "next_actions": ["Continue with forward paper observations."],
            "historical_is_profit_proof": False,
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )

    assert source.decision == "useful_for_research"
    assert readiness.decision == "ready_for_offline_research"
    assert bootstrap.decision == "research_only"
