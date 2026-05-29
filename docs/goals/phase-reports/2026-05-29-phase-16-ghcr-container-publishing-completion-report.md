# Phase 16 Completion Report: GHCR Container Publishing

Date: 2026-05-29

## Scope

Phase 16 makes the VPS runtime consume a published GitHub Container Registry
image by default. It keeps Docker Compose and systemd as the operations layer
and does not change the research, data, validation, paper simulation, memory,
or governance product workflow.

## Delivered

- Added `.github/workflows/publish-container.yml` to publish
  `ghcr.io/ww-shan/crypto-alpha-agent` from the repository `Dockerfile`.
- The workflow publishes `linux/amd64` and `linux/arm64` manifests so VPS
  hosts and local Apple Silicon Docker Desktop can pull the same tag.
- Default branch pushes publish `:main` and immutable `:sha-<commit>` tags;
  version tags publish matching GHCR tags.
- Updated `docker-compose.yml` so the service defaults to
  `ghcr.io/ww-shan/crypto-alpha-agent:main`.
- Preserved explicit local builds and local soak runs through
  `CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local`.
- Updated `docs/vps-deployment.md` so VPS maintenance uses
  `docker compose pull crypto-alpha-agent` followed by
  `docker compose run --rm crypto-alpha-agent llm-health-check`.
- Documented private GHCR package login as a host-local operation without
  committing registry credentials.
- Hardened real LLM structured-output handling:
  - runtime `health_check` and `structured_call` retry transient invalid JSON,
    non-string, or schema-invalid outputs up to three attempts;
  - `plan-experiments` retries structural planner output failures up to three
    attempts;
  - safety failures, charter violations, live-capital requests, live routing,
    unsupported sources, unsupported validators, and missing evidence refs
    still fail closed.
- Expanded research-only judgement decision vocabulary for observed real LLM
  responses while keeping `uses_real_capital=false`,
  `live_order_routing=false`, and governance action enums constrained.

## Boundary

This phase does not add autonomous code writing, autonomous source promotion,
wallet access, exchange order routing, live execution, or live capital.

Published images do not contain `.env`, `var/`, worktrees, local databases,
logs, reports, proxy values, LLM credentials, registry tokens, wallet keys, or
exchange keys. Runtime secrets remain host-local.

## Verification

Verification completed during implementation:

- Baseline VPS contract:
  `uv run --extra dev pytest tests/test_vps_ops.py -q` -> 14 passed.
- TDD RED for GHCR contracts:
  `uv run --extra dev pytest tests/test_vps_ops.py -q` -> failed on missing
  workflow, non-GHCR compose image, and missing VPS GHCR docs.
- Focused GHCR/docs contracts after implementation:
  `uv run --extra dev pytest tests/test_vps_ops.py tests/test_documentation_contract.py -q`
  -> 26 passed.
- TDD RED/GREEN for real LLM judgement vocabulary:
  `uv run --extra dev pytest tests/test_llm_native_judgements.py::test_judgements_accept_context_specific_research_decisions tests/test_llm_configured_client.py::test_responses_adapter_uses_json_schema_format_for_judgement_task -q`
  -> failed before expansion, then 2 passed.
- TDD RED/GREEN for runtime structured-output retries:
  `uv run --extra dev pytest tests/test_llm_native_runtime.py::test_real_runtime_health_check_retries_schema_failures_before_success tests/test_llm_native_runtime.py::test_real_runtime_health_check_fails_closed_after_retry_budget tests/test_llm_native_runtime.py::test_real_runtime_structured_call_retries_schema_failures_before_success -q`
  -> failed before retry helper, then 3 passed.
- TDD RED/GREEN for planner structural-output retries:
  `uv run --extra dev pytest tests/test_ai_experiment_planner.py::test_planner_retries_structural_proposal_schema_failures -q`
  -> failed before planner retry loop, then 1 passed.
- Focused regression bundle:
  `uv run --extra dev pytest tests/test_vps_ops.py tests/test_documentation_contract.py tests/test_ai_experiment_planner.py tests/test_llm_native_runtime.py tests/test_llm_native_judgements.py tests/test_llm_configured_client.py::test_responses_adapter_uses_json_schema_format_for_judgement_task -q`
  -> 81 passed.
- Real LLM planner smoke:
  `uv run --extra dev pytest tests/test_real_llm_integration_policy.py::test_real_plan_experiments_cli_uses_configured_llm_without_secret_leaks -q`
  -> 1 passed.
- Full suite:
  `uv run --extra dev pytest -q` -> 990 passed.

Final lint, diff, staged diff, and staged secret scan are required immediately
before commit: `uv run --extra dev ruff check .`, `git diff --check`,
`git diff --cached --check`, `git diff --cached --name-only`,
`git diff --cached --no-ext-diff --unified=0`, and
`uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`.

## Remaining Gaps

- The first GitHub Actions publish run must complete on GitHub after the merge
  to make `ghcr.io/ww-shan/crypto-alpha-agent:main` available.
- If the GHCR package remains private, the VPS operator must log in to GHCR on
  the host before `docker compose pull`.
- VPS timers still run existing LLM-native evidence jobs; they do not implement
  autonomous code writing or autonomous source promotion.
- The 30/60/90 out-of-sample evidence campaign still requires real operation
  over time.
- Live execution remains blocked by the current charter.
