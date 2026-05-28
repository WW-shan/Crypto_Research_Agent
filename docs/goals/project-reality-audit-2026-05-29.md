# Project Reality Audit - 2026-05-29

## Purpose

This audit answers the owner question: from Phase 0 through Phase 13, what was
really implemented in the repository, how it compares with the roadmap and
project goals, what remains, and whether anything drifted away from the desired
LLM-centered autonomous research tool.

Reviewed evidence:

- Phase reports under `docs/goals/phase-reports/`.
- `docs/roadmap.md`, `docs/goals/project-completion-state.md`, and
  `docs/goals/project-completion-goal.md`.
- Runtime code in `src/crypto_alpha_agent/cli.py`,
  `src/crypto_alpha_agent/config.py`, `src/crypto_alpha_agent/llm/runtime.py`,
  `src/crypto_alpha_agent/pipeline/llm_judgements.py`, evidence pipeline
  modules, strategy registry modules, and source qualification modules.
- Contract and acceptance tests under `tests/`, especially the LLM-native,
  real-LLM policy, documentation, evidence, governance, and complete evidence
  system tests.

## Executive Read

The current repository has really implemented a safe LLM-native crypto alpha
research and evidence factory. Product commands now require a configured real
LLM, run structured LLM health checks, and use strict LLM judgement schemas
around deterministic calculators and guards.

The current repository has not yet implemented the broader owner autonomy
target if that target means a tool that can independently write project code,
discover arbitrary new data sources, and run a closed autonomous
auto-iteration loop from evidence to code changes. It has bounded AI research
planning, source probes, expansion preparation, reports, governance, and
review records. It does not have an autonomous code-writing loop or autonomous
new data source discovery beyond the curated catalog and explicit probes.

## Complete Runtime Flow

1. CLI parsing starts in `crypto_alpha_agent.cli.main()`.
2. `--help`, `--version`, and `llm-health-check` are the only runtime gate
   bypasses. `llm-health-check` still builds the real runtime inside its own
   handler.
3. Every product command builds `RealLLMRuntime` through
   `build_required_real_llm_runtime()` using the command role:
   `planning` for experiment planning and schedule, `summary` for report-style
   review commands, and `research` for the remaining product commands.
4. The runtime runs a structured `LLMHealthCheckResult` health check before the
   command handler receives control. Missing configuration, provider failure,
   invalid JSON, schema failure, or missing `json_schema` and `research_only`
   capability returns exit code 2 with `side_effects_started=false`.
5. The command handler receives `args.llm_runtime`. Product success is not
   allowed through deterministic-only work.
6. Deterministic modules remain calculators and constraints. They handle data
   normalization, SQLite persistence, schema validation, source quality,
   strategy validators, paper simulation, cost model checks, risk guards,
   secret redaction, evidence ledgers, manifests, reports, and artifacts.
7. The deterministic outputs are then passed into real LLM structured tasks.
   The important judgement schemas include source research judgement, data
   readiness judgement, runtime command judgement, evidence-run interpretation,
   bootstrap interpretation, rollout readiness narrative, and report summaries.
8. LLM outputs are parsed as strict Pydantic JSON with `extra=forbid`,
   `strict=True`, and `allow_inf_nan=False`. Evidence references are checked
   against allowed refs. Unknown refs, unsafe live-capital flags, schema
   failures, or provider failures fail the command instead of becoming success.
9. Product success is reported only after the command reaches the relevant LLM
   gate. `evidence-run` may create deterministic local operation artifacts
   after LLM preflight while the run is in progress, but if command-level LLM
   interpretation fails, the run is finalized as a failed run rather than a
   successful product result. It also uses locking, manifests, latest pointers,
   and failed-run markers for operational recovery.
10. `schedule` produces an operator-controlled schedule plan. It is not an
    always-on daemon. External cron, systemd, or another operator runner owns
    repeated execution.

## Really Implemented From Phase 0 To Phase 13

| Phase | Really implemented | Reality check |
| --- | --- | --- |
| Phase 0: worktree and configuration closeout | Local tool directories and `.env` handling were documented and kept out of git. Accidental draft LLM test state was cleaned before the formal LLM work. | Documentation and hygiene phase. No product research capability was supposed to be added here. |
| Phase 1: real LLM adapter | `LLMSettings`, model role routing, required real LLM builder, Responses-compatible adapter, redaction, and real smoke coverage were added. | Initially adapter-only. Later LLM-native work made it mandatory for product commands. |
| Phase 2: connect LLM research loop | `plan-experiments`, `research-loop`, and report summary paths were connected to the configured LLM with strict schemas and metadata-only raw response handling. | LLM became useful for bounded research, but still did not get execution or code-change authority. |
| Phase 3: real LLM test policy | Real LLM integration/core acceptance markers and secret-safety rules were added. Fake LLM coverage was retained for adversarial invalid-output cases. | Now superseded by fail-closed real LLM acceptance for product paths. |
| Phase 4: evidence-run infrastructure | `evidence-run` can run ingestion, validation, paper simulation, memory feedback, daily/weekly artifacts, locks, manifests, latest pointers, and failure markers. | Operational infrastructure exists. Long-running evidence collection still requires repeated operator runs over time. |
| Phase 5: data and strategy expansion preparation | `expansion-prep-report` ranks source and strategy candidates and fails closed when source health, typed records, or adapters are missing. | This is preparation and ranking, not autonomous source discovery or automatic implementation. |
| Phase 6: merged entry gate | Phase 6 was merged into Phase 0 and Phase 1 readiness. | No standalone product phase. |
| Phase 7: final evidence campaign bootstrap | `historical-bootstrap` evaluates historical windows, reports source collection/probe status, classifies strategy results, and sets 30/60/90 out-of-sample targets. | Historical bootstrap exists. The 30/60/90 out-of-sample paper observations have not been accumulated yet. |
| Phase 8: data depth and quality expansion | Source qualification, proxy-aware source health, open-interest records, CCXT open-interest ingestion, source-probe catalog, source coverage matrix, and query catalog were added. | Source probing is catalog-driven. `ProductionResearchSource` still requires repeated canary evidence over time. |
| Phase 9: strategy validator library expansion | Three executable paper-simulated families and three watchlist-only families are registered. Funding/open-interest crowding and volatility watchlist were added. | Broader candidates such as cross-exchange dispersion and basis/carry remain blocked until data and cost assumptions are qualified. |
| Phase 10: execution realism and cost model | Paper simulation includes fees, slippage, min notional, precision, stale-signal, missed-fill, partial-fill, funding alignment, and pre-cost-only-profit rejection. | This is a strong guardrail layer, not live execution. |
| Phase 11: AI researcher upgrade | Evidence context, stricter experiment proposal schema, duplicate rejection, design-only strategy template proposals, hallucination guards, and `ai-research-memo` were added. | AI can propose bounded experiments and validator designs. It cannot directly write code, create paper outcomes, or add unverified data. |
| Phase 12: profit evidence review and governance | `governance-report` builds family scoreboards, stopped-family ledger, paper-only portfolio selector, and owner review actions. | Governance decisions are evidence review artifacts. They do not allocate real capital. |
| Phase 13: continuous research review | Daily, weekly, monthly review reports and a decision log inspect reports, evidence packages, AI memos, scoreboards, stopped-family ledgers, and artifacts. | Phase 13 is read-only review and reporting, not new product execution logic. |
| LLM-native runtime after Phase 13 | Product commands require real LLM preflight and structured LLM judgement. Deterministic-only success paths and optional offline LLM flags were removed from product runtime. | This fixed the major drift where deterministic code could previously be considered product success without real LLM participation. |

## Roadmap And Goal Comparison

Really achieved against the current charter and roadmap:

- Real public-data ingestion foundations for Binance Public Data, CCXT,
  DexScreener, DefiLlama, and optional Dune/The Graph paths.
- Durable local SQLite storage, normalized records, source health, and data
  quality checks.
- Scanner, anomaly, hypothesis, memory, validation, paper simulation, reports,
  governance, rollout review, replay, and scheduler handoff.
- Three executable strategy families plus three watchlist families.
- Execution-realistic paper simulation and conservative cost/risk guards.
- LLM-native runtime gate and strict structured LLM judgements.
- AI planning and AI research memo paths constrained to evidence and registered
  validators.
- No live execution, no wallet keys, no order routing, no real capital, no MEV,
  no premium RPC dependency, and no speed-edge path.

Remaining gaps against the owner autonomy target:

- Autonomous code-writing loop: not yet implemented. The current AI can propose
  design-only strategy templates and experiments, but it does not edit project
  code, create patches, run tests on its own branch, or open reviewable change
  sets.
- Autonomous new data source discovery: not yet implemented. The current
  system has a curated source-probe catalog, source coverage matrix, and query
  catalog. It does not independently search the web for new providers, verify
  docs, probe schemas, and add them to the project as candidates.
- Auto-iteration loop: not yet implemented as one closed product command. The
  pieces exist separately: source-probe, ingest, evidence-run, evidence-report,
  governance-report, plan-experiments, ai-research-memo, historical-bootstrap,
  and review records. There is no controller that repeatedly runs them,
  compares the result to goals, creates the next candidate, and gates the next
  iteration.
- Long-running profit evidence: not yet complete. Historical bootstrap exists,
  but 30/60/90 out-of-sample paper observations still need elapsed operation.
- Live trading: intentionally not implemented and still outside the current
  charter. There is no live order routing and no wallet-key access.

## Drift Or Design Deviations

Fixed drift:

- The earlier product story could still sound deterministic-only because many
  commands had deterministic local paths. The LLM-native runtime work corrected
  this: product commands now require real LLM preflight and structured LLM
  judgement.

Current intentional deviation from the owner's newer autonomy wording:

- The repository is not yet a self-coding autonomous development agent. That is
  a real gap if the desired product is "write code by itself." The current
  safer design keeps AI at bounded proposal and critique authority while code
  changes still require a normal implementation process, tests, and review.
- The repository is not yet an autonomous source-discovery agent. It can probe
  registered targets and rank expansion candidates, but it cannot independently
  find unknown new sources and integrate them.
- The scheduler is external by design. The project can produce schedule plans
  and run one-shot evidence commands, but it is not an always-on daemon.

Not drift:

- Keeping deterministic modules is correct. Data normalization, schema
  validation, source quality, strategy validators, paper simulation, cost model,
  risk guard, secret redaction, and evidence ledger are necessary calculators
  and constraints inside the LLM-native flow.
- Keeping live execution blocked is consistent with the charter and the low
  capital, ordinary-infrastructure owner profile.

## Recommended Next Design Line

The next meaningful phase should be explicitly named around the broader owner
target, for example:

`Phase 14: LLM-Native Autonomous Iteration Controller`

Minimum safe scope:

- Add an LLM-required command that reads source health, evidence reports,
  governance actions, AI memos, memory, and roadmap goals.
- Produce strict `IterationCandidate` records for:
  `new_data_source`, `new_strategy_validator`, `validator_change`,
  `experiment_parameter_change`, or `code_change_request`.
- Keep deterministic gates for source quality, evidence refs, charter
  constraints, cost/risk checks, test requirements, and secret redaction.
- For code changes, start with patch plans and required tests rather than
  unsupervised direct mutation. Direct self-editing should require a separate
  safety design with branch isolation, patch review, test execution, rollback,
  and owner approval.
- If the real LLM connection or structured LLM validation fails, the iteration
  command must fail closed and must not write success artifacts.

This next line would move the project toward the owner target without weakening
the current safety and evidence boundaries.
