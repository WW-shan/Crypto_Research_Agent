# Phase 3 Real LLM Test Policy Completion Report

## Scope

- Phase: Immediate Phase 3: Real LLM Test Policy.
- Date: 2026-05-23.
- Objective: make the owner's real LLM participate in meaningful positive
  integration tests while preserving deterministic fake adversarial tests and
  broad secret-leak checks.
- Work type: implementation, test-policy, documentation, and state repair.
- Pending commit: `test: formalize real llm policy`.
- Boundaries: no live trading, wallet access, exchange order routing, real
  capital, MEV, premium RPC, speed-edge dependency, or execution adapter was
  added.

## External Evidence

Smart Search evidence was saved under
`/tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/`.

Commands:

```bash
smart-search doctor --format json --output /tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/00-doctor.json
smart-search deep "Phase 3 Real LLM Test Policy for a Python crypto research agent: pytest markers for real provider integration tests, default local opt-in/opt-out behavior, fake adversarial tests, secret leak scans, and CI-safe handling of API keys/logs/artifacts" --budget deep --format json --output /tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/01-deep-plan.json
smart-search search "pytest markers real API integration tests skipif environment variable CI secrets redaction artifacts" --validation balanced --extra-sources 3 --format json --output /tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/02-broad-search.json
smart-search fetch "https://docs.pytest.org/en/stable/example/markers.html" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/03-pytest-markers.md
smart-search fetch "https://docs.pytest.org/en/stable/how-to/skipping.html" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/04-pytest-skipping.md
smart-search fetch "https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/05-github-actions-secrets.md
smart-search fetch "https://platform.openai.com/api/docs/guides/production-best-practices" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/06-openai-production-best-practices.md
smart-search context7-docs "/pytest-dev/pytest" "custom markers skipif environment variable integration tests strict markers" --format json --output /tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/08-context7-pytest-docs.json
```

Findings used:

- Pytest custom markers support selecting/deselecting integration tests and
  should be registered to avoid accidental typos.
- Pytest skip/skipif is appropriate for external resources that are unavailable
  under explicit conditions.
- GitHub Actions secrets should be injected through secret contexts/environment
  variables and masked rather than printed.
- OpenAI production guidance says API keys should be kept out of code and
  public repositories and exposed through environment variables or secret
  management.

## Local Feasibility

Initial local checks:

```bash
git status --short --branch --untracked-files=all
```

Result: clean `main...origin/main` before Phase 3 edits.

```bash
uv run --extra dev pytest --collect-only -q -m integration
```

Result before implementation: 1 integration test collected, 769 deselected.

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks -q
```

Result before implementation: 1 passed with the configured real LLM.

Code feasibility findings:

- `pyproject.toml` already had an `integration` marker but no
  `llm_integration` marker or strict marker validation.
- Real LLM coverage existed only for the configured adapter smoke path.
- `plan-experiments`, `research-loop`, and `evidence-report` already had Phase
  2 real LLM CLI wiring and could be tested directly.
- Existing fake tests already covered unsafe/adversarial output but the policy
  was not asserted as a durable contract.
- `docs/roadmap.md` and `docs/goals/project-completion-state.md` referenced a
  Phase 2 completion report that was missing from the repository.

## Substep Validation And Debugging

Secret scanner TDD:

```bash
uv run --extra dev pytest tests/test_secret_scan_policy.py -q
```

Result: failed first with `ModuleNotFoundError: No module named
'crypto_alpha_agent.security'`, then passed after adding the scanner.

Real LLM policy TDD:

```bash
uv run --extra dev pytest tests/test_real_llm_integration_policy.py tests/test_real_llm_test_policy_contract.py -q
```

Result: failed first because `llm_integration_policy` did not exist.

After adding the helper and marker, the real LLM tests initially exposed real
integration failures:

- `plan-experiments` returned `charter_violation` because the model used the
  forbidden term `live order` in a negative safety explanation.
- `evidence-report` returned `invalid_summary` because the real model produced
  more metric references than the previous schema allowed.
- `research-loop` succeeded in direct diagnostic rerun and was stabilized by
  the same stricter prompt wording.

Fixes:

- `OpenAIResponsesAdapter` now tells real models not to repeat prohibited
  execution terms in free-text fields, while still requiring `false` boolean
  authority fields.
- Evidence-report summary list bounds were relaxed from 8 to 16 metric refs
  and from 8 to 12 caveats to tolerate useful real summaries while still
  bounding output.
- Real LLM test helpers now retry transient provider `5xx` and timeout failures
  once and fail with redacted integration-environment messages if the provider
  remains unavailable.
- Secret scanner public metadata now redacts configured values in both surface
  names and finding labels.
- The fake adversarial policy contract now binds each required category to a
  specific deterministic test function.
- Evidence-report summary normalization accepts exact false safety-field echoes
  and `no live order routing` wording required by real summaries, while a
  regression still rejects indirect follow-on instructions such as `then place
  one`.

Focused post-fix result:

```bash
uv run --extra dev pytest tests/test_secret_scan_policy.py tests/test_real_llm_test_policy_contract.py tests/test_evidence_reports.py::test_report_summarizer_accepts_common_caveats_alias_without_extra_raw_text tests/test_evidence_reports.py::test_report_summarizer_normalizes_false_safety_flag_echoes_without_raw_text tests/test_evidence_reports.py::test_report_summarizer_rejects_valid_unsafe_instruction_without_raw_text tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks tests/test_real_llm_integration_policy.py -q
```

Result: 16 passed.

## Files Changed

Created:

- `src/crypto_alpha_agent/security/__init__.py`
- `src/crypto_alpha_agent/security/secret_scan.py`
- `tests/llm_integration_policy.py`
- `tests/test_secret_scan_policy.py`
- `tests/test_real_llm_integration_policy.py`
- `tests/test_real_llm_test_policy_contract.py`
- `docs/superpowers/plans/2026-05-23-phase-3-real-llm-test-policy.md`
- `docs/goals/phase-reports/2026-05-23-phase-2-connect-llm-research-loop-completion-report.md`
- `docs/goals/phase-reports/2026-05-23-phase-3-real-llm-test-policy-completion-report.md`

Modified:

- `pyproject.toml`
- `.gitignore`
- `src/crypto_alpha_agent/agents/report_summarizer.py`
- `src/crypto_alpha_agent/llm/responses.py`
- `tests/test_evidence_reports.py`
- `tests/test_llm_configured_client.py`
- `docs/runbook.md`
- `docs/roadmap.md`
- `docs/goals/project-completion-state.md`

## Subagents

Subagent used:

- `Kepler` (`019e548c-d1fc-7643-adcb-04317a1e23c7`) performed a read-only
  Phase 3 gap audit.

Key findings:

- Critical: only the adapter had real positive LLM coverage.
- Critical: secret leak scanning did not yet cover memory, reports, artifacts,
  staged diffs, and manifests.
- Critical: the Phase 2 completion report link existed but the file was
  missing.
- Important: fake adversarial tests were scattered but not formalized as a
  policy boundary.
- Important: provider failures needed to be treated as integration environment
  failures, not product success.

Actions taken:

- Added real positive tests for `plan-experiments`, `research-loop`, and
  `evidence-report`.
- Added a reusable secret scanner and test helper.
- Added a policy contract for fake adversarial coverage.
- Added the missing Phase 2 completion report.

## Review Passes

Review pass 1: specification/requirements review by `Curie`
(`019e54d8-1561-7381-af04-fde378b2f1cf`).

- Critical: none.
- Important: completion records still said review/final verification/staged
  checks were pending; verification counts were stale; the adversarial policy
  contract was too weak because it searched broad file text instead of binding
  categories to deterministic tests.
- Fixes: completion records are updated after final verification, and
  `tests/test_real_llm_test_policy_contract.py` now maps every required fake
  adversarial category to a specific deterministic test function.

Review pass 2: code-quality/secret-safety review by `Nash`
(`019e54d8-4845-7980-9ef5-84727c04f475`).

- Critical: none.
- Important: public finding surfaces could leak configured values when a path
  contained a secret; adversarial policy contract was too weak.
- Minor: false `caves` alias weakens exact schema behavior; unused test helpers
  remained after helper consolidation.
- Fixes: public surfaces are redacted; unused helpers were removed; the
  adversarial policy contract was strengthened. The `caves` alias remains as a
  narrow real-provider tolerance with deterministic coverage and is normalized
  before strict validation.

Targeted re-review by `Harvey`
(`019e54f6-f5b7-7fd0-a5f3-f1de42c6f8f2`) reported no Critical or Important
issues and only noted that final records needed synchronization after staged
verification.

Targeted code-quality re-review by `Schrodinger`
(`019e54f7-3427-74c0-a5a3-e7842137e1dd`) found remaining Important issues:

- configured secret labels could still leak through public finding metadata;
- broad false-safety normalization could mask an unsafe follow-on instruction;
- the real evidence-report LLM test had recently failed with `invalid_summary`.

Fixes: finding labels now redact configured values, normalization is limited to
exact safety-field echoes plus `no live order routing`, a regression rejects
`then place one`, and the evidence-report real LLM path was rerun.

Final targeted re-review by `Arendt`
(`019e5506-72c4-78a3-85eb-3ef4548e0456`) reported no Critical, Important, or
Minor findings. Critical/Important issues are cleared.

## Verification

Focused verification completed:

```bash
uv run --extra dev pytest tests/test_secret_scan_policy.py tests/test_real_llm_test_policy_contract.py tests/test_evidence_reports.py::test_report_summarizer_accepts_common_caveats_alias_without_extra_raw_text tests/test_evidence_reports.py::test_report_summarizer_normalizes_false_safety_flag_echoes_without_raw_text tests/test_evidence_reports.py::test_report_summarizer_rejects_valid_unsafe_instruction_without_raw_text tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks tests/test_real_llm_integration_policy.py -q
```

Result: 16 passed.

LLM marker collection:

```bash
uv run --extra dev pytest --collect-only -q -m llm_integration
```

Result: 4 collected, 781 deselected.

Full verification:

```bash
uv run --extra dev pytest -q
```

Result: 785 passed in 55.99s.

Ruff:

```bash
uv run --extra dev ruff check .
```

Result: `All checks passed!`.

Diff check:

```bash
git diff --check
```

Result: passed with no output.

Staged checks:

```bash
git diff --cached --check
```

Result: passed with no output.

Staged secret-safety:

```bash
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

Result: passed with `[]`.

## Secret Safety

Current implemented protections:

- Real LLM tests use `tests/llm_integration_policy.py` to scan stdout, stderr,
  payload JSON, memory JSONL, report Markdown, and generated report paths.
- `SecretScanFinding` exposes only surface names and labels, never matched
  values; configured values are redacted from surface and label metadata before
  public output.
- `uv run python -m crypto_alpha_agent.security.secret_scan --staged
  --fail-on-empty-with-untracked` is available for staged diff review after
  intended files are staged.
- The scanner treats configured API keys, base URLs, local proxy values, bearer
  tokens, private-key blocks, and mnemonic-like values as sensitive surfaces.

Final staged secret-safety passed with `[]` after all intended Phase 3 files
were staged. `.env`, keys, databases, local reports, caches, and local
artifacts were not staged.

## Remaining Gaps

After this phase, the next roadmap phase is Immediate Phase 4: Evidence Run
Infrastructure. It must add run manifests, locking, failed-run markers, daily
artifact retention, and repeated operator-safe evidence-run behavior without
starting the formal Phase 7 evidence campaign.
