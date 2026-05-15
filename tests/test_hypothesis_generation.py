from __future__ import annotations

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.agents.anomaly import AnomalyDetector
from crypto_alpha_agent.agents.scanner import ScannerSignal


def test_structural_anomaly_generates_falsifiable_hypothesis_with_required_fields():
    from crypto_alpha_agent.agents.hypothesis import HypothesisGenerator

    signal = ScannerSignal(
        category="dex",
        source="uniswap-v3",
        asset="ETH",
        metric="pool_imbalance",
        value=1.42,
        evidence=["tick liquidity shifted toward buys"],
        raw={"pool": "0xabc", "delta": 0.19},
        venue="uniswap",
        protocol="uniswap-v3",
        z_score=3.8,
        deviation=0.27,
        persistence_seconds=1_800,
        liquidity_usd=250_000,
        capital_required_usd=10_000,
        structural_break=True,
    )

    [anomaly] = AnomalyDetector().rank([signal])
    [hypothesis] = HypothesisGenerator().generate([anomaly])

    assert hypothesis.what_changed
    assert hypothesis.why_it_might_be_edge
    assert hypothesis.evidence
    assert hypothesis.expected_persistence_seconds == pytest.approx(1_800)
    assert hypothesis.disconfirmation_tests
    assert hypothesis.disconfirmation_criteria
    assert hypothesis.disconfirmation_criteria[0].metric == "deviation"
    assert hypothesis.disconfirmation_criteria[0].operator == "abs_lte"
    assert hypothesis.disconfirmation_criteria[0].threshold == pytest.approx(0.135)
    assert hypothesis.disconfirmation_criteria[0].window_seconds == pytest.approx(1_800)
    assert hypothesis.action_mode == "research_only"
    assert hypothesis.actionability == "executable"


def test_evidence_bundle_preserves_source_category_and_raw_evidence():
    from crypto_alpha_agent.agents.hypothesis import HypothesisGenerator

    signal = ScannerSignal(
        category="chain",
        source="thegraph",
        asset="ARB",
        metric="holder_concentration",
        value=0.84,
        evidence=["top wallets accumulated"],
        raw={"query": "holders", "sample_size": 120},
        chain="arbitrum",
        z_score=2.9,
        persistence_seconds=2_400,
        liquidity_usd=140_000,
        capital_required_usd=8_000,
    )

    [anomaly] = AnomalyDetector().rank([signal])
    [hypothesis] = HypothesisGenerator().generate([anomaly])
    [bundle] = hypothesis.evidence

    assert bundle.source == "thegraph"
    assert bundle.category == "chain"
    assert bundle.raw == {"query": "holders", "sample_size": 120}
    assert bundle.signal_evidence == ["top wallets accumulated"]
    assert bundle.anomaly_classification == anomaly.classification


def test_evidence_bundle_deep_copies_nested_raw_evidence():
    from crypto_alpha_agent.agents.hypothesis import HypothesisGenerator

    signal = ScannerSignal(
        category="chain",
        source="thegraph",
        asset="OP",
        metric="bridge_inflow",
        value=8_000_000,
        evidence=["bridge inflow spike"],
        raw={"response": {"rows": [{"amount": 8_000_000}]}},
        chain="optimism",
        z_score=3.4,
        persistence_seconds=1_200,
    )

    [hypothesis] = HypothesisGenerator().generate([signal])

    signal.raw["response"]["rows"][0]["amount"] = 1

    assert hypothesis.evidence[0].raw == {"response": {"rows": [{"amount": 8_000_000}]}}


def test_mirage_anomaly_produces_research_only_hypothesis_and_marks_actionability():
    from crypto_alpha_agent.agents.hypothesis import HypothesisGenerator

    signal = ScannerSignal(
        category="cex",
        source="binance",
        asset="BTC",
        metric="spread_capture",
        value=0.11,
        evidence=["visible spread on low depth book"],
        raw={"pair": "BTC/USDT"},
        venue="binance",
        z_score=2.1,
        persistence_seconds=900,
        liquidity_usd=5_000,
        capital_required_usd=20_000,
        speed_dependency="high",
        rpc_dependency="high",
    )

    [anomaly] = AnomalyDetector().rank([signal])
    assert anomaly.classification == "mirage"
    assert anomaly.executable is False

    [hypothesis] = HypothesisGenerator().generate([anomaly])

    assert hypothesis.action_mode == "research_only"
    assert hypothesis.actionability == "blocked"
    assert "mirage" in hypothesis.what_changed.lower()


def test_alpha_hypothesis_requires_evidence_and_disconfirmation_criteria():
    from crypto_alpha_agent.agents.hypothesis import (
        AlphaHypothesis,
        DisconfirmationCriterion,
        EvidenceBundle,
    )

    with pytest.raises(ValidationError):
        AlphaHypothesis(
            source="thegraph",
            category="chain",
            asset="ARB",
            what_changed="holder concentration increased",
            why_it_might_be_edge="large holders can front-run passive flows",
            evidence=[],
            expected_persistence_seconds=1_800,
            disconfirmation_tests=["if concentration normalizes on the next snapshot, invalidate"],
            disconfirmation_criteria=[
                DisconfirmationCriterion(
                    metric="holder_concentration",
                    operator="lte",
                    threshold=0.5,
                    window_seconds=1_800,
                    reason="invalidate if concentration normalizes",
                )
            ],
            action_mode="research_only",
            actionability="executable",
        )

    with pytest.raises(ValidationError):
        AlphaHypothesis(
            source="thegraph",
            category="chain",
            asset="ARB",
            what_changed="holder concentration increased",
            why_it_might_be_edge="large holders can front-run passive flows",
            evidence=[
                EvidenceBundle(
                    source="thegraph",
                    category="chain",
                    asset="ARB",
                    metric="holder_concentration",
                    value=0.84,
                    signal_evidence=["top wallets accumulated"],
                    raw={"query": "holders"},
                    anomaly_classification="statistical_outlier",
                    anomaly_score=18.0,
                    executable=True,
                    persistence_seconds=1_800,
                )
            ],
            expected_persistence_seconds=1_800,
            disconfirmation_tests=[],
            disconfirmation_criteria=[
                DisconfirmationCriterion(
                    metric="holder_concentration",
                    operator="lte",
                    threshold=0.5,
                    window_seconds=1_800,
                    reason="invalidate if concentration normalizes",
                )
            ],
            action_mode="research_only",
            actionability="executable",
        )

    with pytest.raises(ValidationError):
        AlphaHypothesis(
            source="thegraph",
            category="chain",
            asset="ARB",
            what_changed="holder concentration increased",
            why_it_might_be_edge="large holders can front-run passive flows",
            evidence=[
                EvidenceBundle(
                    source="thegraph",
                    category="chain",
                    asset="ARB",
                    metric="holder_concentration",
                    value=0.84,
                    signal_evidence=["top wallets accumulated"],
                    raw={"query": "holders"},
                    anomaly_classification="statistical_outlier",
                    anomaly_score=18.0,
                    executable=True,
                    persistence_seconds=1_800,
                )
            ],
            expected_persistence_seconds=1_800,
            disconfirmation_tests=["if concentration normalizes on the next snapshot, invalidate"],
            disconfirmation_criteria=[],
            action_mode="research_only",
            actionability="executable",
        )
