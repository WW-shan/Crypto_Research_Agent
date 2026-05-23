# Phase 3 Real LLM Test Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the owner-approved real LLM testing policy into enforced tests, reusable secret-leak scanning, documented operator commands, and complete phase records.

**Architecture:** Keep Phase 3 as a test-policy and verification slice. Do not add trading, wallet, order-routing, MEV, or strategy behavior. Add a small reusable secret scanner, a test-only real-LLM policy helper, real positive integration tests for the three Phase 2 LLM entry points, and documentation/state/report updates. Existing fake adversarial tests remain the deterministic safety boundary for impossible-to-force model failures.

**Tech Stack:** Python 3.12, argparse CLI, Pydantic models already in the project, pytest integration markers, existing OpenAI-compatible Responses adapter, Smart Search evidence, ruff.

---

## External Evidence

Smart Search evidence for this phase is stored under `/tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/`.

- `00-doctor.json`: Smart Search was available; main search, Tavily fetch, and Context7 docs were reachable. Exa, Firecrawl, and Zhipu were not configured.
- `01-deep-plan.json`: deep-research plan for real LLM integration-test policy, pytest markers, opt-in CI behavior, fake adversarial tests, secret redaction, and artifact safety.
- `02-broad-search.json`: broad discovery supported the same approach used here: registered pytest markers for external tests, skip/opt-in logic for CI, and secret handling through environment variables plus redaction/scanning.
- `03-pytest-markers.md`: fetched official pytest marker docs. Used finding: custom markers can select/deselect integration tests with `-m`, and registered markers are recommended.
- `04-pytest-skipping.md`: fetched official pytest skip/xfail docs. Used finding: tests depending on unavailable external resources should be skipped under explicit conditions rather than hidden as product success.
- `05-github-actions-secrets.md`: fetched official GitHub Actions secrets docs. Used findings: secrets should be provided through `secrets`/environment variables, sensitive values should be masked, and secrets should not be passed or printed on command lines.
- `06-openai-production-best-practices.md`: fetched official OpenAI production best-practices docs. Used findings: API keys must not be exposed in code or public repositories, and environment variables or secret management should be used.
- `08-context7-pytest-docs.json`: Context7 pytest snippets confirmed custom marker registration and strict marker validation patterns.

External implementation consequence:

- Real LLM tests must be explicit pytest integration tests.
- Local owner-directed runs may use real credentials by default when configured, but CI/shared automation must skip unless explicitly enabled.
- Positive real tests should fail as integration environment failures when the configured provider fails; fake tests remain responsible for deterministic unsafe-output coverage.
- Secret scanning must cover test output and artifacts, not just source code.

## Local Feasibility

Current state:

- `git status --short --branch --untracked-files=all` starts clean on `main...origin/main`.
- `pyproject.toml` already registers an `integration` marker.
- `tests/test_llm_configured_client.py` has one real configured LLM smoke test and many fake adapter/redaction tests.
- `tests/test_ai_experiment_planner.py`, `tests/test_cli_research_loop.py`, and `tests/test_evidence_reports.py` have injected/fake LLM wiring tests for Phase 2.
- `src/crypto_alpha_agent/cli.py` exposes `--offline-only` and `--no-offline-only` for `plan-experiments`, `research-loop`, and `evidence-report`. In pytest, omitted flags remain deterministic unless `CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS=1` is set.
- Existing guards and fake tests already cover invalid JSON, schema violations, live-order/private-key/MEV/premium-RPC/high-capital patterns across LLM contracts, planner, graph routing, and report summaries.

Feasibility checks already run:

```bash
uv run --extra dev pytest --collect-only -q -m integration
```

Result before this plan: 1 integration test collected, 769 deselected.

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks -q
```

Result before this plan: 1 passed with the configured real LLM.

Precondition repair:

- `docs/roadmap.md` and `docs/goals/project-completion-state.md` reference `docs/goals/phase-reports/2026-05-23-phase-2-connect-llm-research-loop-completion-report.md`, but that file is missing in the current repository. Phase 3 must add the missing Phase 2 report and correct stale Round 4 verification notes before Phase 3 can truthfully claim the chain is complete.

## File Map

- Create `src/crypto_alpha_agent/security/__init__.py`: public exports for secret scanning.
- Create `src/crypto_alpha_agent/security/secret_scan.py`: reusable redacted secret scanner for stdout, stderr, memory files, Markdown/JSON reports, generated artifacts, scheduler/run manifests, and staged diffs.
- Create `tests/llm_integration_policy.py`: test-only helpers for configured real LLM skip policy and artifact leak assertions.
- Create `tests/test_secret_scan_policy.py`: deterministic TDD tests for scanner behavior over text, files, and staged diffs.
- Create `tests/test_real_llm_integration_policy.py`: real LLM positive integration tests for `plan-experiments`, `research-loop`, and `evidence-report`.
- Modify `tests/test_llm_configured_client.py`: reuse the shared real LLM policy helper and mark the smoke as `llm_integration`.
- Modify `pyproject.toml`: register `llm_integration` and enable strict marker validation if current markers allow it.
- Modify `docs/runbook.md`: add Real LLM Test Policy commands, CI behavior, and secret-scan procedure.
- Modify `docs/roadmap.md`: add Phase 3 completion record and keep Phase 4 as next.
- Modify `docs/goals/project-completion-state.md`: move to Round 5 / Phase 3, fix stale Round 4 notes, record Phase 3 verification, and link reports.
- Create `docs/goals/phase-reports/2026-05-23-phase-2-connect-llm-research-loop-completion-report.md`: precondition repair for missing Phase 2 record.
- Create `docs/goals/phase-reports/2026-05-23-phase-3-real-llm-test-policy-completion-report.md`: Phase 3 completion report.

## Task 0: Phase 2 Record Repair

**Files:**
- Create: `docs/goals/phase-reports/2026-05-23-phase-2-connect-llm-research-loop-completion-report.md`
- Modify later: `docs/goals/project-completion-state.md`

- [ ] **Step 1: Add the missing Phase 2 completion report**

Create the missing report from current authoritative state:

- Phase name/date/objective.
- Smart Search evidence path `/tmp/smart-search-evidence/2026-05-23-phase2/`.
- Local feasibility findings from the existing Phase 2 plan.
- Files changed in commit `ae3e601 feat: connect llm to research loop`.
- Verification commands recorded in the state file: focused RED/GREEN checks, focused regressions, real smoke retry, full `770 passed`, ruff, diff checks, staged secret scan.
- Note that final subagent review was not preserved in the repository record and is treated as a documentation gap repaired by this report, not as a new code claim.

- [ ] **Step 2: Verify the report path now exists**

Run:

```bash
test -f docs/goals/phase-reports/2026-05-23-phase-2-connect-llm-research-loop-completion-report.md
```

Expected: exit code 0.

## Task 1: Secret Scanner Utility

**Files:**
- Create: `src/crypto_alpha_agent/security/__init__.py`
- Create: `src/crypto_alpha_agent/security/secret_scan.py`
- Test: `tests/test_secret_scan_policy.py`

- [ ] **Step 1: Write failing scanner tests**

Add deterministic tests:

```python
def test_secret_scan_reports_configured_secrets_without_exposing_values(tmp_path):
    secret = "cfg-test-secret-value-123456"
    base_url = "https://provider.example/root"
    findings = scan_text(
        f"Authorization: Bearer {secret} at {base_url}",
        surface="stdout",
        secret_values={"api_key": secret, "base_url": base_url},
    )
    public = json.dumps([finding.to_public_dict() for finding in findings], sort_keys=True)
    assert findings
    assert secret not in public
    assert base_url not in public
```

```python
def test_secret_scan_covers_memory_reports_artifacts_manifests_and_staged_diff(tmp_path):
    # Write files named like memory JSONL, markdown report, JSON artifact, and run manifest.
    # Assert scan_paths finds injected configured values and reports redacted surfaces only.
    # Initialize a temporary git repo, stage a file containing the secret, and assert
    # scan_git_staged_diff(repo_path=repo, ...) finds staged_diff without exposing values.
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_secret_scan_policy.py -q
```

Expected: FAIL because `crypto_alpha_agent.security.secret_scan` does not exist.

- [ ] **Step 3: Implement minimal scanner**

Implement:

- `SecretScanFinding` dataclass with `surface`, `label`, `pattern`, and `to_public_dict()`.
- `collect_sensitive_environment_values(env=None, env_file=Path(".env"))`.
- `scan_text(text, surface, secret_values=())`.
- `scan_paths(paths, secret_values=())`.
- `scan_git_staged_diff(repo_path=Path("."), secret_values=())`.
- Patterns for API-key-like values, bearer tokens, private-key blocks, seed phrases/mnemonics, and explicitly supplied configured secrets.

Rules:

- Findings must never store or print the matched value.
- `OPENAI_BASE_URL`, proxy variables, API keys, tokens, secrets, passwords, and private-key-like variable names count as sensitive configured values when scanning.
- Missing `.env` is acceptable.
- Scanner is a safety tool only; it must not read wallet keys, submit network calls, or mutate git state.

- [ ] **Step 4: Run GREEN tests**

Run the focused scanner tests and confirm PASS.

## Task 2: Real LLM Integration Policy Helpers And Positive Tests

**Files:**
- Create: `tests/llm_integration_policy.py`
- Create: `tests/test_real_llm_integration_policy.py`
- Modify: `tests/test_llm_configured_client.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing real integration policy tests**

Add tests marked with both `@pytest.mark.integration` and `@pytest.mark.llm_integration`:

```python
def test_real_plan_experiments_cli_uses_configured_llm_without_secret_leaks(...):
    # Use configured planning route and --no-offline-only.
    # Assert accepted proposal, research-only payload, no raw_response, and no secrets
    # in stdout, stderr, memory JSONL, payload JSON, or generated artifacts.
```

```python
def test_real_research_loop_cli_uses_configured_llm_without_secret_leaks(...):
    # Seed a tiny SQLite market-candle record.
    # Use configured research route and --no-offline-only.
    # Assert accepted research-only result, metadata-only raw response, and no secrets
    # in stdout, stderr, memory JSONL, or payload JSON.
```

```python
def test_real_evidence_report_cli_uses_fast_summary_llm_without_secret_leaks(...):
    # Use configured summary route and --no-offline-only.
    # Assert accepted LLM narrative summary, deterministic metrics remain present,
    # and no secrets in stdout, stderr, report Markdown, report JSON payload, or artifact paths.
```

Update the existing real configured smoke to use the shared helper and mark it `llm_integration`.

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_real_llm_integration_policy.py -q
```

Expected: FAIL because the helper and scanner are not yet wired into the tests.

- [ ] **Step 3: Implement helper and marker configuration**

Add helper functions:

- `configured_llm_settings_or_skip(role)`.
- `enable_real_llm_cli_for_pytest(monkeypatch)`.
- `secret_values_for_settings(settings)`.
- `assert_no_secret_leaks(text_surfaces, path_surfaces, settings)`.
- `assert_no_raw_response_payload(payload)`.
- `assert_research_only_payload(payload)`.

Marker policy:

- Register `llm_integration` in `pyproject.toml`.
- Keep `integration` registered.
- Enable strict marker validation if collection proves current marks are registered.

Skip policy:

- If credentials are absent, skip with a clear configuration reason.
- If `CI` is set, skip unless `CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS=1`.
- In local owner-directed runs with credentials, run the real LLM positive tests by default.
- Inside CLI tests, set `CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS=1` because the CLI resolver intentionally keeps pytest deterministic unless opted in.

- [ ] **Step 4: Run GREEN real integration tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks tests/test_real_llm_integration_policy.py -q
```

Expected with configured local credentials: all real LLM positive tests pass. If the provider fails, the failure is recorded as integration environment failure and rerun once before deciding it is an external issue.

## Task 3: Fake Adversarial Policy Coverage Check

**Files:**
- Create or modify: `tests/test_real_llm_test_policy_contract.py`

- [ ] **Step 1: Write failing policy coverage test**

Add a deterministic test that checks the repository still contains fake/injected adversarial coverage for the required categories:

- invalid JSON;
- schema violation;
- live order/live execution;
- private key/seed phrase/wallet key;
- MEV or premium RPC;
- high capital/capital-above-budget;
- malicious text redaction/no raw-response persistence.

Implementation should inspect the known test files as text and assert each category is represented by at least one deterministic fake/injected test. This is a policy contract test, not a substitute for the tests themselves.

- [ ] **Step 2: Run RED/GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_real_llm_test_policy_contract.py -q
```

Expected: initially fail until the file exists, then pass because existing fake tests already cover the required categories.

## Task 4: Documentation, State, And Completion Reports

**Files:**
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-23-phase-3-real-llm-test-policy-completion-report.md`

- [ ] **Step 1: Update runbook**

Add a Real LLM Test Policy section that documents:

- Local positive test command using real LLM credentials.
- CI/shared automation opt-in behavior.
- Fake adversarial tests remain deterministic and should not be replaced by real-model prompting.
- Secret scan command covering stdout/stderr captures, memory JSONL, Markdown/JSON reports, artifacts, run manifests, and staged diffs.
- External provider failure handling: integration environment failure, not product success.

- [ ] **Step 2: Update roadmap/state**

Roadmap:

- Mark Immediate Phase 3 as complete only after verification.
- Set Immediate Phase 4 as next.
- Preserve no-live/no-wallet/no-order/no-MEV boundaries.

State:

- Move current round to Round 5 / Immediate Phase 3.
- Fix stale Phase 2 pending-review/staged-secret wording and link the repaired Phase 2 report.
- Record Smart Search evidence, local feasibility, tests, review passes, secret-safety, commit, and next phase.

- [ ] **Step 3: Write Phase 3 completion report**

Include:

- Phase name/date/objective.
- Smart Search commands/evidence paths/fetched sources.
- Local feasibility findings and prototype results.
- Substep validation results.
- Files changed and tests added.
- Subagent assignments and findings.
- Review pass 1 and 2 results.
- Verification commands and results.
- Secret-safety result and non-staged artifacts confirmation.
- Remaining gaps and next Phase recommendation.

## Task 5: Review, Verification, Commit, Push

**Files:**
- No predetermined source files; fix any review findings in the relevant files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_secret_scan_policy.py tests/test_real_llm_test_policy_contract.py tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks tests/test_real_llm_integration_policy.py -q
```

- [ ] **Step 2: Run two subagent review passes**

Review pass 1: specification/requirements review.

Review pass 2: code-quality/secret-safety review.

Fix all Critical or Important findings and re-review after fixes.

- [ ] **Step 3: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git status --short --branch --untracked-files=all
```

- [ ] **Step 4: Stage and run staged secret checks**

Run:

```bash
git add docs src tests pyproject.toml
git diff --cached --check
git diff --cached --name-only
git diff --cached --no-ext-diff --unified=0
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

If the module has no CLI entrypoint after implementation, use the equivalent Python one-liner importing `scan_git_staged_diff(...)`.

- [ ] **Step 5: Commit and push**

Commit message:

```bash
git commit -m "test: formalize real llm policy"
git push origin main
```

## Self-Review

- Spec coverage: Phase 3 roadmap policy maps to Task 1 secret scanning, Task 2 real positive integration tests, Task 3 fake adversarial coverage contract, Task 4 docs/state/report, and Task 5 review/verification/commit.
- Placeholder scan: no task depends on an unspecified file or future API.
- Type consistency: scanner functions and helper names are defined before use in later tasks.
- Scope check: Phase 3 does not start Phase 4 evidence-run infrastructure and does not modify data ingestion, strategy validators, paper simulation, live execution, wallets, exchange orders, or MEV paths.
