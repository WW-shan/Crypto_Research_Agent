# LLM-Native Runtime Design

## Objective

Convert the project from an evidence factory with optional LLM enhancement into
an LLM-native crypto research agent.

The product rule is:

```text
No real LLM, no product runtime.
No valid structured LLM output, no product runtime.
Deterministic code computes, validates, constrains, and records.
Research judgement must involve the real LLM.
```

This design intentionally removes product paths that can run without a real LLM.
The goal is not to add a thin LLM health check in front of the old deterministic
flows. The goal is to make the real LLM a required participant in every product
command and complete research workflow.

## Confirmed Owner Decisions

- LLM is a core dependency, not an optional enhancer.
- Core business flows must be tested with a real LLM end to end.
- Ordinary unit tests may use fake LLMs only for isolated parser, schema, guard,
  redaction, cost, validator, and other local logic tests.
- Product CLI commands must not use fake LLMs.
- Product CLI commands must not use deterministic fallback when the LLM is
  missing or invalid.
- All CLI commands require real LLM runtime, except:
  - `llm-health-check`
  - `--help`
  - `--version`
- LLM readiness must be a structured JSON schema check.
- Missing credentials, connection failure, timeout, non-JSON output, schema
  failure, guard rejection, fake LLM usage, or missing real-provider evidence is
  a blocking failure.
- When the preflight LLM check fails, the command exits nonzero before opening a
  database, making a market-data network request, writing a file, or producing a
  success artifact.

## Non-Goals

- Do not enable live trading.
- Do not load wallet keys.
- Do not submit exchange orders.
- Do not add MEV, mempool, bridge-race, flash-loan, premium-RPC, private-node,
  colocation, or speed-edge strategy paths.
- Do not let the LLM override schema validation, validators, cost model, risk
  guard, charter guard, or rollout gates.
- Do not claim historical bootstrap or paper evidence is profit proof until the
  evidence gates require it.

## Runtime Architecture

Every product command follows the same top-level shape:

```text
CLI command
  -> build_required_real_llm()
  -> run_structured_llm_health_check()
  -> run command deterministic work
  -> run command-specific real LLM judgement
  -> validate LLM output with schema and deterministic guards
  -> write outputs, memory, reports, and ledgers
```

The health check is not a plain text ping. It must require a strict JSON response
that proves the configured LLM can follow the structured-output contract needed
by the project. A response that cannot be parsed into the health schema fails
closed.

`llm-health-check` is the only diagnostic command that may call the LLM without
first passing the global product runtime gate.

## Required LLM Runtime Context

Product entry points should receive a required real LLM runtime object rather
than an optional callable.

Preferred naming:

```python
llm_runtime: LLMRuntimeContext
```

or:

```python
llm_client: RealLLMClient
```

The runtime context must expose enough metadata for tests and artifacts to prove
that a real provider was used:

- provider name
- model name
- role or route name
- request id or response id when available
- structured schema name
- `llm_provider=real`
- `used_fake_llm=false`

## Command Responsibilities

### `source-probe`

Deterministic work:

- Request the configured source target.
- Parse the response.
- Compute provider status and source-health fields.

Required LLM work:

- Interpret source-health results.
- Decide whether the source is worth promoting in the research workflow.
- Identify missing fields and the next probe requirement.

Structured output:

- `SourceResearchJudgement`

The command fails if this LLM judgement is missing, invalid, or rejected by
guards.

### `ingest`

Deterministic work:

- Collect source data.
- Normalize records.
- Write typed records.
- Produce data-quality summaries.

Required LLM work:

- Judge whether the collected data is ready for research use.
- Identify missing records, stale fields, duplicate risk, or additional source
  probes needed before research use.

Structured output:

- `DataReadinessJudgement`

The data source can be fake in low-level tests, but product acceptance tests must
use a real LLM for the judgement.

### `research-loop`

Deterministic work:

- Load stored records.
- Convert records to scanner signals.
- Rank anomalies.
- Provide computed context and evidence references.

Required LLM work:

- Generate hypotheses.
- Explain expected edge mechanisms.
- Define disconfirmation tests.
- Critique weak or unsupported hypotheses.

Structured output:

- `LLMHypothesisSet`

The deterministic scanner and anomaly detector remain tools. They cannot by
themselves make the `research-loop` command successful.

### `evidence-run`

Deterministic work:

- Ingest configured data.
- Record source health.
- Run research loop support computations.
- Run validators.
- Run paper simulation where eligible.
- Write validation evidence, paper outcomes, and memory.

Required LLM work:

- Interpret the full run evidence.
- Explain validation and paper outcomes.
- Review blocked reasons.
- Propose the next bounded experiment.

Structured output:

- `EvidenceRunInterpretation`

If deterministic data collection or validation succeeds but LLM interpretation
fails, the command fails.

### `plan-experiments`

Deterministic work:

- Build context from validation evidence, paper evidence, source health, memory,
  blocked parameter sets, stopped families, available data fields, and registered
  validators.

Required LLM work:

- Generate the next experiment batch.

Structured output:

- `ExperimentBatch`

Deterministic guards then enforce:

- registered strategy family
- registered validator
- evidence references that exist
- available data fields only
- no stopped family unless explicitly allowed by a future approved design
- no live capital
- no live order routing
- no charter violation

The old deterministic product fallback is removed.

### `evidence-report`

Deterministic work:

- Aggregate ledger facts.
- Build daily or weekly evidence facts.

Required LLM work:

- Produce structured report narrative.
- Explain what improved, degraded, is blocked, should stop, and what should be
  tried next.

Structured output:

- `EvidenceReportNarrative`

LLM narrative must reference real evidence facts. Unsupported claims fail
validation.

### `governance-report`

Deterministic work:

- Compute family scoreboard.
- Compute paper sample, net PnL, expectancy, drawdown, hit rate, source-health,
  stopped-family, and portfolio-review fields.
- Produce deterministic governance actions.

Required LLM work:

- Explain owner-facing governance decisions.
- Summarize why a family is `keep_collecting`, `stop`, `redesign_validator`,
  `add_data`, or `owner_decision_review`.

Structured output:

- `GovernanceReview`

The LLM cannot override the deterministic scoreboard or governance action. If
the LLM explanation contradicts the computed facts, the command fails.

### `historical-bootstrap`

Deterministic work:

- Run historical windows.
- Produce bootstrap strategy evidence and source-health context.

Required LLM work:

- Interpret whether bootstrap evidence is a useful starting point for forward
  evidence collection.
- Identify which family needs data, redesign, or stopping consideration.

Structured output:

- `BootstrapInterpretation`

The output must preserve the rule that historical bootstrap is not profit proof
and does not count as future out-of-sample evidence.

### `rollout-review`

Deterministic work:

- Evaluate rollout gates.
- Check paper evidence.
- Check sample count, walk-forward coverage, cost-adjusted expectancy, risk
  limits, and human approval references.

Required LLM work:

- Produce an owner-readable readiness explanation.

Structured output:

- `RolloutReadinessNarrative`

`live_execution_enabled=false` remains a deterministic hard constraint. The LLM
cannot enable live execution.

## Removed Product Semantics

The product runtime must remove or reject these semantics:

- `llm=None`
- `required=False` for product LLM construction
- `use_llm`
- `skip_llm`
- optional LLM summary
- optional LLM planner
- deterministic product fallback
- `if llm is None: ...`
- product CLI success without real LLM participation
- `offline_only` as a no-LLM mode

If a name like `offline_only` remains, it may only refer to market-data network
policy. It must not disable LLM usage.

## Deterministic Components That Remain

The following deterministic modules are still required, but they are tools and
guards inside an LLM-native runtime. They cannot independently define product
success:

- data normalization
- schema validation
- source quality computation
- strategy validators
- paper simulation
- cost model
- risk guard
- charter guard
- secret redaction
- evidence ledger
- memory persistence
- report fact aggregation

The LLM is the research brain. Deterministic code is the calculator, instrument
panel, guardrail, and audit log.

## Failure Semantics

Preflight failure happens before business side effects.

The command must exit nonzero when:

- LLM credentials are missing.
- LLM configuration is invalid.
- LLM connection fails.
- LLM request times out.
- LLM response is not valid JSON.
- LLM response does not match the required schema.
- LLM output violates charter, guard, or evidence-reference checks.
- A fake LLM is used in a product command.
- The result does not prove `llm_provider=real`.

Preflight failure output should be structured JSON similar to:

```json
{
  "command": "evidence-run",
  "exit_code": 2,
  "reason_code": "llm_health_check_failed",
  "llm_required": true,
  "llm_provider": "unavailable",
  "side_effects_started": false
}
```

Command-specific LLM failure after deterministic work has started also exits
nonzero and must not write success artifacts or update latest-success pointers.

## Testing Strategy

### Blocking Real LLM Acceptance Tests

Core product acceptance tests must call the real LLM. These tests fail when the
real LLM is unavailable or produces invalid structured output.

Required acceptance coverage:

- real LLM health check
- real LLM `source-probe` flow
- real LLM `ingest` flow
- real LLM `research-loop` flow
- real LLM `evidence-run` flow
- real LLM `plan-experiments` flow
- real LLM `evidence-report` flow
- real LLM `governance-report` flow
- real LLM `historical-bootstrap` flow
- real LLM `rollout-review` flow

Acceptance tests must verify:

- `llm_provider=real`
- `used_fake_llm=false`
- schema name is recorded
- command-specific LLM output exists
- deterministic guard validation ran
- no live capital or live order routing is enabled

### Unit Tests

Unit tests may use fake LLMs only when testing isolated local logic, including:

- schema parser behavior
- guard behavior
- redaction behavior
- cost model logic
- validator math
- source-quality calculations
- prompt/response coercion edge cases

Fake LLM tests cannot prove CLI acceptance or product runtime readiness.

### No Skip Policy For Core Acceptance

The confirmed owner rule is blocking failure:

- Missing API key fails.
- Timeout fails.
- Provider failure fails.
- Invalid JSON fails.
- Schema failure fails.
- Guard rejection fails.
- Fake LLM usage fails.

Core real LLM acceptance tests must not silently skip under normal verification.

## Documentation Updates Required During Implementation

Implementation must update:

- `docs/runbook.md`
- `docs/roadmap.md`
- `docs/goals/project-completion-state.md`
- phase completion report for the LLM-native runtime work
- CLI examples that currently imply LLM-optional execution
- test policy documentation that currently permits deterministic product
  acceptance without a real LLM

## Open Implementation Notes

- The final implementation plan should decide the exact Pydantic schema names
  and fields for each structured LLM output.
- The final implementation plan should audit current CLI parser arguments and
  remove any user-facing LLM-disable flags.
- The final implementation plan should audit product function signatures for
  optional LLM callables.
- The final implementation plan should keep deterministic modules testable as
  isolated local units.
- The final implementation plan should preserve the current charter safety
  exclusions around live trading, wallet access, MEV, premium infrastructure,
  and speed-edge strategies.
