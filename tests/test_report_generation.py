from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.observability.logging import (
    EventLogger,
    ObservabilityEvent,
    load_events,
)
from crypto_alpha_agent.observability.reports import generate_daily_report


def test_daily_report_is_replayable_from_persisted_jsonl_events(tmp_path):
    event_path = tmp_path / "events.jsonl"

    with EventLogger(event_path) as logger:
        logger.record(
            timestamp=datetime(2026, 5, 16, 9, 30, tzinfo=UTC),
            event_type="opportunity_scored",
            run_id="run-18",
            opportunity_id="opp-1",
            decision="approve",
            action="paper_trade",
            reason_codes=["positive_expected_value"],
            metrics={"expected_net_pnl_usd": 42.5, "confidence": 0.82},
            evidence_refs=["scanner:cex-spread"],
            artifact_refs=["backtests/opp-1.json"],
        )
        logger.record(
            timestamp=datetime(2026, 5, 16, 10, 15, tzinfo=UTC),
            event_type="risk_guard",
            run_id="run-18",
            opportunity_id="opp-2",
            decision="block",
            action="skip",
            reason_codes=["capital_above_opportunity_limit", "daily_loss_limit_reached"],
            metrics={"expected_net_pnl_usd": -5.0, "confidence": 0.31},
            evidence_refs=["guardian:policy"],
        )
        logger.record(
            timestamp=datetime(2026, 5, 17, 1, 0, tzinfo=UTC),
            event_type="risk_guard",
            run_id="run-19",
            opportunity_id="opp-next-day",
            decision="approve",
            action="paper_trade",
            reason_codes=["positive_expected_value"],
            metrics={"expected_net_pnl_usd": 8.0},
        )

    original_report = generate_daily_report(
        load_events(event_path).events,
        "2026-05-16",
    )

    with event_path.open("a", encoding="utf-8") as handle:
        handle.write('{"timestamp": "2026-05-16T11:00:00Z", "event_type": ')

    replay = load_events(event_path)
    replayed_report = generate_daily_report(
        replay.events,
        "2026-05-16",
        skipped_event_lines=replay.skipped_count,
    )

    assert replay.skipped_count == 1
    assert replayed_report.total_events == 2
    assert replayed_report.event_type_counts == {
        "opportunity_scored": 1,
        "risk_guard": 1,
    }
    assert replayed_report.decision_counts == {"approve": 1, "block": 1}
    assert replayed_report.action_counts == {"paper_trade": 1, "skip": 1}
    assert replayed_report.approvals == 1
    assert replayed_report.blocks == 1
    assert replayed_report.reason_code_counts == {
        "capital_above_opportunity_limit": 1,
        "daily_loss_limit_reached": 1,
        "positive_expected_value": 1,
    }
    assert replayed_report.metrics["expected_net_pnl_usd"].sum == 37.5
    assert replayed_report.metrics["expected_net_pnl_usd"].average == 18.75
    assert replayed_report.events[0].evidence_refs == ["scanner:cex-spread"]
    assert replayed_report.events[1].reason_codes == [
        "capital_above_opportunity_limit",
        "daily_loss_limit_reached",
    ]
    assert replayed_report.model_dump(mode="json", exclude={"skipped_event_lines"}) == (
        original_report.model_dump(mode="json", exclude={"skipped_event_lines"})
    )


def test_event_logger_separates_new_event_after_truncated_jsonl_line(tmp_path):
    event_path = tmp_path / "events.jsonl"
    event_path.write_text(
        '{"timestamp": "2026-05-16T11:00:00Z", "event_type": ',
        encoding="utf-8",
    )

    with EventLogger(event_path) as logger:
        logger.record(
            timestamp=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
            event_type="opportunity_scored",
            run_id="run-after-partial",
            metrics={"expected_net_pnl_usd": 12.0},
        )

    replay = load_events(event_path)

    assert replay.skipped_count == 1
    assert [event.run_id for event in replay.events] == ["run-after-partial"]


@pytest.mark.parametrize("metric_value", [float("nan"), float("inf"), float("-inf")])
def test_observability_event_rejects_non_finite_metric_values(metric_value):
    with pytest.raises(ValidationError):
        ObservabilityEvent.model_validate(
            {
                "timestamp": datetime(2026, 5, 16, 9, 30, tzinfo=UTC),
                "event_type": "opportunity_scored",
                "run_id": "run-18",
                "metrics": {"expected_net_pnl_usd": metric_value},
            }
        )


def test_observability_event_derives_date_from_timestamp_when_supplied_date_disagrees():
    event = ObservabilityEvent.model_validate(
        {
            "timestamp": datetime(2026, 5, 16, 23, 30, tzinfo=UTC),
            "date": date(2026, 5, 15),
            "event_type": "opportunity_scored",
            "run_id": "run-18",
        }
    )

    assert event.date == date(2026, 5, 16)


def test_observability_event_derives_date_from_utc_timestamp_date():
    event = ObservabilityEvent.model_validate(
        {
            "timestamp": "2026-05-16T23:30:00-05:00",
            "event_type": "opportunity_scored",
            "run_id": "run-offset",
        }
    )

    assert event.date == date(2026, 5, 17)
