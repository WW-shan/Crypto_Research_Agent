# LLM-Native Runtime Completion Report - 2026-05-24

## Objective

Make the real configured LLM a required participant in every product command and
remove deterministic-only product success paths.

## Safety

This phase does not enable live trading, wallet keys, exchange order routing,
MEV, premium RPC, private infrastructure, or speed-edge strategies.

Deterministic modules remain active for normalization, schema validation,
source-quality scoring, strategy validation, paper simulation, cost modeling,
risk guards, secret redaction, and evidence ledgers. They now act as
calculators and constraints inside the LLM-native runtime; they cannot make a
product command succeed without real LLM participation.

## Completed

- Added a required real LLM runtime gate and structured health check.
- Removed product-facing no-LLM fallback paths and obsolete offline LLM flags.
- Required structured LLM judgement or interpretation for product commands,
  including evidence runs, source probes, ingest checks, governance reports,
  historical bootstrap, rollout review, schedule plans, and legacy smoke
  commands.
- Converted real LLM policy tests from skipped/optional to fail-closed core
  acceptance coverage.
- Expanded real LLM acceptance coverage to `llm-health-check`, `source-probe`,
  `ingest`, `plan-experiments`, `research-loop`, `evidence-report`,
  `governance-report`, `historical-bootstrap`, and `rollout-review`.

## Verification

- `uv run --extra dev pytest tests/test_llm_native_runtime.py tests/test_cli_llm_native_gate.py tests/test_llm_native_judgements.py -q`
  - Result: `24 passed in 0.62s`.
- `uv run --extra dev pytest tests/test_real_llm_test_policy_contract.py tests/llm_integration_policy.py -q`
  - Result: `3 passed`.
- `uv run --extra dev pytest tests/test_real_llm_integration_policy.py -q`
  - Result: `9 passed in 314.86s`.
- `uv run --extra dev pytest tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks -q`
  - Result: `1 passed`.
- `uv run --extra dev pytest -q`
  - Result: `957 passed in 157.53s`.
- `uv run --extra dev ruff check .`
  - Result: passed.
- `git diff --check`
  - Result: passed.
- `rg -n "offline_only|--offline-only|--no-offline-only|llm is None|llm=None|required=False|skip\\(\"real LLM|deterministic local mode|offline_no_config|pytest_offline_default" src tests docs`
  - Result: no current product-path matches. Remaining matches are historical
    plans/reports/design notes describing removed behavior, parser rejection
    tests proving removed flags are rejected, and config unit tests for missing
    optional settings.
