# Project Completion State

This file is the working memory for the long-running Codex Goal defined in
`docs/goals/project-completion-goal.md`. Update it at the end of every completed
round.

## Current Round

- Round: 5
- Status: Immediate Phase 3 complete; commit and push pending
- Started: 2026-05-23
- Completed: 2026-05-23
- Active slice: Immediate Phase 3: Real LLM Test Policy
- Active plan source:
  `docs/superpowers/plans/2026-05-23-phase-3-real-llm-test-policy.md`
- Phase report:
  `docs/goals/phase-reports/2026-05-23-phase-3-real-llm-test-policy-completion-report.md`

## Completed This Round

- Ran Phase 3 Smart Search deep research and fetched pytest marker/skip docs,
  GitHub Actions secret docs, OpenAI production guidance, and Context7 pytest
  marker references.
- Verified local feasibility from the current worktree:
  - only one real LLM integration test existed before Phase 3;
  - `plan-experiments`, `research-loop`, and `evidence-report` already had real
    LLM CLI wiring from Phase 2;
  - fake adversarial tests existed but were not formalized as a test-policy
    contract;
  - Phase 2's completion report was referenced but missing from the repository.
- Added `crypto_alpha_agent.security.secret_scan` for redacted scanning of
  text, paths, and staged diffs.
- Added shared real LLM test helpers in `tests/llm_integration_policy.py`.
- Added real positive LLM integration tests for:
  - configured adapter smoke;
  - `plan-experiments`;
  - `research-loop`;
  - `evidence-report`.
- Added `llm_integration` pytest marker and strict marker validation.
- Added a deterministic policy contract that fake/injected adversarial coverage
  remains present for invalid JSON, schema violations, live-order/private-key,
  MEV/premium-RPC, high-capital, and raw-response metadata-only cases.
- Debugged real LLM failures and strengthened schema hints to avoid prohibited
  execution terms in free-text values.
- Relaxed evidence-report summary list bounds to tolerate useful real summaries
  while preserving bounded schema validation.
- Repaired the missing Phase 2 completion report.
- Updated the runbook and roadmap for the Phase 3 test policy.

## Verification Evidence

- Smart Search:
  `/tmp/smart-search-evidence/2026-05-23-phase3-real-llm-test-policy/`
  contains `00-doctor.json`, `01-deep-plan.json`, `02-broad-search.json`,
  `03-pytest-markers.md`, `04-pytest-skipping.md`,
  `05-github-actions-secrets.md`, `06-openai-production-best-practices.md`,
  and `08-context7-pytest-docs.json`.
- Initial integration collection:
  `uv run --extra dev pytest --collect-only -q -m integration` collected 1
  integration test before Phase 3 implementation.
- Initial real LLM smoke:
  `uv run --extra dev pytest tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks -q`
  passed with 1 test before Phase 3 implementation.
- Secret scanner RED/GREEN:
  `uv run --extra dev pytest tests/test_secret_scan_policy.py -q` failed first
  because `crypto_alpha_agent.security` did not exist, then later passed with 6
  tests after adding regression coverage for path and label redaction.
- Real LLM policy RED:
  `uv run --extra dev pytest tests/test_real_llm_integration_policy.py tests/test_real_llm_test_policy_contract.py -q`
  failed first because `llm_integration_policy` did not exist.
- Real LLM debugging:
  the first real policy run exposed `charter_violation` in planner output and
  `invalid_summary` in evidence-report output; schema hints and summary bounds
  were adjusted. Later review exposed transient provider `504` failures,
  public finding label leakage, weak adversarial policy checks, and a false
  safety-echo normalizer that could mask an unsafe follow-on instruction; all
  were fixed and re-reviewed.
- Focused Phase 3 verification:
  `uv run --extra dev pytest tests/test_secret_scan_policy.py tests/test_real_llm_test_policy_contract.py tests/test_evidence_reports.py::test_report_summarizer_accepts_common_caveats_alias_without_extra_raw_text tests/test_evidence_reports.py::test_report_summarizer_normalizes_false_safety_flag_echoes_without_raw_text tests/test_evidence_reports.py::test_report_summarizer_rejects_valid_unsafe_instruction_without_raw_text tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks tests/test_real_llm_integration_policy.py -q`
  passed with 16 tests.
- Real LLM marker collection:
  `uv run --extra dev pytest --collect-only -q -m llm_integration` collected 4
  real LLM integration tests and deselected 781 tests.
- Review pass 1 (spec/requirements) and review pass 2
  (code-quality/secret-safety) found no Critical issues. Important issues were
  fixed, and targeted re-review reported no Critical, Important, or Minor
  findings.
- Full tests:
  `uv run --extra dev pytest -q` passed with 785 tests.
- Ruff:
  `uv run --extra dev ruff check .` passed with `All checks passed!`.
- Diff check:
  `git diff --check` passed.
- Staged checks:
  `git diff --cached --check` passed.
- Staged secret-safety:
  `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`
  passed with `[]`.

## Current Project Target

The first complete safe research-loop milestone is complete for the current
charter:

- public-data ingestion;
- local durable SQLite storage;
- scanner and anomaly detection;
- hypothesis generation and reflection;
- deterministic historical validation;
- paper simulation and evidence accumulation;
- validation and paper memory feedback;
- daily and weekly evidence reports;
- bounded AI experiment planning;
- degradation and stop rules;
- rollout review artifacts with `live_execution_enabled=false`.

## Known Hard Boundaries

- No wallet-key access.
- No live order routing.
- No exchange order submission.
- No real-capital execution.
- No MEV, mempool, bridge-race, flash-loan, premium-RPC, or speed-edge
  strategies.
- No secrets in git or public GitHub.

## Known Remaining Gaps

The first complete research-loop milestone remains complete under the current
charter. Post-milestone Phase 0, Immediate Phase 1, Immediate Phase 2, and
Immediate Phase 3 are complete. Phase 3 still requires commit and push before
the next Phase may start.

Future work is now ordered as an evidence-factory buildout before the formal
evidence campaign:

- Immediate Phase 4-5: keep evidence-run infrastructure operable while
  preparing data and strategy expansion.
- Phase 8: qualify and deepen public data sources, including proxy-aware
  source probes.
- Phase 9: expand deterministic strategy validators and watchlists.
- Phase 10: make paper/backtest results execution-realistic after costs.
- Phase 11: upgrade the AI researcher to reason from evidence without bypassing
  validators.
- Phase 12: add portfolio/governance scoring for profit/no-profit decisions.
- Phase 7: only after Phases 8-12, run historical bootstrap and then collect
  future out-of-sample paper observations.
- Phase 13: perform read-only review of generated reports, evidence packages,
  AI memos, strategy scoreboards, and finished artifacts, then write review
  reports and decision records that judge whether the system is improving
  profit research effectiveness.

Live execution remains outside the current charter until a future explicit
charter revision.

## Next Round Entry Instructions

If work continues after Phase 3:

1. Read `docs/project-charter.md` before any new plan.
2. Read `docs/goals/project-completion-goal.md` and follow its Per-Round
   Execution Protocol exactly: Smart Search deep research before design,
   local code-feasibility verification before planning, evidence-first substep
   gates for every meaningful added capability, one Phase per round,
   Superpowers workflows, subagent use, repeated review/fix/re-review cycles,
   state synchronization, a complete Phase report under
   `docs/goals/phase-reports/`, and no next Phase until the current Phase is
   clean, verified, committed, and pushed.
3. Read the "Immediate Sequence: Worktree Then Real LLM" section in
   `docs/roadmap.md`.
4. Treat Phase 6 as merged into Immediate Phase 0 / Immediate Phase 1 entry
   readiness, not as a later standalone feature phase.
5. Start with Immediate Phase 4: Evidence Run Infrastructure. Phase 3
   formalized real LLM integration tests, fake adversarial policy coverage, and
   secret-scan tooling. Do not reimplement Phase 1, Phase 2, or Phase 3.
6. Treat live execution, wallet keys, exchange order routing, private RPC,
   MEV, and speed-edge paths as blocked unless the owner explicitly revises the
   charter.
7. Use the Phase 1/2 model routing: research/planning/code use the configured
   strong model and report/summary use the configured fast model. Preserve fake
   LLM tests for deterministic adversarial cases, and make real positive tests
   explicit and secret-safe.
8. Use the local proxy variables in `.env` for public-data endpoints that fail
   direct probing, and record source health as direct, proxy, or failed.
9. Build Phase 8, Phase 9, Phase 10, Phase 11, and Phase 12 before starting the
   formal Phase 7 evidence campaign.
10. In Phase 7, first run historical bootstrap over qualified data, then treat
    future daily evidence as out-of-sample confirmation or rejection.
11. Use Phase 13 as a read-only report/artifact effectiveness review loop that
    produces review reports and decision records, not as a code implementation
    or tiny-live phase.
12. Prefer evidence-factory quality and validator expansion over new agent
    framework work.
13. Keep failed evidence and rejected assumptions in memory.
14. Update this file and `docs/roadmap.md` after any future milestone.

## Round History

| Round | Date | Slice | Verification | Commit | GitHub |
| --- | --- | --- | --- | --- | --- |
| 0 | 2026-05-17 | Goal contract bootstrap | pytest 676 passed; ruff passed; diff check passed; staged secret review passed | Goal bootstrap docs slice | public repo target |
| 1 | 2026-05-17 UTC / 2026-05-18 local | Complete autonomous evidence system milestone | pytest 750 passed; ruff passed; diff check passed; focused source tests 52 passed; forbidden-path review found no production live path | `fb1635d281f33e93a6723832bdf04a115e160c86` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 2 | 2026-05-23 | Immediate Phase 0 / merged Phase 6 worktree and configuration closeout | focused Phase 0 checks 8 passed; pytest 750 passed; ruff passed; diff check passed; staged secret review passed | Phase 0 completion commit `docs: complete phase 0 closeout` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 3 | 2026-05-23 | Immediate Phase 1 real LLM adapter | tests 762 passed; ruff passed; diff check passed; staged secret review passed | Phase 1 completion commit `feat: add real llm adapter` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 4 | 2026-05-23 | Immediate Phase 2 connect LLM to research loop | tests 770 passed; ruff passed; diff check passed; staged secret review passed | `ae3e601 feat: connect llm to research loop` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 5 | 2026-05-23 | Immediate Phase 3 real LLM test policy | focused Phase 3 tests 16 passed; pytest 785 passed; ruff passed; diff check passed; staged secret review passed | pending Phase 3 commit `test: formalize real llm policy` | `https://github.com/WW-shan/Crypto_Research_Agent` |
