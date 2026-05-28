# LLM-Native Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every product CLI path require a real configured LLM and remove deterministic-only product success paths.

**Architecture:** Add a required real LLM runtime layer, run a structured health check before every product command, and pass the runtime into command handlers for command-specific LLM judgements. Deterministic modules remain as calculators, guards, ledgers, and renderers; they no longer define product success without real LLM participation.

**Tech Stack:** Python 3.12, argparse CLI, Pydantic strict models, existing OpenAI-compatible Responses adapter, pytest with `integration`, `llm_integration`, and new `core_acceptance` markers.

---

## Scope Check

This plan implements the approved design in
`docs/superpowers/specs/2026-05-24-llm-native-runtime-design.md`.

The work is broad but tightly coupled around one runtime rule: no real LLM, no
product runtime. Splitting the work into separate feature branches would leave
temporary bypass paths. Keep this as one implementation plan with small commits
after each task.

## File Structure

Create:

- `src/crypto_alpha_agent/llm/runtime.py`
  Required real LLM runtime context, health-check task/result schemas,
  structured JSON parsing, runtime metadata, and fail-closed errors.

- `src/crypto_alpha_agent/pipeline/llm_judgements.py`
  Command-specific LLM judgement task/result schemas and helpers for source,
  ingest, research, evidence, governance, bootstrap, rollout, and legacy command
  judgements.

- `tests/test_llm_native_runtime.py`
  Unit tests for required runtime construction, health schema parsing, failure
  redaction, and fake-provider rejection.

- `tests/test_cli_llm_native_gate.py`
  CLI tests for the global runtime gate, bypass commands, no-side-effect
  preflight failure, and removal of `--offline-only`.

- `tests/test_llm_native_judgements.py`
  Unit tests for command-specific judgement schema validation and evidence-ref
  guard behavior.

Modify:

- `src/crypto_alpha_agent/config.py`
  Add required real LLM builders. Remove product-facing optional defaults.

- `src/crypto_alpha_agent/llm/__init__.py`
  Export required runtime builders and errors.

- `src/crypto_alpha_agent/llm/responses.py`
  Add schema hints for new runtime and judgement task models.

- `src/crypto_alpha_agent/cli.py`
  Add `llm-health-check`, add `--version`, run the global runtime gate, remove
  `--offline-only`, remove `_resolve_llm_for_cli`, and require command-specific
  LLM judgements.

- `src/crypto_alpha_agent/pipeline/experiment_planner.py`
  Remove deterministic product fallback and require an LLM callable/runtime.

- `src/crypto_alpha_agent/agents/report_summarizer.py`
  Treat invalid or rejected summaries as product failures when called from CLI.

- `src/crypto_alpha_agent/pipeline/evidence_runner.py`
  Carry LLM interpretation metadata in `EvidenceRunnerReport`.

- `src/crypto_alpha_agent/pipeline/research_loop.py`
  Carry LLM hypothesis/critique metadata in `ResearchLoopReport` or CLI payloads.

- `src/crypto_alpha_agent/pipeline/governance_reports.py`
  Add deterministic fact surface for LLM governance review and conflict checks.

- `src/crypto_alpha_agent/pipeline/historical_bootstrap.py`
  Add deterministic fact surface for LLM bootstrap interpretation.

- `src/crypto_alpha_agent/risk/rollout.py` or `src/crypto_alpha_agent/evidence/live_readiness.py`
  Keep readiness facts deterministic while allowing an LLM narrative wrapper.

- `tests/llm_integration_policy.py`
  Replace skip helpers with fail-closed helpers for core acceptance.

- `tests/test_real_llm_integration_policy.py`
  Expand real LLM acceptance coverage and remove `--no-offline-only`.

- `tests/test_real_llm_test_policy_contract.py`
  Enforce marker registration and fake LLM boundaries under the new policy.

- `pyproject.toml`
  Add `core_acceptance` marker.

- `docs/runbook.md`, `docs/roadmap.md`,
  `docs/goals/project-completion-state.md`
  Update docs to say LLM is mandatory and deterministic-only product runs are no
  longer valid.

## Task 1: Add Required LLM Runtime

**Files:**

- Create: `src/crypto_alpha_agent/llm/runtime.py`
- Modify: `src/crypto_alpha_agent/config.py`
- Modify: `src/crypto_alpha_agent/llm/__init__.py`
- Test: `tests/test_llm_native_runtime.py`

- [ ] **Step 1: Write failing runtime tests**

Add `tests/test_llm_native_runtime.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_alpha_agent.config import LLMSettings
from crypto_alpha_agent.llm.runtime import (
    LLMHealthCheckResult,
    LLMRuntimeError,
    RealLLMRuntime,
    build_required_real_llm_runtime,
    parse_structured_llm_json,
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


def test_parse_structured_llm_json_rejects_non_json() -> None:
    with pytest.raises(LLMRuntimeError, match="invalid_json"):
        parse_structured_llm_json("not json", LLMHealthCheckResult)


def test_real_runtime_health_check_records_real_provider_metadata() -> None:
    llm = CapturingLLM(
        json.dumps(
            {
                "status": "ok",
                "schema_name": "LLMHealthCheckResult",
                "capabilities": ["json_schema", "research_only"],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )
    )
    runtime = RealLLMRuntime(llm=llm, provider="real", role="research")

    result = runtime.health_check(command="research-loop")

    assert result.status == "ok"
    assert llm.calls
    assert runtime.metadata()["llm_provider"] == "real"
    assert runtime.metadata()["used_fake_llm"] is False
    assert runtime.metadata()["llm_model"] == "test-real-model"


def test_real_runtime_rejects_fake_provider() -> None:
    llm = CapturingLLM("{}")

    with pytest.raises(LLMRuntimeError, match="fake_llm_not_allowed"):
        RealLLMRuntime(llm=llm, provider="fake", role="research")


def test_build_required_real_llm_runtime_fails_when_env_missing(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")

    with pytest.raises(LLMRuntimeError, match="llm_configuration_missing"):
        build_required_real_llm_runtime(env_file=env_path, role="research")
```

- [ ] **Step 2: Run failing runtime tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_native_runtime.py -q
```

Expected: FAIL because `crypto_alpha_agent.llm.runtime` does not exist.

- [ ] **Step 3: Implement runtime module**

Create `src/crypto_alpha_agent/llm/runtime.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from crypto_alpha_agent.config import LLMRole, build_required_real_llm
from crypto_alpha_agent.llm.redaction import redact_text

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class LLMRuntimeError(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        super().__init__(message)


class _RuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class LLMHealthCheckTask(_RuntimeModel):
    command: str = Field(min_length=1)
    schema_name: Literal["LLMHealthCheckResult"] = "LLMHealthCheckResult"
    objective: str = Field(
        default=(
            "Return a strict JSON health response proving structured output support "
            "for the LLM-native crypto research runtime."
        ),
        min_length=1,
    )
    required_capabilities: tuple[str, ...] = ("json_schema", "research_only")


class LLMHealthCheckResult(_RuntimeModel):
    status: Literal["ok"]
    schema_name: Literal["LLMHealthCheckResult"]
    capabilities: list[str] = Field(min_length=2)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class RealLLMRuntime:
    def __init__(self, *, llm: Any, provider: Literal["real"], role: LLMRole) -> None:
        if provider != "real":
            raise LLMRuntimeError("fake_llm_not_allowed", "Product runtime requires a real LLM provider.")
        self.llm = llm
        self.provider = provider
        self.role = role
        self.last_health: LLMHealthCheckResult | None = None

    def health_check(self, *, command: str) -> LLMHealthCheckResult:
        raw_response = self.llm(LLMHealthCheckTask(command=command))
        result = parse_structured_llm_json(raw_response, LLMHealthCheckResult)
        required = {"json_schema", "research_only"}
        if not required.issubset(set(result.capabilities)):
            raise LLMRuntimeError(
                "llm_health_missing_capability",
                "LLM health check did not report required capabilities.",
            )
        self.last_health = result
        return result

    def structured_call(self, task: BaseModel, output_model: type[StructuredModel]) -> StructuredModel:
        return parse_structured_llm_json(self.llm(task), output_model)

    def metadata(self) -> dict[str, Any]:
        settings = getattr(self.llm, "settings", None)
        metadata: dict[str, Any] = {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": self.role,
        }
        model = getattr(settings, "model", None)
        if model:
            metadata["llm_model"] = str(model)
        if self.last_health is not None:
            metadata["llm_health_schema"] = self.last_health.schema_name
        return metadata


def build_required_real_llm_runtime(
    *,
    env_file: str | Path | None = Path(".env"),
    role: LLMRole = "research",
) -> RealLLMRuntime:
    try:
        llm = build_required_real_llm(env_file=env_file, role=role)
    except ValueError as exc:
        raise LLMRuntimeError(
            "llm_configuration_missing",
            redact_text(str(exc)),
        ) from None
    return RealLLMRuntime(llm=llm, provider="real", role=role)


def parse_structured_llm_json(raw_response: Any, output_model: type[StructuredModel]) -> StructuredModel:
    if not isinstance(raw_response, str):
        raise LLMRuntimeError("invalid_llm_response_type", "LLM response must be a string.")
    try:
        payload = json.loads(raw_response, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        digest = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()[:12]
        raise LLMRuntimeError("invalid_json", f"LLM response was not valid JSON: sha256={digest}") from exc
    try:
        return output_model.model_validate(payload)
    except ValidationError as exc:
        raise LLMRuntimeError("schema_validation_failed", redact_text(str(exc))) from None


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
```

- [ ] **Step 4: Add required builder in config**

Modify `src/crypto_alpha_agent/config.py`:

```python
def build_required_real_llm(
    *,
    env_file: str | Path | None = Path(".env"),
    role: LLMRole = "research",
    env: dict[str, str] | None = None,
):
    settings = build_configured_llm_settings(
        env_file=env_file,
        role=role,
        required=True,
        env=env,
    )
    if settings is None:
        raise ValueError("Real LLM is required but settings were not built.")
    from crypto_alpha_agent.llm.responses import OpenAIResponsesAdapter

    return OpenAIResponsesAdapter(settings)
```

Keep `build_configured_llm_settings` for low-level configuration tests. Product
CLI code will stop importing `build_configured_llm`.

- [ ] **Step 5: Export runtime API**

Modify `src/crypto_alpha_agent/llm/__init__.py`:

```python
from crypto_alpha_agent.llm.runtime import (
    LLMHealthCheckResult,
    LLMHealthCheckTask,
    LLMRuntimeError,
    RealLLMRuntime,
    build_required_real_llm_runtime,
    parse_structured_llm_json,
)
```

Add these names to `__all__`.

- [ ] **Step 6: Run runtime tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_native_runtime.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit runtime layer**

```bash
git add src/crypto_alpha_agent/config.py src/crypto_alpha_agent/llm/__init__.py src/crypto_alpha_agent/llm/runtime.py tests/test_llm_native_runtime.py
git commit -m "feat: add required llm runtime"
```

## Task 2: Add CLI Global LLM Gate

**Files:**

- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/llm/responses.py`
- Test: `tests/test_cli_llm_native_gate.py`

- [ ] **Step 1: Write failing CLI gate tests**

Add `tests/test_cli_llm_native_gate.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.llm.runtime import LLMRuntimeError


class PassingRuntime:
    def __init__(self) -> None:
        self.health_commands = []

    def health_check(self, *, command: str):
        self.health_commands.append(command)
        return object()

    def metadata(self):
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": "research",
            "llm_model": "test-real-model",
            "llm_health_schema": "LLMHealthCheckResult",
        }


def test_help_bypasses_llm_gate(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "crypto-alpha-agent" in captured.out


def test_llm_health_check_command_bypasses_global_gate(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    runtime = PassingRuntime()
    monkeypatch.setattr("crypto_alpha_agent.cli.build_required_real_llm_runtime", lambda role="research": runtime)

    exit_code = main(["llm-health-check"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["command"] == "llm-health-check"
    assert payload["llm_provider"] == "real"
    assert runtime.health_commands == ["llm-health-check"]


def test_product_command_fails_closed_before_side_effects(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    def fail_runtime(role="research"):
        raise LLMRuntimeError("llm_configuration_missing", "missing test config")

    monkeypatch.setattr("crypto_alpha_agent.cli.build_required_real_llm_runtime", fail_runtime)
    db_path = tmp_path / "research.sqlite"

    exit_code = main(["ingest", "--offline-check", "--db", str(db_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert payload["command"] == "ingest"
    assert payload["reason_code"] == "llm_configuration_missing"
    assert payload["side_effects_started"] is False
    assert not db_path.exists()


def test_offline_only_argument_is_removed(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["plan-experiments", "--db", str(tmp_path / "x.sqlite"), "--memory", str(tmp_path / "m.jsonl"), "--offline-only"])
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "unrecognized arguments: --offline-only" in captured.err
```

- [ ] **Step 2: Run failing CLI gate tests**

Run:

```bash
uv run --extra dev pytest tests/test_cli_llm_native_gate.py -q
```

Expected: FAIL because `llm-health-check` and the global LLM gate do not exist.

- [ ] **Step 3: Add CLI version and health command**

In `src/crypto_alpha_agent/cli.py`, import runtime:

```python
from crypto_alpha_agent.llm.runtime import (
    LLMRuntimeError,
    RealLLMRuntime,
    build_required_real_llm_runtime,
)
```

Add a version action in `build_parser()`:

```python
parser.add_argument("--version", action="version", version="crypto-alpha-agent 0.1.0")
```

Add the diagnostic command before product commands:

```python
llm_health_parser = subparsers.add_parser(
    "llm-health-check",
    help="Run the required real LLM structured health check.",
)
llm_health_parser.set_defaults(handler=_handle_llm_health_check, llm_gate_bypass=True)
```

- [ ] **Step 4: Replace main with fail-closed global gate**

Update `main()`:

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "llm_gate_bypass", False):
        payload = args.handler(args)
        print(json.dumps(payload, sort_keys=True))
        return int(payload.get("exit_code", 0) or 0)
    try:
        runtime = build_required_real_llm_runtime(role=_llm_role_for_command(args.command))
        runtime.health_check(command=args.command)
    except LLMRuntimeError as exc:
        payload = _llm_preflight_failure_payload(args.command, exc)
        print(json.dumps(payload, sort_keys=True))
        return 2
    args.llm_runtime = runtime
    payload = args.handler(args)
    print(json.dumps(payload, sort_keys=True))
    return int(payload.get("exit_code", 0) or 0)
```

Add helpers:

```python
def _llm_role_for_command(command: str) -> LLMRole:
    if command in {"plan-experiments", "schedule"}:
        return "planning"
    if command in {"evidence-report", "governance-report", "historical-bootstrap", "rollout-review"}:
        return "summary"
    return "research"


def _llm_preflight_failure_payload(command: str, exc: LLMRuntimeError) -> dict[str, Any]:
    return {
        "command": command,
        "exit_code": 2,
        "reason_code": exc.reason_code,
        "llm_required": True,
        "llm_provider": "unavailable",
        "side_effects_started": False,
        "uses_real_capital": False,
        "live_order_routing": False,
        "failure": redact_text(str(exc)),
    }
```

- [ ] **Step 5: Add health-check handler**

Add to `src/crypto_alpha_agent/cli.py`:

```python
def _handle_llm_health_check(_args: argparse.Namespace) -> dict[str, Any]:
    try:
        runtime = build_required_real_llm_runtime(role="research")
        health = runtime.health_check(command="llm-health-check")
    except LLMRuntimeError as exc:
        return {
            "command": "llm-health-check",
            "exit_code": 2,
            "reason_code": exc.reason_code,
            "llm_required": True,
            "llm_provider": "unavailable",
            "side_effects_started": False,
            "uses_real_capital": False,
            "live_order_routing": False,
            "failure": redact_text(str(exc)),
        }
    return {
        "command": "llm-health-check",
        "exit_code": 0,
        "llm_required": True,
        "health": health.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
        **runtime.metadata(),
    }
```

- [ ] **Step 6: Remove offline-only parser helper**

Delete the function named `_add_offline_only_llm_argument` from
`src/crypto_alpha_agent/cli.py`.

Remove all calls to `_add_offline_only_llm_argument` and remove the
`--offline-only` block from `plan-experiments`.

- [ ] **Step 7: Remove `_resolve_llm_for_cli`**

Delete `_resolve_llm_for_cli`. Product handlers will read:

```python
runtime: RealLLMRuntime = args.llm_runtime
```

- [ ] **Step 8: Add response hint for health task**

In `src/crypto_alpha_agent/llm/responses.py`, add before the default hint:

```python
if task_type == "LLMHealthCheckTask":
    return (
        "Schema instructions: return exactly one LLMHealthCheckResult JSON object "
        "with status=\"ok\", schema_name=\"LLMHealthCheckResult\", capabilities "
        "including json_schema and research_only, uses_real_capital=false, and "
        "live_order_routing=false. Do not include extra fields."
    )
```

- [ ] **Step 9: Run CLI gate tests**

Run:

```bash
uv run --extra dev pytest tests/test_cli_llm_native_gate.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit CLI gate**

```bash
git add src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/llm/responses.py tests/test_cli_llm_native_gate.py
git commit -m "feat: require llm runtime for cli"
```

## Task 3: Add Shared LLM Judgement Schemas

**Files:**

- Create: `src/crypto_alpha_agent/pipeline/llm_judgements.py`
- Modify: `src/crypto_alpha_agent/llm/responses.py`
- Test: `tests/test_llm_native_judgements.py`

- [ ] **Step 1: Write failing judgement tests**

Add `tests/test_llm_native_judgements.py`:

```python
from __future__ import annotations

import json

import pytest

from crypto_alpha_agent.llm.runtime import RealLLMRuntime
from crypto_alpha_agent.pipeline.llm_judgements import (
    DataReadinessJudgement,
    SourceResearchJudgement,
    run_source_research_judgement,
)
from tests.test_llm_native_runtime import CapturingLLM


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
    runtime = RealLLMRuntime(llm=llm, provider="real", role="research")

    result = run_source_research_judgement(
        runtime,
        command="source-probe",
        source_health={"target_id": "binance_usdm_open_interest_history"},
        evidence_refs=["source-health:binance_usdm_open_interest_history"],
    )

    assert result.decision == "add_data"
    assert result.evidence_refs == ["source-health:binance_usdm_open_interest_history"]


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
```

- [ ] **Step 2: Run failing judgement tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_native_judgements.py -q
```

Expected: FAIL because `pipeline.llm_judgements` does not exist.

- [ ] **Step 3: Implement judgement module**

Create `src/crypto_alpha_agent/pipeline/llm_judgements.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.llm.runtime import RealLLMRuntime

JudgementDecision = Literal[
    "research_ready",
    "keep_collecting",
    "add_data",
    "redesign_validator",
    "stop",
    "owner_decision_review",
    "blocked",
]


class _JudgementModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class _EvidenceBackedJudgement(_JudgementModel):
    decision: JudgementDecision
    rationale: str = Field(min_length=1, max_length=1600)
    evidence_refs: list[str] = Field(min_length=1, max_length=32)
    next_actions: list[str] = Field(min_length=1, max_length=12)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    def validate_refs(self, allowed_refs: set[str]) -> None:
        unknown = sorted(set(self.evidence_refs) - allowed_refs)
        if unknown:
            raise ValueError("unknown evidence refs: " + ", ".join(unknown))


class SourceResearchJudgement(_EvidenceBackedJudgement):
    schema_name: Literal["SourceResearchJudgement"]


class DataReadinessJudgement(_EvidenceBackedJudgement):
    schema_name: Literal["DataReadinessJudgement"]
    missing_fields: list[str] = Field(default_factory=list, max_length=24)


class LLMHypothesisSet(_EvidenceBackedJudgement):
    schema_name: Literal["LLMHypothesisSet"]
    hypotheses: list[dict[str, Any]] = Field(default_factory=list, max_length=8)
    critique: list[str] = Field(default_factory=list, max_length=12)


class EvidenceRunInterpretation(_EvidenceBackedJudgement):
    schema_name: Literal["EvidenceRunInterpretation"]
    blocked_reason_review: list[str] = Field(default_factory=list, max_length=16)
    next_experiment: dict[str, Any] | None = None


class GovernanceReview(_EvidenceBackedJudgement):
    schema_name: Literal["GovernanceReview"]
    family_actions: dict[str, JudgementDecision] = Field(default_factory=dict)


class BootstrapInterpretation(_EvidenceBackedJudgement):
    schema_name: Literal["BootstrapInterpretation"]
    historical_is_profit_proof: Literal[False] = False


class RolloutReadinessNarrative(_EvidenceBackedJudgement):
    schema_name: Literal["RolloutReadinessNarrative"]
    live_execution_enabled: Literal[False] = False


class RuntimeCommandJudgement(_EvidenceBackedJudgement):
    schema_name: Literal["RuntimeCommandJudgement"]


class LLMJudgementTask(_JudgementModel):
    command: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    facts: dict[str, Any]
    evidence_refs: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)


def run_source_research_judgement(
    runtime: RealLLMRuntime,
    *,
    command: str,
    source_health: dict[str, Any],
    evidence_refs: list[str],
) -> SourceResearchJudgement:
    task = LLMJudgementTask(
        command=command,
        schema_name="SourceResearchJudgement",
        objective="Judge whether the probed source is useful for research.",
        facts={"source_health": source_health},
        evidence_refs=evidence_refs,
        constraints=_default_constraints(),
    )
    judgement = runtime.structured_call(task, SourceResearchJudgement)
    judgement.validate_refs(set(evidence_refs))
    return judgement


def run_data_readiness_judgement(
    runtime: RealLLMRuntime,
    *,
    command: str,
    ingestion_summary: dict[str, Any],
    evidence_refs: list[str],
) -> DataReadinessJudgement:
    task = LLMJudgementTask(
        command=command,
        schema_name="DataReadinessJudgement",
        objective="Judge whether ingested data is ready for research use.",
        facts={"ingestion_summary": ingestion_summary},
        evidence_refs=evidence_refs,
        constraints=_default_constraints(),
    )
    judgement = runtime.structured_call(task, DataReadinessJudgement)
    judgement.validate_refs(set(evidence_refs))
    return judgement


def run_runtime_command_judgement(
    runtime: RealLLMRuntime,
    *,
    command: str,
    facts: dict[str, Any],
    evidence_refs: list[str],
    objective: str,
) -> RuntimeCommandJudgement:
    task = LLMJudgementTask(
        command=command,
        schema_name="RuntimeCommandJudgement",
        objective=objective,
        facts=facts,
        evidence_refs=evidence_refs,
        constraints=_default_constraints(),
    )
    judgement = runtime.structured_call(task, RuntimeCommandJudgement)
    judgement.validate_refs(set(evidence_refs))
    return judgement


def _default_constraints() -> list[str]:
    return [
        "Use only supplied facts and evidence_refs.",
        "Do not request live capital.",
        "Do not request live order routing.",
        "Do not request wallet keys or premium infrastructure.",
        "Return only the requested JSON schema.",
    ]
```

- [ ] **Step 4: Add response hint for judgement task**

In `src/crypto_alpha_agent/llm/responses.py`, add:

```python
if task_type == "LLMJudgementTask":
    return (
        "Schema instructions: return exactly one JSON object matching schema_name "
        "from the task. Include decision, rationale, evidence_refs using only refs "
        "from the task, next_actions, uses_real_capital=false, and "
        "live_order_routing=false. For BootstrapInterpretation include "
        "historical_is_profit_proof=false. For RolloutReadinessNarrative include "
        "live_execution_enabled=false. Do not include extra fields."
    )
```

- [ ] **Step 5: Run judgement tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_native_judgements.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit judgement schemas**

```bash
git add src/crypto_alpha_agent/pipeline/llm_judgements.py src/crypto_alpha_agent/llm/responses.py tests/test_llm_native_judgements.py
git commit -m "feat: add llm judgement schemas"
```

## Task 4: Remove Planner Fallback

**Files:**

- Modify: `src/crypto_alpha_agent/pipeline/experiment_planner.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `tests/test_ai_experiment_planner.py`
- Modify: `tests/test_cli_research_loop.py`

- [ ] **Step 1: Write failing planner requirement test**

In `tests/test_ai_experiment_planner.py`, add:

```python
def test_plan_experiments_requires_llm(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    with pytest.raises(TypeError, match="llm"):
        plan_next_experiments(
            db_path=db_path,
            memory_path=memory_path,
            current_capital_usd=300.0,
        )
```

- [ ] **Step 2: Run focused planner test**

Run:

```bash
uv run --extra dev pytest tests/test_ai_experiment_planner.py::test_plan_experiments_requires_llm -q
```

Expected: FAIL because `llm` is currently optional.

- [ ] **Step 3: Change planner signature**

In `src/crypto_alpha_agent/pipeline/experiment_planner.py`, change:

```python
def plan_next_experiments(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    strategy_family: str | None = None,
    max_proposals: int = 3,
    current_capital_usd: float = 300.0,
    llm: PlannerLLM,
    allow_stopped_family: bool = False,
) -> ExperimentPlannerResult:
```

Remove `offline_only` from `ExperimentPlannerInput` and from all constructor
calls.

- [ ] **Step 4: Delete deterministic fallback branch**

In `plan_next_experiments`, replace the current conditional branch that chooses
between `_plan_with_llm` and `_fallback_proposals`
with:

```python
result = _plan_with_llm(
    planner_input,
    batch_id=batch_id,
    llm=llm,
    validation_evidence=validation_evidence,
    paper_evidence=paper_evidence,
    degraded_families=degraded_families,
    blocked_parameter_sets=blocked_parameter_sets,
    duplicate_signatures=duplicate_signatures,
    research_context=research_context,
)
```

Keep `_fallback_proposals` only if deterministic unit tests import it directly.
If no direct import exists, delete `_fallback_proposals` and tests that assert
offline planner success.

- [ ] **Step 5: Update CLI plan handler**

In `_handle_plan_experiments`, replace runtime resolution with:

```python
runtime: RealLLMRuntime = args.llm_runtime
try:
    result = plan_next_experiments(
        db_path=args.db,
        memory_path=args.memory,
        strategy_family=args.strategy_family,
        max_proposals=args.max_proposals,
        current_capital_usd=args.current_capital_usd,
        llm=runtime.llm,
    )
except LLMProviderError as exc:
    args.parser.error(str(exc))
    raise AssertionError("argparse parser.error should exit") from exc
```

Add `**runtime.metadata()` to the payload and remove `llm_metadata`.

- [ ] **Step 6: Delete offline planner tests**

Remove or rewrite tests whose purpose is deterministic product success, including:

```python
test_plan_experiments_offline_only_skips_configured_llm
```

Replace with CLI parser tests asserting `--offline-only` is rejected.

- [ ] **Step 7: Run planner tests**

Run:

```bash
uv run --extra dev pytest tests/test_ai_experiment_planner.py tests/test_cli_llm_native_gate.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit planner conversion**

```bash
git add src/crypto_alpha_agent/pipeline/experiment_planner.py src/crypto_alpha_agent/cli.py tests/test_ai_experiment_planner.py tests/test_cli_llm_native_gate.py
git commit -m "feat: require llm experiment planning"
```

## Task 5: Convert Source Probe And Ingest To LLM-Native Commands

**Files:**

- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `tests/test_source_probe.py`
- Modify: `tests/test_cli_ingest.py`

- [ ] **Step 1: Write source-probe CLI judgement test**

In `tests/test_source_probe.py`, add:

```python
def test_source_probe_payload_requires_llm_judgement(monkeypatch, tmp_path, capsys):
    runtime = _runtime_with_judgement(
        {
            "schema_name": "SourceResearchJudgement",
            "decision": "add_data",
            "rationale": "The target is listed but needs a live canary.",
            "evidence_refs": ["source-health:binance_usdm_open_interest_history"],
            "next_actions": ["Run source-probe with network access."],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )
    monkeypatch.setattr("crypto_alpha_agent.cli.build_required_real_llm_runtime", lambda role="research": runtime)

    exit_code = main(["source-probe", "--list-targets"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["llm_provider"] == "real"
    assert payload["llm_judgement"]["schema_name"] == "SourceResearchJudgement"
```

Define `_runtime_with_judgement` in the test module using `RealLLMRuntime` and
`CapturingLLM` from `tests/test_llm_native_runtime.py`.

- [ ] **Step 2: Write ingest CLI judgement test**

In `tests/test_cli_ingest.py`, add:

```python
def test_ingest_offline_check_requires_llm_data_readiness(monkeypatch, tmp_path, capsys):
    runtime = _runtime_with_judgement(
        {
            "schema_name": "DataReadinessJudgement",
            "decision": "add_data",
            "rationale": "The store exists but contains no research rows.",
            "evidence_refs": ["ingest:offline_check"],
            "missing_fields": ["market_candle", "funding_rate"],
            "next_actions": ["Ingest CCXT OHLCV and funding history."],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )
    monkeypatch.setattr("crypto_alpha_agent.cli.build_required_real_llm_runtime", lambda role="research": runtime)
    db_path = tmp_path / "research.sqlite"

    exit_code = main(["ingest", "--offline-check", "--db", str(db_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["llm_judgement"]["schema_name"] == "DataReadinessJudgement"
    assert payload["llm_provider"] == "real"
```

- [ ] **Step 3: Run failing source/ingest tests**

Run:

```bash
uv run --extra dev pytest tests/test_source_probe.py::test_source_probe_payload_requires_llm_judgement tests/test_cli_ingest.py::test_ingest_offline_check_requires_llm_data_readiness -q
```

Expected: FAIL because handlers do not call judgement helpers.

- [ ] **Step 4: Add source-probe judgement to handler**

In `_handle_source_probe`, after building the target list or probe result, call:

```python
runtime: RealLLMRuntime = args.llm_runtime
evidence_refs = [f"source-health:{item['target_id']}" for item in targets_payload]
judgement = run_source_research_judgement(
    runtime,
    command="source-probe",
    source_health={"targets": targets_payload},
    evidence_refs=evidence_refs or ["source-health:list-targets"],
)
```

For a single probe result, use:

```python
evidence_refs = [f"source-health:{result.target_id}"]
```

Add to returned payload:

```python
"llm_judgement": judgement.model_dump(mode="json"),
**runtime.metadata(),
```

- [ ] **Step 5: Add ingest judgement to handler**

In `_handle_ingest`, after deterministic payload construction and before
return:

```python
runtime: RealLLMRuntime = args.llm_runtime
evidence_refs = ["ingest:offline_check"] if ingestion is None else [f"ingest:{payload['mode']}"]
judgement = run_data_readiness_judgement(
    runtime,
    command="ingest",
    ingestion_summary=payload,
    evidence_refs=evidence_refs,
)
payload["llm_judgement"] = judgement.model_dump(mode="json")
payload.update(runtime.metadata())
```

- [ ] **Step 6: Run source/ingest tests**

Run:

```bash
uv run --extra dev pytest tests/test_source_probe.py tests/test_cli_ingest.py -q
```

Expected: PASS after updating older assertions to expect `llm_provider=real`
where CLI product commands are exercised.

- [ ] **Step 7: Commit source/ingest conversion**

```bash
git add src/crypto_alpha_agent/cli.py tests/test_source_probe.py tests/test_cli_ingest.py
git commit -m "feat: require llm source and ingest judgements"
```

## Task 6: Convert Research Loop And Evidence Reports

**Files:**

- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/agents/report_summarizer.py`
- Modify: `tests/test_cli_research_loop.py`
- Modify: `tests/test_evidence_reports.py`

- [ ] **Step 1: Write failing research-loop required LLM test**

In `tests/test_cli_research_loop.py`, update the existing LLM CLI test to remove
`--no-offline-only` and assert:

```python
assert payload["llm_provider"] == "real"
assert payload["used_fake_llm"] is False
assert payload["llm_research_result"]["accepted"] is True
```

Add a missing-runtime test that monkeypatches `build_required_real_llm_runtime`
to raise `LLMRuntimeError` and asserts `side_effects_started=false`.

- [ ] **Step 2: Write failing evidence-report summary test**

In `tests/test_evidence_reports.py`, update the report CLI LLM test to assert:

```python
assert payload["llm_provider"] == "real"
assert payload["llm_summary_accepted"] is True
```

Remove assertions that allow:

```python
payload["llm_summary_accepted"] is False
payload["llm_mode"] == "offline_only"
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_cli_research_loop.py tests/test_evidence_reports.py -q
```

Expected: FAIL because the handlers still allow no LLM.

- [ ] **Step 4: Force research-loop LLM graph**

In `_handle_research_loop`, remove `_resolve_llm_for_cli` calls. Use:

```python
runtime: RealLLMRuntime = args.llm_runtime
llm_state = build_llm_research_graph(
    runtime.llm,
    max_capital_usd=args.current_capital_usd,
).invoke(
    {
        "research_report": report,
        "memory_path": str(args.memory) if args.memory is not None else None,
        "suggest_paper_action": False,
    }
)
payload["llm_research_result"] = llm_state["llm_research_result"]
payload.update(runtime.metadata())
```

Delete the `if llm is not None` guard.

- [ ] **Step 5: Force evidence-report LLM summary**

Change `_apply_evidence_report_summary` signature:

```python
def _apply_evidence_report_summary(
    args: argparse.Namespace,
    report: Any,
    *,
    report_type: ReportType,
    runtime: RealLLMRuntime,
) -> tuple[Any, dict[str, Any]]:
```

Remove the `if llm is None` branch. Call:

```python
summary_result = summarize_evidence_report(report, report_type=report_type, llm=runtime.llm)
if not summary_result.accepted or summary_result.summary is None:
    args.parser.error("LLM evidence report summary rejected: " + ",".join(summary_result.rejected_reason_codes))
```

Update `_handle_evidence_report` to pass `runtime=args.llm_runtime` and include
`**runtime.metadata()`.

- [ ] **Step 6: Run research/report tests**

Run:

```bash
uv run --extra dev pytest tests/test_cli_research_loop.py tests/test_evidence_reports.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit research/report conversion**

```bash
git add src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/agents/report_summarizer.py tests/test_cli_research_loop.py tests/test_evidence_reports.py
git commit -m "feat: require llm research and report flows"
```

## Task 7: Convert Governance, Bootstrap, Rollout, And Memo Commands

**Files:**

- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/pipeline/governance_reports.py`
- Modify: `src/crypto_alpha_agent/pipeline/historical_bootstrap.py`
- Modify: `tests/test_governance_reports.py`
- Modify: `tests/test_historical_bootstrap.py`
- Modify: `tests/test_rollout_review.py`
- Modify: `tests/test_ai_research_memo.py`

- [ ] **Step 1: Add governance LLM judgement in CLI**

In `_handle_governance_report`, after deterministic `report` is built:

```python
runtime: RealLLMRuntime = args.llm_runtime
facts = report.model_dump(mode="json")
evidence_refs = [f"governance:{row['strategy_family']}" for row in facts.get("family_scoreboard", [])]
if not evidence_refs:
    evidence_refs = ["governance:empty-scoreboard"]
judgement = run_runtime_command_judgement(
    runtime,
    command="governance-report",
    facts=facts,
    evidence_refs=evidence_refs,
    objective="Explain the deterministic governance report without changing its actions.",
)
```

Add `llm_judgement` and runtime metadata to payload.

- [ ] **Step 2: Add bootstrap LLM judgement**

In `_handle_historical_bootstrap`, after `report` is built and before writes:

```python
runtime: RealLLMRuntime = args.llm_runtime
facts = report.model_dump(mode="json")
judgement = runtime.structured_call(
    LLMJudgementTask(
        command="historical-bootstrap",
        schema_name="BootstrapInterpretation",
        objective="Interpret bootstrap evidence while preserving that historical evidence is not profit proof.",
        facts=facts,
        evidence_refs=["bootstrap:" + report.manifest.run_id],
        constraints=[
            "historical_is_profit_proof must be false",
            "uses_real_capital must be false",
            "live_order_routing must be false",
        ],
    ),
    BootstrapInterpretation,
)
judgement.validate_refs({"bootstrap:" + report.manifest.run_id})
```

Add the judgement to payload and JSON artifact.

- [ ] **Step 3: Add rollout LLM narrative**

In `_handle_rollout_review`, after deterministic `review`:

```python
runtime: RealLLMRuntime = args.llm_runtime
facts = review.model_dump(mode="json")
judgement = runtime.structured_call(
    LLMJudgementTask(
        command="rollout-review",
        schema_name="RolloutReadinessNarrative",
        objective="Explain rollout readiness without enabling live execution.",
        facts=facts,
        evidence_refs=[f"rollout:{args.strategy_family}"],
        constraints=[
            "live_execution_enabled must be false",
            "uses_real_capital must be false",
            "live_order_routing must be false",
        ],
    ),
    RolloutReadinessNarrative,
)
judgement.validate_refs({f"rollout:{args.strategy_family}"})
```

Add the judgement to output artifacts.

- [ ] **Step 4: Add memo and expansion judgements**

For `_handle_ai_research_memo` and `_handle_expansion_prep_report`, call
`run_runtime_command_judgement` with evidence refs:

```python
["ai-research-memo:" + (args.strategy_family or "all")]
["expansion-prep:registry"]
```

Add `llm_judgement` and runtime metadata to payloads.

- [ ] **Step 5: Update tests**

For each command test, monkeypatch `build_required_real_llm_runtime` to return a
`RealLLMRuntime` backed by `CapturingLLM` with the expected schema:

```python
{
    "schema_name": "RuntimeCommandJudgement",
    "decision": "add_data",
    "rationale": "Evidence is not yet sufficient.",
    "evidence_refs": ["governance:empty-scoreboard"],
    "next_actions": ["Collect forward paper observations."],
    "uses_real_capital": False,
    "live_order_routing": False
}
```

Use `BootstrapInterpretation` and `RolloutReadinessNarrative` schemas for the
bootstrap and rollout tests.

- [ ] **Step 6: Run converted command tests**

Run:

```bash
uv run --extra dev pytest tests/test_governance_reports.py tests/test_historical_bootstrap.py tests/test_rollout_review.py tests/test_ai_research_memo.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit governance/bootstrap/rollout conversion**

```bash
git add src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/pipeline/governance_reports.py src/crypto_alpha_agent/pipeline/historical_bootstrap.py tests/test_governance_reports.py tests/test_historical_bootstrap.py tests/test_rollout_review.py tests/test_ai_research_memo.py
git commit -m "feat: require llm review judgements"
```

## Task 8: Convert Evidence Run And Remaining Product Commands

**Files:**

- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `src/crypto_alpha_agent/pipeline/evidence_runner.py`
- Modify: `tests/test_evidence_runner.py`
- Modify: `tests/test_scheduler_cli.py`
- Modify: CLI test files that exercise `scan`, `research`, `backtest`,
  `paper`, `report`, `replay`, `paper-sim-loop`, and
  `expansion-prep-report`.

- [x] **Step 1: Add evidence-run LLM interpretation**

In `_handle_evidence_run`, after the `report` value is returned by
`run_daily_evidence_pipeline` and before writing daily/weekly reports:

```python
runtime: RealLLMRuntime = args.llm_runtime
report_facts = report.model_dump(mode="json")
evidence_refs = [f"evidence-run:{run_id}", *[f"step:{step.name}" for step in report.steps]]
interpretation = runtime.structured_call(
    LLMJudgementTask(
        command="evidence-run",
        schema_name="EvidenceRunInterpretation",
        objective="Interpret evidence-run results and propose the next bounded experiment.",
        facts=report_facts,
        evidence_refs=evidence_refs,
        constraints=[
            "Use only supplied evidence_refs",
            "uses_real_capital must be false",
            "live_order_routing must be false",
        ],
    ),
    EvidenceRunInterpretation,
)
interpretation.validate_refs(set(evidence_refs))
```

Add `llm_interpretation` and runtime metadata to the payload and manifest.

- [x] **Step 2: Treat evidence-run LLM failure as command failure**

Wrap the interpretation call in the existing `try` block. If it raises
`LLMRuntimeError`, call `_finalize_evidence_run_failure` with:

```python
reason_code=exc.reason_code
failure=redacted_failure(str(exc), secrets=_evidence_run_secret_values(args))
write_artifacts=False
```

This preserves the confirmed preflight no-side-effect rule and avoids success
artifacts for failed interpretation.

- [x] **Step 3: Add LLM judgement to schedule**

In `_handle_schedule`, after `plan` is returned by `build_daily_schedule_plan`,
call `run_runtime_command_judgement` with:

```python
facts=plan.model_dump(mode="json")
evidence_refs=[f"schedule:{plan.run_id}"]
objective="Review the planned evidence-run schedule before operator use."
```

Add `llm_judgement` and runtime metadata to the returned plan payload.

- [x] **Step 4: Convert legacy smoke commands**

For `_handle_scan`, `_handle_research`, `_handle_backtest`, `_handle_paper`,
`_handle_report`, `_handle_replay`, and `_handle_paper_sim_loop`, add a runtime
judgement before returning:

```python
runtime: RealLLMRuntime = args.llm_runtime
judgement = run_runtime_command_judgement(
    runtime,
    command="scan",
    facts=payload,
    evidence_refs=["runtime:scan"],
    objective="Review this command output under the LLM-native runtime policy.",
)
payload["llm_judgement"] = judgement.model_dump(mode="json")
payload.update(runtime.metadata())
```

Use command-specific refs such as `runtime:report`, `runtime:replay`, and
`paper-sim-loop:<strategy_family>`.

- [x] **Step 5: Update tests for remaining product commands**

For each affected CLI test, monkeypatch `build_required_real_llm_runtime` to
return a `RealLLMRuntime` with a `RuntimeCommandJudgement` response unless the
test intentionally checks missing LLM failure.

Each product command payload assertion should include:

```python
assert payload["llm_provider"] == "real"
assert payload["used_fake_llm"] is False
assert payload["llm_judgement"] or payload["llm_interpretation"]
```

- [x] **Step 6: Run broad CLI tests**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_runner.py tests/test_scheduler_cli.py tests/test_cli_research_loop.py tests/test_cli_ingest.py tests/test_source_probe.py tests/test_evidence_reports.py -q
```

Expected: PASS.

- [x] **Step 7: Commit remaining command conversion**

```bash
git add src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/pipeline/evidence_runner.py tests
git commit -m "feat: require llm for product commands"
```

## Task 9: Enforce Real LLM Acceptance Policy

**Files:**

- Modify: `pyproject.toml`
- Modify: `tests/llm_integration_policy.py`
- Modify: `tests/test_real_llm_integration_policy.py`
- Modify: `tests/test_real_llm_test_policy_contract.py`

- [x] **Step 1: Add marker**

In `pyproject.toml`, add:

```toml
"core_acceptance: product runtime tests that must use the configured real LLM",
```

- [x] **Step 2: Replace skip helper**

In `tests/llm_integration_policy.py`, replace `configured_llm_settings_or_skip`
with:

```python
def configured_llm_settings_or_fail(role: LLMRole = "research") -> LLMSettings:
    settings = build_configured_llm_settings(role=role, required=True)
    assert settings is not None
    return settings
```

Remove CI skip behavior. Keep retry logic for transient provider failures, but
the final outcome remains test failure.

- [x] **Step 3: Update real LLM tests**

In `tests/test_real_llm_integration_policy.py`:

- Replace `configured_llm_settings_or_skip` with `configured_llm_settings_or_fail`.
- Remove `enable_real_llm_cli_for_pytest`.
- Remove `--no-offline-only`.
- Add `@pytest.mark.core_acceptance` to every real LLM product test.
- Add real LLM tests for:
  - `llm-health-check`
  - `source-probe --list-targets`
  - `ingest --offline-check`
  - `governance-report`
  - `historical-bootstrap`
  - `rollout-review`

Each test must assert:

```python
assert payload["llm_provider"] == "real"
assert payload["used_fake_llm"] is False
```

- [x] **Step 4: Update policy contract**

In `tests/test_real_llm_test_policy_contract.py`, add:

```python
def test_core_acceptance_marker_is_registered() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "core_acceptance: product runtime tests that must use the configured real LLM" in pyproject
```

Add a source scan that fails if core acceptance tests call
`configured_llm_settings_or_skip`.

- [x] **Step 5: Run real LLM policy tests**

Run:

```bash
uv run --extra dev pytest tests/test_real_llm_test_policy_contract.py tests/llm_integration_policy.py -q
```

Expected: PASS for policy contract. `tests/llm_integration_policy.py` is a
helper module and may report no collected tests.

- [x] **Step 6: Run real LLM acceptance tests**

Run:

```bash
uv run --extra dev pytest tests/test_real_llm_integration_policy.py -q
```

Expected: PASS only when real LLM configuration is valid. Missing key, timeout,
provider failure, invalid JSON, schema failure, guard rejection, fake LLM usage,
or missing real metadata fails the test run.

- [x] **Step 7: Commit real LLM policy**

```bash
git add pyproject.toml tests/llm_integration_policy.py tests/test_real_llm_integration_policy.py tests/test_real_llm_test_policy_contract.py
git commit -m "test: require real llm acceptance"
```

## Task 10: Update Documentation

**Files:**

- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Add: `docs/goals/phase-reports/2026-05-24-llm-native-runtime-completion-report.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Update runbook**

Replace sections that say real LLM tests are optional or skipped with:

```markdown
The product runtime is LLM-native. Every product CLI command requires a
configured real LLM and a passing structured health check before business work
begins. The only bypasses are `llm-health-check`, `--help`, and `--version`.

Core acceptance tests call the configured real LLM and fail when credentials,
provider availability, JSON schema compliance, or guard validation fail.
```

Remove examples using `--offline-only` or `--no-offline-only`.

- [ ] **Step 2: Update roadmap**

Add a new section:

```markdown
## LLM-Native Runtime

The project no longer treats LLM usage as optional for product commands.
Deterministic code remains the source of calculation, schema validation, cost
modeling, risk limits, and audit logs, but product success requires real LLM
judgement plus deterministic guard validation.
```

- [ ] **Step 3: Update completion state**

In `docs/goals/project-completion-state.md`, add a current state note:

```markdown
The prior Phase 13 completion state described a deterministic evidence factory.
The active next project line changes the runtime target: product commands must
be LLM-native and must not succeed through deterministic-only fallback.
```

- [ ] **Step 4: Add phase report**

Create `docs/goals/phase-reports/2026-05-24-llm-native-runtime-completion-report.md` with:

```markdown
# LLM-Native Runtime Completion Report - 2026-05-24

## Objective

Make the real configured LLM a required participant in every product command and
remove deterministic-only product success paths.

## Safety

This phase does not enable live trading, wallet keys, exchange order routing,
MEV, premium RPC, private infrastructure, or speed-edge strategies.

## Verification

- `uv run --extra dev pytest tests/test_llm_native_runtime.py tests/test_cli_llm_native_gate.py tests/test_llm_native_judgements.py -q`
- `uv run --extra dev pytest tests/test_real_llm_integration_policy.py -q`
- `uv run --extra dev pytest -q`
- `uv run --extra dev ruff check .`
- `git diff --check`
```

Update the verification list with actual results after implementation.

- [ ] **Step 5: Update documentation contract tests**

In `tests/test_documentation_contract.py`, add assertions that:

- `docs/runbook.md` mentions `llm-health-check`.
- `docs/runbook.md` does not mention `--offline-only`.
- `docs/roadmap.md` mentions `LLM-Native Runtime`.
- The LLM-native design spec path exists.

- [ ] **Step 6: Run docs tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit docs**

```bash
git add docs/runbook.md docs/roadmap.md docs/goals/project-completion-state.md docs/goals/phase-reports/2026-05-24-llm-native-runtime-completion-report.md tests/test_documentation_contract.py
git commit -m "docs: document llm-native runtime"
```

## Task 11: Final Verification

**Files:**

- No planned code changes.

- [ ] **Step 1: Run focused LLM-native tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_native_runtime.py tests/test_cli_llm_native_gate.py tests/test_llm_native_judgements.py -q
```

Expected: PASS.

- [ ] **Step 2: Run real LLM acceptance**

Run:

```bash
uv run --extra dev pytest tests/test_real_llm_integration_policy.py -q
```

Expected: PASS with valid real LLM credentials. Failure is blocking.

- [ ] **Step 3: Run full regression**

Run:

```bash
uv run --extra dev pytest -q
```

Expected: PASS. Real LLM failures are not skipped.

- [ ] **Step 4: Run lint**

Run:

```bash
uv run --extra dev ruff check .
```

Expected: PASS.

- [ ] **Step 5: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 6: Check for optional LLM product paths**

Run:

```bash
rg -n "offline_only|--offline-only|--no-offline-only|llm is None|llm=None|required=False|skip\\(\"real LLM|deterministic local mode|offline_no_config|pytest_offline_default" src tests docs
```

Expected: no product-path matches. Matches are allowed only in historical phase
reports or design documents that describe removed behavior.

- [ ] **Step 7: Check git status**

Run:

```bash
git status --short
```

Expected: clean or only intentional final documentation edits.

- [ ] **Step 8: Record verification results and commit**

If Task 11 changed the completion report with actual verification results:

```bash
git add docs/goals/phase-reports/2026-05-24-llm-native-runtime-completion-report.md
git commit -m "docs: record llm-native runtime verification"
```

## Self-Review Checklist

- Spec requirement "all CLI commands require real LLM except health/help/version" is covered by Tasks 1, 2, 5, 6, 7, and 8.
- Spec requirement "delete optional LLM and deterministic fallback" is covered by Tasks 2, 4, and 11.
- Spec requirement "command-specific LLM judgement" is covered by Tasks 3, 5, 6, 7, and 8.
- Spec requirement "real LLM acceptance tests fail closed" is covered by Task 9.
- Spec requirement "deterministic modules remain as tools and guards" is preserved by Tasks 4 through 8 because validators, reports, ledgers, cost model, and risk code remain deterministic but are wrapped by LLM-native CLI flows.
- Spec requirement "docs updated" is covered by Task 10.
