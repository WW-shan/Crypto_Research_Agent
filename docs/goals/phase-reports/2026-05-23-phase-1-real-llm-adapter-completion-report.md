# Phase 1 Real LLM Adapter Completion Report

## Scope

- Phase: Immediate Phase 1: Real LLM Adapter.
- Date: 2026-05-23.
- Objective: make the repository read the owner's local
  OpenAI-compatible LLM configuration, route models by role, call the
  configured Responses-compatible endpoint, and prove the call path without
  leaking secrets.
- Boundaries: this phase did not wire the real LLM into `research-loop`,
  `plan-experiments`, `evidence-run`, report summaries, memory persistence, or
  any execution/live path.

## External Evidence

Smart Search and source-backed research were run before planning:

```bash
smart-search doctor --format json
smart-search deep "Immediate Phase 1 Real LLM Adapter for a Python project: implement local .env OpenAI-compatible Responses API client, model routing for research/planning/coder/summary roles, fail-closed missing credentials, redaction of API keys/base URLs/provider headers, and safe real LLM smoke tests without leaking secrets" --budget deep --format json --output /tmp/smart-search-evidence/2026-05-23-phase1/01-deep-plan.json
smart-search search "Python OpenAI-compatible Responses API client .env configuration model routing secret redaction integration tests" --validation balanced --extra-sources 3 --timeout 90 --format json --output /tmp/smart-search-evidence/2026-05-23-phase1/02-broad-search.json
smart-search search "site:developers.openai.com/api/docs Responses API create response authentication Bearer OpenAI" --validation balanced --extra-sources 2 --timeout 90 --format json --output /tmp/smart-search-evidence/2026-05-23-phase1/05-openai-official-search.json
smart-search fetch "https://developers.openai.com/api/docs/guides/migrate-to-responses" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase1/06-openai-responses-vs-chat.md
smart-search fetch "https://developers.openai.com/api/reference/resources/responses/methods/create/" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase1/08-openai-responses-create-developers.md
smart-search fetch "https://developers.openai.com/api/reference/overview/" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase1/09-openai-api-overview.md
smart-search fetch "https://docs.pydantic.dev/latest/api/types/#pydantic.types.SecretStr" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase1/10-pydantic-secretstr.md
```

Findings used:

- OpenAI documentation shows Responses requests use a model plus `input`, and
  the migration guide documents `/v1/responses` and `output_text` or `output`
  response items.
- OpenAI API documentation states API keys are secrets, should be loaded from
  environment or a server-side key-management source, and are supplied with
  HTTP bearer authentication.
- Pydantic `SecretStr` is suitable for storing the API key in a settings model
  without normal string representation exposing the raw value.
- Exa official-doc search was attempted but unavailable because `EXA_API_KEY`
  is not configured. Smart Search `search` and `fetch` supplied the official
  OpenAI and Pydantic page evidence.

## Local Feasibility And Prototype

Local feasibility checks:

- `git status --short --branch --untracked-files=all` started clean on
  `main...origin/main`.
- `.env` was present locally and ignored; only variable presence was checked,
  not values.
- Existing code already had injected LLM seams:
  `run_llm_research_node(report, llm, ...)`, `plan_next_experiments(...,
  llm=None, ...)`, and LangGraph builders that accept injected callables.

Small prototype:

- A metadata-only `uv run --extra dev python` probe called the configured
  Responses-compatible endpoint.
- Result: configured, HTTP status `200`, JSON response, and `output` items.
- The prototype printed no API key, provider URL, provider headers, model text,
  or local proxy value.

## Implementation Summary

Files created:

- `src/crypto_alpha_agent/llm/__init__.py`
- `src/crypto_alpha_agent/llm/redaction.py`
- `src/crypto_alpha_agent/llm/responses.py`
- `tests/test_llm_configured_client.py`
- `docs/superpowers/plans/2026-05-23-phase-1-real-llm-adapter.md`
- `docs/goals/phase-reports/2026-05-23-phase-1-real-llm-adapter-completion-report.md`

Files modified:

- `src/crypto_alpha_agent/config.py`
- `pyproject.toml`
- `docs/runbook.md`
- `docs/roadmap.md`
- `docs/goals/project-completion-state.md`

Behavior added:

- `LLMSettings.from_env(...)` reads local `.env` plus shell environment, with
  shell environment taking precedence.
- Model routing:
  - `default`, `research`, and `planning` use `OPENAI_RESEARCH_MODEL` then
    `OPENAI_MODEL`.
  - `coder` and `validator_design` use `OPENAI_CODER_MODEL` then
    `OPENAI_MODEL`.
  - `summary`, `report`, and `fast` use `OPENAI_FAST_MODEL` then
    `OPENAI_MODEL`.
- Missing required credentials fail closed with a local configuration error that
  names missing variable names but not values.
- `build_configured_llm(...)` returns an `OpenAIResponsesAdapter` when
  credentials are configured, or `None` when optional and missing.
- `OpenAIResponsesAdapter` posts to a normalized Responses URL, extracts
  `output_text` or nested `output` content, strips JSON fences, and returns only
  provider text.
- Provider exceptions redact API key, full provider URL, provider host, bearer
  headers, and provider error-body values.
- The default timeout is `180` seconds so the configured strong research model
  has room to complete smoke tests.
- Pytest has a registered `integration` marker.

## Verification

Completed verification before final review:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py -q
```

Result: 11 passed. This included the real configured LLM smoke test.

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py tests/test_llm_researcher_adapter.py tests/test_llm_contracts.py tests/test_llm_graph_routing.py tests/test_ai_experiment_planner.py tests/test_documentation_contract.py -q
```

Result: 69 passed.

Final verification after review fixes:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py -q
```

Result: 12 passed. This included the real configured LLM smoke test.

```bash
uv run --extra dev pytest -q
```

Result: 762 passed.

```bash
uv run --extra dev ruff check .
```

Result: `All checks passed!`.

```bash
git diff --check
git status --short --branch --untracked-files=all
```

Result: diff whitespace check passed and status showed only deliberate Phase 1
files before staging.

```bash
git diff --cached --check
git diff --cached --name-only
```

Result: staged whitespace check passed and the staged set contained only
deliberate Phase 1 files.

Staged secret-safety scan:

- Checked staged diff for actual API-key-like tokens, non-fake authorization
  bearer headers, GitHub tokens, private-key material, and local configured
  values loaded from `.env` or shell environment.
- Result: passed.
- The scan did not print local secret values, provider URL, local proxy values,
  raw provider headers, or model response text.

## Secret Safety

- `.env` was not printed or staged.
- The adapter has no API-key CLI flag.
- Tests use fake key and provider strings only.
- The real LLM smoke test checks that the configured API key and provider URL
  are not copied into stdout, stderr, or model text.
- A real timeout failure exposed that provider host fragments can appear in
  lower-level HTTP exception text. A regression test was added, and the adapter
  now redacts both full provider URL and parsed host fragments.
- No raw provider headers are logged or persisted.
- No memory records or report artifacts receive raw LLM responses in Phase 1.
- Final staged secret-safety checks passed for the Phase 1 commit set.

## Review Passes

Review pass 1: specification and roadmap compliance.

- Reviewer: read-only subagent `Hooke`.
- Critical findings: none.
- Important findings:
  - `docs/goals/project-completion-state.md` was not yet synchronized with the
    Phase 1 report link. Fixed by updating the current round, completed work,
    verification evidence, next-round entry instructions, and round history.
- Minor findings:
  - The report still said final verification was pending while the roadmap had
    a completion record. This will be resolved by replacing the pending
    verification section after final checks.

Review pass 2: code quality and secret safety.

- Reviewer: read-only subagent `Beauvoir`.
- Critical findings: none.
- Important findings:
  - Real LLM smoke only required opt-in in CI. This was reviewed and rejected as
    a change request because it conflicts with the owner preference and goal
    policy: local owner-directed development may run real LLM smoke tests by
    default once credentials are configured.
  - Secret-leak assertions could print the compared secret value through pytest
    introspection if they failed. Fixed by using a helper that reports only a
    redacted label.
  - Dict/repr-style authorization headers were not fully redacted. Fixed with a
    regression test and a repr-style authorization redaction pattern.
  - The implementation plan's staged secret-scan command included concrete
    provider/proxy fragments. Fixed by replacing them with generic labels.
- Minor findings:
  - The plan includes fake environment assignments inside test code snippets.
    These are intentionally fake test fixtures and do not contain real secrets.

Re-review:

- Specification re-review: no Critical, Important, or Minor findings remained.
- Code-quality/secret-safety re-review: no Critical or Important findings
  remained.

## Boundaries Preserved

- No live trading.
- No wallet/private key handling.
- No exchange order routing.
- No real-capital execution.
- No MEV, mempool, bridge race, flash-loan race, premium RPC, speed-edge, or
  private infrastructure dependency.
- No Phase 2 wiring into `research-loop`, `plan-experiments`, `evidence-run`,
  report summaries, memory persistence, scheduler plans, or execution adapters.

## Remaining Work For Phase 2

Immediate Phase 2 may use `build_configured_llm(...)` to inject the real adapter
into existing research/planning seams. It must still preserve schema parsing,
guard rejection, raw-response omission, memory safety, and explicit offline
controls.
