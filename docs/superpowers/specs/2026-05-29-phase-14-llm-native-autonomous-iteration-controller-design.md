# Phase 14 LLM-Native Autonomous Iteration Controller Design

## Objective

Build the first safe increment toward the owner autonomy target: a product
command that uses the configured real LLM to turn current evidence into strict
iteration candidates for new data sources, strategy changes, experiment
parameter changes, and code-change requests.

This phase does not let the agent directly edit code, install dependencies,
write live adapters, route orders, touch wallets, or run as an always-on daemon.
It creates evidence-grounded candidates that can later be reviewed, tested, and
implemented.

## Evidence

Smart Search evidence is saved under
`/tmp/smart-search-evidence/20260529-phase14-autonomous-iteration/`:

- `00-doctor.json`: Smart Search preflight returned `ok=true`.
- `01-deep-plan.json`: deep-research planning artifact for safe autonomous
  iteration controller design.
- `02-search-agent-safety.json`: broad discovery on autonomous coding agent
  safety, human review gates, structured outputs, and harness boundaries.
- `03-openai-structured-outputs.md`: OpenAI structured output documentation.
- `04-owasp-prompt-injection.md`: OWASP prompt injection prevention guidance.
- `05-github-actions-hardening.md`: GitHub Actions security hardening guidance.
- `06-owasp-ai-agent-security.md`: OWASP AI agent security guidance.
- `08-openai-agent-evals.md`: OpenAI agent evaluation workflow guidance.

Design-relevant evidence:

- Structured LLM outputs should be validated against strict schemas instead of
  treating valid JSON as sufficient.
- Agent systems need least-privilege tool surfaces, human-in-the-loop controls
  for high-risk actions, memory validation, output validation, and monitoring.
- External and retrieved content can carry prompt-injection payloads, so source
  discovery candidates must be treated as untrusted until probed and validated.
- Code automation needs review gates, tests, secret handling, and restricted
  token/workflow permissions before any merge or release action.
- Agent workflows should be evaluated with repeatable traces or datasets when
  prompts, tools, routing, or guardrails change.

## Existing Local Fit

The repository already has the right pieces to compose the first controller:

- `RealLLMRuntime` and strict `parse_structured_llm_json`.
- `build_ai_research_context()` for validation evidence, paper evidence,
  source health, memory, available data fields, and registered validators.
- `plan-experiments` for narrower strategy experiment proposals.
- `expansion-prep-report` for source and strategy readiness.
- `governance-report` for family actions.
- Source-probe catalog and source-health records.
- Secret redaction, evidence ledgers, cost model, risk guards, and no-live
  execution flags.

The new controller should reuse those instead of inventing a separate agent
framework.

## Product Shape

Add a product command:

```bash
uv run crypto-alpha-agent iteration-cycle \
  --db var/research.sqlite \
  --memory var/memory.jsonl \
  --out var/reports/iteration-cycle.md \
  --json-out var/reports/iteration-cycle.json \
  --current-capital-usd 300 \
  --max-candidates 5
```

Because this is a product command, it automatically goes through the existing
LLM-native CLI preflight. If the real LLM connection, health check, structured
JSON parsing, schema validation, evidence-ref validation, or safety validation
fails, the command fails closed.

## Data Model

Create `src/crypto_alpha_agent/pipeline/iteration_controller.py` with strict
Pydantic models:

- `IterationCandidateKind`:
  `new_data_source`, `new_strategy_validator`, `validator_change`,
  `experiment_parameter_change`, `code_change_request`.
- `IterationCandidateRisk`:
  `low`, `medium`, `high`, `blocked`.
- `IterationCandidate`:
  - `candidate_id`
  - `kind`
  - `title`
  - `rationale`
  - `evidence_refs`
  - `expected_value`
  - `risk_level`
  - `next_actions`
  - `required_tests`
  - `required_data_fields`
  - `source_discovery_queries`
  - `source_probe_targets`
  - `strategy_family`
  - `target_files`
  - `human_review_required=True`
  - `direct_code_write_authorized=False`
  - `uses_real_capital=False`
  - `live_order_routing=False`
- `IterationControllerTask`:
  context supplied to the LLM.
- `IterationCycleReport`:
  accepted candidates, rejected reason codes, evidence refs, safe flags, and
  LLM metadata.

Validation rules:

- Candidate evidence refs must be drawn from the supplied context refs.
- Every candidate must require human review.
- Every candidate must include at least one required test.
- `code_change_request` must include target files and cannot authorize direct
  code writes.
- `new_data_source` must include discovery queries or probe targets and cannot
  mark the source production-ready.
- No candidate can set live-capital, live-order, premium-RPC, speed-edge, MEV,
  wallet, or private-key authority.

## Flow

1. CLI preflight builds and health-checks the real LLM runtime.
2. The command builds `AIResearchContext`, expansion-prep, and governance facts.
3. The command constructs an `IterationControllerTask` with:
   - available evidence refs;
   - source health summaries;
   - registered validators;
   - stopped or degraded families;
   - source and strategy readiness candidates;
   - current owner constraints.
4. The real LLM returns an `IterationCandidateBatch`.
5. Deterministic validators reject unsafe, uncited, duplicate, or unsupported
   candidates.
6. The command writes Markdown and JSON artifacts only for accepted candidates
   or explicit blocked results from the real LLM.
7. The report records that it does not execute changes and does not run as a
   daemon.

## Out Of Scope

- Direct file edits by the product command.
- Automatic dependency installation.
- Automatic PR creation.
- Running arbitrary shell commands.
- Unknown web browsing inside product runtime.
- Automatic source promotion to `ProductionResearchSource`.
- Live execution, wallet access, order routing, MEV, private RPC, premium RPC,
  or speed-edge strategies.

## Testing

Focused tests must prove:

- The controller requires an LLM callable.
- Valid LLM candidates are accepted and rendered.
- Unknown evidence refs are rejected.
- Live-order or real-capital candidates are rejected at schema/guard level.
- `code_change_request` cannot authorize direct code writes.
- `new_data_source` must stay candidate/probe-only.
- CLI command uses the existing LLM-native gate and writes JSON/Markdown
  artifacts.
- Documentation mentions the new command as the first safe autonomy increment.

Real LLM integration can be added as a small follow-up after deterministic
guard behavior is stable.
