from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import requests

from crypto_alpha_agent.config import LLMSettings
from crypto_alpha_agent.llm.redaction import redact_text


class LLMProviderError(RuntimeError):
    """Provider request failed without exposing provider credentials."""


class LLMConfigurationError(ValueError):
    """Local LLM configuration is missing or unsupported."""


_PROVIDER_REQUEST_ATTEMPTS = 3
_RETRYABLE_PROVIDER_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class OpenAIResponsesAdapter:
    def __init__(self, settings: LLMSettings, *, session: Any | None = None) -> None:
        self.settings = settings
        self._session_injected = session is not None
        self.session = session if session is not None else requests.Session()

    def __call__(self, task: Any) -> str:
        payload = {
            "model": self.settings.model,
            "input": self._render_input(task),
        }
        text_format = _text_format_for_task(task)
        if text_format is not None:
            payload["text"] = {"format": text_format}
        headers = {
            "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        response = self._post_with_retries(payload=payload, headers=headers)
        try:
            response_payload = response.json()
        except Exception as exc:  # noqa: BLE001 - provider JSON parse boundary.
            raise LLMProviderError(
                self._redact(
                    f"LLM provider returned invalid JSON: {type(exc).__name__}"
                )
            ) from None
        return _extract_response_text(response_payload)

    def _post_with_retries(
        self, *, payload: dict[str, Any], headers: dict[str, str]
    ) -> Any:
        for attempt in range(1, _PROVIDER_REQUEST_ATTEMPTS + 1):
            try:
                response = self.session.post(
                    self._responses_url(),
                    headers=headers,
                    json=payload,
                    timeout=self.settings.timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - redacted provider boundary.
                if attempt == _PROVIDER_REQUEST_ATTEMPTS:
                    raise LLMProviderError(
                        self._redact(
                            "LLM provider request failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
                    ) from None
                continue
            if response.status_code < 400:
                return response
            if (
                attempt < _PROVIDER_REQUEST_ATTEMPTS
                and response.status_code in _RETRYABLE_PROVIDER_STATUS_CODES
            ):
                continue
            raise LLMProviderError(
                self._redact(
                    f"LLM provider request failed with status {response.status_code}: "
                    f"{getattr(response, 'text', '')}"
                )
            )
        raise AssertionError("unreachable provider retry state")

    def _responses_url(self) -> str:
        base_url = self.settings.base_url.rstrip("/")
        if base_url.endswith("/responses"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/responses"
        return f"{base_url}/v1/responses"

    def _render_input(self, task: Any) -> str:
        if hasattr(task, "model_dump"):
            task_payload = task.model_dump(mode="json")
        elif isinstance(task, dict):
            task_payload = task
        else:
            task_payload = {"task": str(task)}
        schema_hint = _schema_hint_for_task(task)
        return (
            "You are a research-only crypto alpha assistant. Return only valid JSON "
            "that matches the caller's requested schema. Do not request prohibited "
            "execution capabilities, secret material, privileged infrastructure, "
            "or capital beyond the supplied profile. Do not wrap JSON in markdown "
            "fences. Do not add fields outside the requested schema. In free-text "
            "fields, do not repeat prohibited execution terms; describe boundaries "
            "as research-only and public-data-only instead.\n\n"
            f"{schema_hint}\n\n"
            "Task JSON:\n"
            + json.dumps(task_payload, sort_keys=True, default=str)
        )

    def _redact(self, value: object) -> str:
        return redact_text(
            value,
            secrets=[
                self.settings.api_key.get_secret_value(),
                *self._base_url_redaction_values(),
            ],
        )

    def _base_url_redaction_values(self) -> list[str]:
        parsed = urlparse(self.settings.base_url)
        values = [self.settings.base_url]
        if parsed.netloc:
            values.append(parsed.netloc)
        if parsed.hostname:
            values.append(parsed.hostname)
        return values


def _extract_response_text(payload: Any) -> str:
    if isinstance(payload, dict):
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        output = payload.get("output")
        if isinstance(output, list):
            for item in output:
                text = _extract_output_item_text(item)
                if text:
                    return text
    raise LLMProviderError("LLM provider response did not contain output text")


def _extract_output_item_text(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    content = item.get("content")
    if isinstance(content, list):
        for content_item in content:
            if isinstance(content_item, dict):
                text = content_item.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    text = item.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _text_format_for_task(task: Any) -> dict[str, Any] | None:
    task_type = type(task).__name__
    if task_type == "ResearchTask":
        return _json_schema_text_format(
            "HypothesisProposal",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "proposal_id": {"type": "string"},
                    "thesis": {"type": "string"},
                    "hypothesis": {"type": "string"},
                    "assumptions": _string_list_schema(),
                    "evidence": _string_list_schema(),
                    "disconfirmation": _string_list_schema(),
                    "data_needed": _string_list_schema(),
                    "capital_required_usd": {"type": "number", "minimum": 0},
                    "speed_dependency": {
                        "type": "string",
                        "enum": ["none", "low", "medium", "high"],
                    },
                    "rpc_dependency": {
                        "type": "string",
                        "enum": ["none", "low", "medium", "high"],
                    },
                    "action_mode": {"type": "string", "enum": ["research_only"]},
                },
                "required": [
                    "proposal_id",
                    "thesis",
                    "hypothesis",
                    "assumptions",
                    "evidence",
                    "disconfirmation",
                    "data_needed",
                    "capital_required_usd",
                    "speed_dependency",
                    "rpc_dependency",
                    "action_mode",
                ],
            },
        )
    if task_type == "ExperimentPlannerTask":
        return _json_schema_text_format(
            "ExperimentPlannerPayload",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "proposals": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": _experiment_proposal_payload_schema(task),
                    }
                },
                "required": ["proposals"],
            },
        )
    if task_type == "EvidenceReportSummaryTask":
        return _json_schema_text_format(
            "EvidenceReportNarrativeSummary",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "report_type": {"type": "string", "enum": ["daily", "weekly"]},
                    "summary": {"type": "string"},
                    "metric_refs": _string_list_schema(max_items=16),
                    "caveats": _string_list_schema(max_items=12),
                    "uses_real_capital": {"type": "boolean", "enum": [False]},
                    "live_order_routing": {"type": "boolean", "enum": [False]},
                },
                "required": [
                    "report_type",
                    "summary",
                    "metric_refs",
                    "caveats",
                    "uses_real_capital",
                    "live_order_routing",
                ],
            },
        )
    if task_type == "IterationControllerTask":
        return _json_schema_text_format(
            "IterationCandidateBatch",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "candidates": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": _iteration_max_candidates(task),
                        "items": _iteration_candidate_schema(),
                    },
                    "rejected_reason_codes": _string_list_schema(
                        min_items=0,
                        max_items=32,
                    ),
                    "uses_real_capital": {"type": "boolean", "enum": [False]},
                    "live_order_routing": {"type": "boolean", "enum": [False]},
                },
                "required": [
                    "candidates",
                    "rejected_reason_codes",
                    "uses_real_capital",
                    "live_order_routing",
                ],
            },
        )
    if task_type == "LLMHealthCheckTask":
        return _json_schema_text_format(
            "LLMHealthCheckResult",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "status": {"type": "string", "enum": ["ok"]},
                    "schema_name": {
                        "type": "string",
                        "enum": ["LLMHealthCheckResult"],
                    },
                    "capabilities": _string_list_schema(min_items=2),
                    "uses_real_capital": {"type": "boolean", "enum": [False]},
                    "live_order_routing": {"type": "boolean", "enum": [False]},
                },
                "required": [
                    "status",
                    "schema_name",
                    "capabilities",
                    "uses_real_capital",
                    "live_order_routing",
                ],
            },
        )
    if task_type == "LLMJudgementTask":
        return _judgement_text_format_for_task(task)
    return None


def _json_schema_text_format(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": name,
        "schema": schema,
        "strict": True,
    }


def _string_list_schema(
    *,
    min_items: int = 1,
    max_items: int | None = None,
    enum_values: list[str] | None = None,
) -> dict[str, Any]:
    item_schema: dict[str, Any] = {"type": "string"}
    if enum_values:
        item_schema["enum"] = enum_values
    schema: dict[str, Any] = {
        "type": "array",
        "minItems": min_items,
        "items": item_schema,
    }
    if max_items is not None:
        schema["maxItems"] = max_items
    return schema


def _experiment_proposal_payload_schema(task: Any) -> dict[str, Any]:
    values = _planner_schema_values(task)
    strategy_family_schema: dict[str, Any] = {"type": "string"}
    if values["strategy_families"]:
        strategy_family_schema["enum"] = values["strategy_families"]
    selected_validator_schema: dict[str, Any] = {"type": "string"}
    if values["validator_names"]:
        selected_validator_schema["enum"] = values["validator_names"]
    required_data_fields_schema = _string_list_schema(
        min_items=values["required_data_field_count"],
        max_items=values["required_data_field_count"],
        enum_values=values["required_data_fields"],
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "strategy_family": strategy_family_schema,
            "parameter_changes": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "threshold_abs": {"type": "number", "minimum": 0},
                    "hold_bars": {"type": "integer", "minimum": 1},
                },
                "required": ["threshold_abs", "hold_bars"],
            },
            "evidence_refs": _string_list_schema(),
            "why_it_might_improve_edge": {"type": "string"},
            "expected_edge_mechanism": {"type": "string"},
            "disconfirmation_tests": _string_list_schema(),
            "stop_conditions": _string_list_schema(),
            "required_data_fields": required_data_fields_schema,
            "selected_validator": selected_validator_schema,
            "uses_real_capital": {"type": "boolean", "enum": [False]},
            "live_order_routing": {"type": "boolean", "enum": [False]},
        },
        "required": [
            "strategy_family",
            "parameter_changes",
            "evidence_refs",
            "why_it_might_improve_edge",
            "expected_edge_mechanism",
            "disconfirmation_tests",
            "stop_conditions",
            "required_data_fields",
            "selected_validator",
            "uses_real_capital",
            "live_order_routing",
        ],
    }


def _iteration_candidate_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {
                "type": "string",
                "enum": [
                    "new_data_source",
                    "new_strategy_validator",
                    "validator_change",
                    "experiment_parameter_change",
                    "code_change_request",
                ],
            },
            "title": {"type": "string"},
            "rationale": {"type": "string"},
            "evidence_refs": _string_list_schema(min_items=1, max_items=12),
            "expected_value": {"type": "string"},
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "blocked"],
            },
            "next_actions": _string_list_schema(min_items=1, max_items=12),
            "required_tests": _string_list_schema(min_items=1, max_items=12),
            "required_data_fields": _string_list_schema(min_items=1, max_items=24),
            "source_discovery_queries": _string_list_schema(
                min_items=0,
                max_items=8,
            ),
            "source_probe_targets": _string_list_schema(
                min_items=0,
                max_items=8,
            ),
            "strategy_family": {"type": ["string", "null"]},
            "target_files": _string_list_schema(min_items=0, max_items=12),
            "human_review_required": {"type": "boolean", "enum": [True]},
            "direct_code_write_authorized": {"type": "boolean", "enum": [False]},
            "uses_real_capital": {"type": "boolean", "enum": [False]},
            "live_order_routing": {"type": "boolean", "enum": [False]},
        },
        "required": [
            "kind",
            "title",
            "rationale",
            "evidence_refs",
            "expected_value",
            "risk_level",
            "next_actions",
            "required_tests",
            "required_data_fields",
            "source_discovery_queries",
            "source_probe_targets",
            "strategy_family",
            "target_files",
            "human_review_required",
            "direct_code_write_authorized",
            "uses_real_capital",
            "live_order_routing",
        ],
    }


def _iteration_max_candidates(task: Any) -> int:
    controller_input = getattr(task, "controller_input", None)
    value = getattr(controller_input, "max_candidates", 5)
    if isinstance(value, int) and 1 <= value <= 10:
        return value
    return 5


def _planner_schema_values(task: Any) -> dict[str, Any]:
    planner_input = getattr(task, "planner_input", None)
    requested_family = getattr(planner_input, "strategy_family", None)
    registered_validators = [
        item
        for item in getattr(task, "registered_validators", [])
        if isinstance(item, dict)
    ]
    matching_validators = [
        item
        for item in registered_validators
        if not requested_family or item.get("strategy_family") == requested_family
    ]
    if not matching_validators:
        matching_validators = registered_validators

    strategy_families = _dedupe_strings(
        [
            str(item.get("strategy_family", ""))
            for item in matching_validators
            if item.get("strategy_family")
        ]
    )
    if requested_family and requested_family not in strategy_families:
        strategy_families = [requested_family, *strategy_families]
    validator_names = _dedupe_strings(
        [
            str(item.get("validator_name", ""))
            for item in matching_validators
            if item.get("validator_name")
        ]
    )
    required_data_fields = _dedupe_strings(
        [
            str(field)
            for item in matching_validators
            for field in item.get("required_record_types", [])
        ]
    )
    if not validator_names:
        validator_names = ["funding_price_confirmation"]
    if not required_data_fields:
        required_data_fields = ["market_candle", "funding_rate"]
    return {
        "strategy_families": strategy_families,
        "validator_names": validator_names,
        "required_data_fields": required_data_fields,
        "required_data_field_count": max(1, len(required_data_fields)),
    }


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _judgement_text_format_for_task(task: Any) -> dict[str, Any]:
    schema_name = str(getattr(task, "schema_name", "")).strip()
    return _json_schema_text_format(
        schema_name or "RuntimeCommandJudgement",
        _judgement_schema_for_name(schema_name),
    )


def _judgement_schema_for_name(schema_name: str) -> dict[str, Any]:
    base = _judgement_base_schema(schema_name)
    if schema_name == "SourceResearchJudgement":
        return base
    if schema_name == "DataReadinessJudgement":
        schema = _clone_schema(base)
        schema["properties"]["missing_fields"] = _string_list_schema(max_items=24)
        schema["required"] = [*schema["required"], "missing_fields"]
        return schema
    if schema_name == "LLMHypothesisSet":
        schema = _clone_schema(base)
        schema["properties"]["hypotheses"] = {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "object", "additionalProperties": True},
        }
        schema["properties"]["critique"] = _string_list_schema(max_items=12)
        schema["required"] = [*schema["required"], "hypotheses", "critique"]
        return schema
    if schema_name == "EvidenceRunInterpretation":
        schema = _clone_schema(base)
        schema["properties"]["blocked_reason_review"] = _string_list_schema(max_items=16)
        schema["properties"]["next_experiment"] = _evidence_run_next_experiment_schema()
        schema["required"] = [
            *schema["required"],
            "blocked_reason_review",
            "next_experiment",
        ]
        return schema
    if schema_name == "GovernanceReview":
        schema = _clone_schema(base)
        schema["properties"]["family_actions"] = {
            "type": "object",
            "additionalProperties": {
                "type": "string",
                "enum": [
                    "research_ready",
                    "keep_collecting",
                    "add_data",
                    "redesign_validator",
                    "stop",
                    "owner_decision_review",
                    "blocked",
                ],
            },
        }
        schema["required"] = [*schema["required"], "family_actions"]
        return schema
    if schema_name == "BootstrapInterpretation":
        schema = _clone_schema(base)
        schema["properties"]["historical_is_profit_proof"] = {
            "type": "boolean",
            "enum": [False],
        }
        schema["required"] = [
            *schema["required"],
            "historical_is_profit_proof",
        ]
        return schema
    if schema_name == "RolloutReadinessNarrative":
        schema = _clone_schema(base)
        schema["properties"]["live_execution_enabled"] = {
            "type": "boolean",
            "enum": [False],
        }
        schema["required"] = [*schema["required"], "live_execution_enabled"]
        return schema
    return base


def _evidence_run_next_experiment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "strategy_family": {"type": ["string", "null"]},
            "experiment_type": {"type": "string"},
            "rationale": {"type": "string"},
            "required_data_fields": _string_list_schema(min_items=0, max_items=24),
            "stop_conditions": _string_list_schema(min_items=0, max_items=12),
        },
        "required": [
            "strategy_family",
            "experiment_type",
            "rationale",
            "required_data_fields",
            "stop_conditions",
        ],
    }


def _judgement_base_schema(schema_name: str) -> dict[str, Any]:
    schema_name_property: dict[str, Any] = {"type": "string"}
    if schema_name:
        schema_name_property["enum"] = [schema_name]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_name": schema_name_property,
            "decision": {
                "type": "string",
                "enum": [
                    "useful_for_research",
                    "not_ready",
                    "ready_for_offline_research",
                    "research_only",
                    "research_ready",
                    "keep_collecting",
                    "add_data",
                    "redesign_validator",
                    "stop",
                    "owner_decision_review",
                    "blocked",
                ],
            },
            "rationale": {"type": "string"},
            "evidence_refs": _string_list_schema(max_items=32),
            "next_actions": _string_list_schema(max_items=12),
            "uses_real_capital": {"type": "boolean", "enum": [False]},
            "live_order_routing": {"type": "boolean", "enum": [False]},
        },
        "required": [
            "schema_name",
            "decision",
            "rationale",
            "evidence_refs",
            "next_actions",
            "uses_real_capital",
            "live_order_routing",
        ],
    }


def _clone_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": schema["type"],
        "additionalProperties": schema["additionalProperties"],
        "properties": dict(schema["properties"]),
        "required": list(schema["required"]),
    }


def _schema_hint_for_task(task: Any) -> str:
    task_type = type(task).__name__
    if task_type == "ResearchTask":
        return (
            "Schema instructions: return exactly one HypothesisProposal JSON object "
            "with these fields: proposal_id, thesis, hypothesis, assumptions, "
            "evidence, disconfirmation, data_needed, capital_required_usd, "
            "speed_dependency, rpc_dependency, action_mode. Use action_mode "
            '"research_only"; use speed_dependency and rpc_dependency values "none", '
            '"low", "medium", or "high"; keep capital_required_usd within the '
            "supplied current_capital_usd. Do not include extra fields or prohibited "
            "execution terms in thesis, hypothesis, assumptions, evidence, "
            "disconfirmation, or data_needed."
        )
    if task_type == "ExperimentPlannerTask":
        return (
            "Schema instructions: return bounded ExperimentProposal payloads as "
            "exactly one JSON object with a proposals list. The top-level object "
            "must contain only proposals. Each proposal "
            "must contain exactly these fields: strategy_family, parameter_changes, "
            "evidence_refs, why_it_might_improve_edge, expected_edge_mechanism, "
            "disconfirmation_tests, stop_conditions, required_data_fields, "
            "selected_validator, uses_real_capital, and live_order_routing. Set "
            "uses_real_capital=false and live_order_routing=false. Use non-empty "
            "string lists for evidence_refs, disconfirmation_tests, stop_conditions, "
            "and required_data_fields. required_data_fields must exactly match the "
            "selected validator's required_record_types. parameter_changes must be a JSON object. Use only "
            "registered strategy families and selected_validator values from the task "
            "context, and do not repeat blocked parameter sets. Do not include "
            "allowed_data_sources, proposal_id, max_capital_usd, max_notional_usd, "
            "accepted, rejected_reason_codes, or strategy_template_proposals; the "
            "planner computes those fields. Do not use prohibited execution terms in "
            "why_it_might_improve_edge, expected_edge_mechanism, "
            "disconfirmation_tests, or stop_conditions; phrase safety boundaries as "
            "research-only, paper-only, public-data-only, after-cost, and "
            "walk-forward checks."
        )
    if task_type == "EvidenceReportSummaryTask":
        return (
            "Schema instructions: return exactly one EvidenceReportNarrativeSummary "
            "JSON object with report_type, summary, metric_refs, caveats, "
            "uses_real_capital=false, and live_order_routing=false. Summarize only "
            "the deterministic metrics supplied in the task. metric_refs must be a "
            "short list of 1 to 16 strings, and caveats must be a short list of 0 to "
            "12 strings. Do not include uses_real_capital or live_order_routing as "
            "metric_refs; those are structural boolean fields only. Do not include "
            "extra fields or prohibited execution terms in summary, metric_refs, or "
            "caveats. Do not write phrases containing live, order, routing, "
            "capital, or execution in summary or caveats; say research-only and "
            "public-data-only instead."
        )
    if task_type == "IterationControllerTask":
        return (
            "Schema instructions: return exactly one IterationCandidateBatch JSON "
            "object with candidates, rejected_reason_codes, uses_real_capital=false, "
            "and live_order_routing=false. Each IterationCandidate must contain "
            "exactly these fields: kind, title, rationale, evidence_refs, "
            "expected_value, risk_level, next_actions, required_tests, "
            "required_data_fields, source_discovery_queries, source_probe_targets, "
            "strategy_family, target_files, human_review_required, "
            "direct_code_write_authorized, uses_real_capital, and "
            "live_order_routing. Use only kind values from allowed_candidate_kinds. "
            "Use only evidence_refs from the task evidence_refs list. Set "
            "human_review_required=true, direct_code_write_authorized=false, "
            "uses_real_capital=false, and live_order_routing=false. For "
            "new_data_source, include at least one string in source_discovery_queries "
            "or source_probe_targets. For code_change_request, include target_files "
            "and required_tests. Do not include candidate_id, candidate_kind, "
            "tool_refs, provider, feed, source_id, discovery_queries, "
            "acceptance_criteria, preconditions, validator_scope, proposed_parameters, "
            "or any other extra fields."
        )
    if task_type == "LLMHealthCheckTask":
        return (
            "Schema instructions: return exactly one LLMHealthCheckResult JSON "
            'object with status="ok", schema_name="LLMHealthCheckResult", '
            "capabilities including json_schema and research_only, "
            "uses_real_capital=false, and live_order_routing=false. Do not include "
            "extra fields."
        )
    if task_type == "LLMJudgementTask":
        return (
            "Schema instructions: return exactly one JSON object matching schema_name "
            "from the task. Include schema_name, decision, rationale, evidence_refs "
            "using only refs from the task, next_actions, uses_real_capital=false, "
            "and live_order_routing=false. For DataReadinessJudgement include "
            "missing_fields. For BootstrapInterpretation include "
            "historical_is_profit_proof=false. For RolloutReadinessNarrative "
            "include live_execution_enabled=false. Do not include extra fields or "
            "unsupported evidence refs."
        )
    return "Schema instructions: return only a valid JSON object for the caller."
