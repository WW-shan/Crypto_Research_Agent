# Roadmap

This roadmap is the living plan for turning the current research kernel into a
low-capital crypto alpha research system. It should be updated after each major
implementation phase.

The project charter in `docs/project-charter.md` is the governing constraint for
this roadmap.

The standing owner profile remains profit-first research with only a few hundred
USD, ordinary public APIs/RPC, no speed edge, no MEV or premium infrastructure,
and research plus paper validation before any live capital.

## Current Baseline

Implemented:

- LangGraph orchestration skeleton with loops, branch routing, checkpoint hooks,
  human checkpoint behavior, and deterministic regression coverage.
- Canonical opportunity and research state models.
- Market scanner, anomaly detector, hypothesis generator, feasibility scoring,
  strategy coder sandbox, reflection, memory, ranking, paper execution, risk
  guardian, rollout gates, observability, CLI smoke commands, and end-to-end
  deterministic tests.
- Real-data ingestion foundations:
  - Binance Public Data historical candle client.
  - CCXT OHLCV and funding-rate collector.
  - DexScreener discovery client.
  - DefiLlama yield-pool client.
  - SQLite research data store.
  - Scanner bridge for candles, funding rates, DEX pairs, DeFi yields, stored
    records, and JSON payloads.
  - Safe `ingest` CLI that defaults to offline initialization and requires
    `--allow-network` for source declarations.
- Stored-data research loop:
  - `research-loop` command that loads stored records, scans signals, runs
    anomaly detection, generates research-only hypotheses, and records loop
    artifacts.
  - Gated Binance Public Data historical candle ingestion through
    `research-loop` with explicit `--allow-network`.
  - Optional Markdown report artifact written with `--report-out`.
- Historical validation foundations:
  - Persisted candle history loader for stored market candles.
  - Conservative close-momentum validator over stored candle bars.
  - Funding-rate extremity validator for stored funding records.
  - Funding-plus-price validator for the first strategy family.
  - Walk-forward train/test window utility.
  - Hard walk-forward gate for the first strategy family before paper evidence
    consideration.
  - Optional `--include-validation` research-loop summaries in JSON and
    Markdown reports.
- Closed-loop MVP foundations:
  - Charter-constrained prompts, LLM contract models, and guardrails for
    research-only proposals.
  - Fake-LLM-tested research adapter plus an opt-in LangGraph LLM research loop.
  - Memory persistence for generated and blocked hypotheses.
  - Local dry-run scheduler planning with explicit network controls.
  - Paper evidence aggregation and a paper eligibility gate.
  - Tiny-live readiness artifact generation only, with documented tiny-live
    controls in `docs/tiny-live-readiness.md`.
- Evidence system operations:
  - `evidence-run` one-shot pipeline for daily research, paper simulation, and
    evidence artifact generation.
  - Product-level `evidence-run` locking, run manifests, JSON payloads, latest
    pointers, failed-run markers, and source-health network-route recording.
  - `plan-experiments` for bounded operator-facing experiment planning.
  - `evidence-report` daily and weekly Markdown builders.
  - `governance-report` profit governance Markdown builder with family
    scoreboards, stopped-family ledger, paper-only portfolio selector, and
    monthly owner review.
  - `rollout-review` CLI that preserves the strategy-specific evidence package.
  - External operator-controlled scheduling handoff documented in the runbook.

Current limits that remain outside the completed safe research-loop milestone:

- Historical validation covers the initial low-capital strategy families and
  the first executable paper-simulated funding family. A broader strategy
  library is future expansion, not a blocker for the first milestone.
- The LLM loop is opt-in and constrained to research contracts; it is not a
  substitute for historical validation or paper evidence.
- The scheduler remains operator-controlled and dry-run only, but the runbook
  now documents a complete scheduling handoff for `evidence-run`.
- External scheduler remains operator-controlled even though the runbook now
  documents complete scheduling handoff details for `evidence-run`.
- Paper simulation, outcome ledger, evidence reporting, and memory feedback are
  operational. Longer paper evidence collection is still required before any
  tiny-live review can even be considered.
- There is no live execution path, no wallet-key access, no exchange order
  routing, and the system should not deploy capital.

## Phase 1: Real Data Closed-Loop MVP - Complete

Goal: Run a full local research loop from real data to a daily report without
live trading.

Delivered:

- `research-loop` can explicitly pull Binance Public Data historical candles
  with `--allow-network`.
- Normalized records and loop artifacts are persisted into SQLite.
- Stored records are loaded and converted into scanner signals.
- Anomaly detection and hypothesis generation run over stored data.
- A Markdown daily report can be generated from the run.

Completion evidence:

- One command can run a safe local pipeline for a limited source/symbol set.
- The command writes durable data and a reproducible report.
- No wallet keys, exchange order routing, or live capital are touched.

Example command:

```bash
uv run crypto-alpha-agent research-loop \
  --db var/research.sqlite \
  --source binance-public \
  --symbol BTCUSDT \
  --timeframe 1h \
  --year 2026 \
  --month 5 \
  --current-capital-usd 300 \
  --allow-network \
  --report-out var/reports/daily.md
```

## Phase 2 Strategy Validation Expanded - Complete For First Milestone

Goal: Validate simple low-capital strategy families against real historical
data before any paper proposal.

Delivered:

- Stored Binance Public Data candles can be loaded as typed chronological bars.
- A conservative close-momentum validator produces trade count, net return, max
  drawdown, and fee/slippage-adjusted expectancy.
- Stored funding-rate records can be summarized for positive and negative
  funding extremes.
- The first strategy family has an implemented funding-plus-price validator and
  a hard walk-forward gate before paper evidence consideration.
- `research-loop --include-validation` can attach historical validation
  summaries to JSON and Markdown reports.

Initial strategy families:

- Funding-rate extremity plus price momentum filter.
- Funding-rate mean reversion after extreme prints.
- DeFi yield regime change filter with TVL and liquidity constraints.
- DEX pair liquidity/volume anomaly watchlist, used for observation rather than
  direct execution.

Completion evidence:

- Initial strategy families are registered with deterministic validation or
  research-watchlist adapters.
- Results include fees, slippage assumptions, trade count, max drawdown, and
  expectancy where applicable.
- Walk-forward or out-of-sample splits are applied before paper approval.
- Strategies that fail are persisted with rejection reasons.

Future Phase 2 expansion:

- Extend combined validators and hard walk-forward gates beyond the first
  funding-plus-price strategy family.
- Add enough strategy-family evidence before any paper-trading gate is
  considered.

## Phase 3: LLM Research Agent Loop - Complete

Goal: Move from static templates to an AI-assisted research loop that proposes
and critiques hypotheses while staying inside the charter.

Delivered:

- Charter-constrained prompt templates for supervisor, scanner, hypothesis
  generator, coder, and reflexion roles.
- Strict LLM research contract models that default to research-only behavior
  and reject live-order, private-key, high-capital, MEV, premium-RPC,
  bridge-race, flash-loan, and speed-edge instructions.
- Fake-LLM research adapter with deterministic tests for valid, invalid, and
  unsafe model output.
- Opt-in LangGraph LLM research loop that guards proposals, requests
  validation, critiques evidence, persists memory, and routes paper suggestions
  to human review rather than execution.

Completion standard:

- Agents can generate candidate research tasks from stored real data.
- Every generated strategy includes explicit assumptions and disconfirming
  evidence.
- Generated code is sandboxed and cannot access wallets, shell, or unrestricted
  network.

## Phase 4 Evidence Accumulation Operational - Complete For First Milestone

Goal: Collect paper-trade evidence only for strategy families that passed
historical validation.

Delivered:

- Deterministic `paper-sim-loop` command for the funding extremity plus price
  confirmation strategy family.
- Persisted paper outcome ledger for simulated closed and blocked outcomes.
- Aggregation of persisted paper outcomes into strategy evidence packages.
- Paper evidence reports attached to the stored-data research loop.
- Paper eligibility gate that requires sufficient clean evidence before a
  candidate can be considered for paper approval.
- Failure tracking for paper evidence normalization and eligibility decisions.
- Paper outcome memory feedback so blocked and failed simulations can inform
  future research filtering.
- Daily and weekly evidence reports are operational.
- `evidence-run` can drive the daily paper loop, memory feedback, and report
  generation in one operator-controlled command.

Future Phase 4 expansion:

- Add broader charter-compliant strategy families beyond the initial funding
  extremity plus price confirmation slice.
- Run longer paper collection for narrow, charter-compliant strategy families.
- Expand evidence coverage across fees, slippage, liquidity, stale signals, and
  overfit behavior.
- Optionally add ordinary public data sources when they improve evidence quality
  without adding speed-edge, premium infrastructure, or live-trading
  dependencies.

Completion standard:

- Each paper candidate has a minimum sample size requirement.
- The system tracks net expectancy, drawdown, hit rate, and failure reasons.
- Candidates that degrade are automatically removed from paper consideration.

## Completed Legacy Phase 5: Tiny Live Readiness Review - Artifact Only

Goal: Decide whether a narrow strategy family is ready for tiny live testing.

This is completed historical scope. The current immediate Phase 5 is the
separate Data And Strategy Expansion preparation slice below.

Delivered:

- Tiny-live readiness artifact generation from rollout gates, paper evidence,
  notional limits, and human approval status.
- Readiness artifacts can record both blocking and passing review outcomes.
- Tiny-live controls are documented in `docs/tiny-live-readiness.md`.

Remaining scope:

- This phase still does not include live execution, wallet access, order
  routing, or capital deployment.
- Live readiness remains blocked until repeated paper evidence passes rollout
  gates for a narrow low-capital strategy family and a human explicitly
  approves.

Completion standard:

- No live path exists until the strategy-specific evidence package passes.
- Live readiness is a review artifact, not an automatic transition.
- A kill switch and max-loss limit are defined before any live test.

## Active Next Step

The first complete safe research-loop milestone is complete. The repository now
has a tested local loop for public-data ingestion, scanner/anomaly/hypothesis
generation, deterministic validation, paper simulation, evidence memory,
daily/weekly/governance reports, bounded experiment planning, degradation stop
rules, and rollout-review artifacts with live execution disabled.

The next practical work is operational evidence collection over time and
incremental strategy-library expansion where it improves slow-to-medium
frequency research. Do not pivot to speed arbitrage, MEV, premium
infrastructure, high-capital strategies, or live trading. The remaining blocked
item is live execution until future charter revision, specifically a future
explicit charter revision by the owner.

The roadmap below is the post-milestone work needed to move from "working
evidence factory" to "profit evidence." None of these phases should weaken the
charter. A phase is complete only when it improves the system's ability to
prove or reject a money-making edge under the owner's low-capital constraints.

## Post-Milestone Roadmap: Profit Evidence Gaps

The main gap is not another agent framework. The main gap is that no strategy
family has yet accumulated enough real paper evidence to prove that it can
survive fees, slippage, data gaps, stale signals, low capital, and ordinary
infrastructure.

The next work therefore has seven priorities:

1. Close the current worktree and local-configuration state before more code
   changes.
2. Connect the local real LLM configuration so AI research work uses the
   owner's configured models instead of only injected fake callables.
3. Make the network route explicit. Some public crypto endpoints are reliable
   only through the operator's local proxy, so source health must distinguish
   direct success, proxy success, and provider failure.
4. Expand slow public-data coverage where it improves validation quality.
5. Add deterministic validators for more low-capital strategy families.
6. Make backtests and paper simulations more execution-realistic.
7. Upgrade AI research and governance so evidence can be interpreted and
   rejected systematically.
8. Run the historical bootstrap and long-running evidence campaign only after
   the data, validators, cost model, AI researcher, and governance layers are
   strong enough to make the results meaningful.
9. Keep live execution blocked and use the final phase for continuous review of
   research reports, evidence packages, and finished artifacts so the owner can
   judge whether the system is actually improving the chance of making money.

### Immediate Sequence: Worktree Then Real LLM

This immediate sequence is complete through Immediate Phase 4. Immediate Phase
5 prepares data and strategy expansion before long-running evidence collection
is treated as operational.

The execution order after the immediate LLM work is intentionally not numeric:
Phase 6 is merged into the Phase 1 entry gate, Immediate Phase 5 prepares the
expansion path, then Phase 8, Phase 9, Phase 10, Phase 11, and Phase 12 build
the evidence factory. Phase 12 is now complete, so Phase 7 runs the historical
bootstrap and future out-of-sample evidence campaign, and Phase 13 becomes the
ongoing report and artifact review loop.

#### Immediate Phase 0: Worktree And Configuration Closeout

Goal: Start the next implementation from a clean, explainable local state.

Status as of 2026-05-23: complete after the Phase 0 closeout round. `.agents/`
and `.claude/` are treated as local-only AI-tool directories and ignored by the
repository. `.env` remains local and ignored. The accidental
`tests/test_llm_configured_client.py` draft was removed so Immediate Phase 1 can
recreate LLM adapter tests under its own TDD plan.

Required actions:

- Decide whether `.agents/` and `.claude/` are local-only tool directories. If
  they are local-only, add ignore rules or a short operator note; if they are
  product tooling, document and commit them deliberately.
- Keep `.env` local and ignored. It may contain real LLM credentials, but those
  credentials must never be staged, committed, logged, copied into reports, or
  persisted into memory.
- Preserve the local LLM configuration keys:
  `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`,
  `OPENAI_RESEARCH_MODEL`, `OPENAI_CODER_MODEL`, and `OPENAI_FAST_MODEL`.
- Record that the current preferred model routing is:
  research/planning/code uses `gpt-5.5`; fast report/summary work uses
  `gpt-5.4-mini`.
- Preserve the local proxy configuration for public data endpoints that fail
  or timeout on the direct route:
  `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, lowercase proxy variants,
  `NO_PROXY`, and `CRYPTO_ALPHA_AGENT_PROXY`.
- Treat the local proxy as operator configuration, not product infrastructure.
  It may be used for data collection and source probes, but it must not become
  a speed edge, private RPC dependency, or live execution path.
- Handle any accidental pre-plan files explicitly. The current
  `tests/test_llm_configured_client.py` draft must either be deleted before
  the formal plan starts or incorporated into the approved Phase 1 TDD plan.
- Commit the roadmap and state-document updates separately from LLM adapter
  implementation.

Completion standard:

- `git status --short` before Phase 1 shows only deliberate files.
- `.env` is ignored and not staged.
- No API key, bearer token, private key, seed phrase, generated report, SQLite
  database, cache, or local artifact is staged.

#### Immediate Phase 1: Real LLM Adapter

Goal: Make the code actually use the owner's local OpenAI-compatible LLM
configuration.

Required implementation:

- Add `LLMSettings` that reads local `.env` and environment variables.
- Add an OpenAI-compatible Responses client adapter for the configured
  `OPENAI_BASE_URL`.
- Support model routing:
  - default/research/planning: `OPENAI_RESEARCH_MODEL` falling back to
    `OPENAI_MODEL`;
  - coder/validator-design: `OPENAI_CODER_MODEL` falling back to
    `OPENAI_MODEL`;
  - report/summary: `OPENAI_FAST_MODEL` falling back to `OPENAI_MODEL`.
- Treat real LLM as the default operator path once credentials are configured.
  Keep explicit `--no-llm`, `--offline-only`, or test injection hooks only for
  disabled/offline runs and deterministic safety tests.
- Redact credentials from all exceptions, logs, memory records, reports,
  scheduler plans, and test output.
- Expected file areas:
  `src/crypto_alpha_agent/llm/`, `src/crypto_alpha_agent/config.py`,
  `tests/test_llm_configured_client.py`, and `docs/runbook.md`.

Completion standard:

- A real LLM smoke test can call the configured endpoint and return a valid
  research proposal.
- The configured route supports the owner's model split:
  research, planning, and code use `gpt-5.5`; fast summaries use
  `gpt-5.4-mini`.
- The adapter does not print the key, raw authorization headers, provider
  response headers, or other credential-bearing metadata.
- Missing credentials fail closed with a clear local-configuration error when
  real LLM is required.
- The adapter can be tested without printing or persisting the API key.
- Fake adversarial tests remain for invalid JSON, schema violations, live
  order requests, private-key requests, MEV, premium RPC, high capital, and
  other unsafe outputs.

Phase 1 completion record: implemented by
`docs/goals/phase-reports/2026-05-23-phase-1-real-llm-adapter-completion-report.md`.
The adapter remains research-only and is not wired into Phase 2 research-loop,
plan-experiments, evidence-run, report-summary, memory-persistence, or
execution/live paths yet.

#### Immediate Phase 2: Connect LLM To The Research Loop

Goal: Use the real LLM as a research assistant across the existing evidence
workflow without granting execution authority.

Required integration points:

- `plan-experiments` uses `gpt-5.5` by default to propose bounded next
  experiments from validation evidence, paper evidence, stopped-family memory,
  and blocked parameter sets.
- `research-loop` can use `gpt-5.5` to generate stronger research hypotheses
  from stored records, scanner signals, anomaly rankings, and validation
  summaries.
- `evidence-report` can use `gpt-5.4-mini` to add concise daily and weekly
  narrative summaries while preserving deterministic metrics as source of
  truth.
- Coder/validator design flows use `gpt-5.5` only to produce candidate design
  text or draft code for human/TDD implementation. They must not execute code,
  write live adapters, or bypass review.

Completion standard:

- `plan-experiments` can make a real call to the configured `gpt-5.5` route
  when credentials are present and real LLM mode is enabled.
- Real LLM output is parsed through strict schemas.
- Invalid, unsafe, or unverifiable LLM output is rejected and persisted as
  rejected memory metadata.
- LLM raw responses are not stored in memory by default; metadata, hash,
  length, status, and rejection reasons are enough.
- Report summaries never overwrite or reinterpret deterministic validation,
  paper, source-health, or cost metrics.

Phase 2 completion record: implemented by
`docs/goals/phase-reports/2026-05-23-phase-2-connect-llm-research-loop-completion-report.md`.

Completed behavior:

- `plan-experiments` now resolves the configured planning LLM by default in
  operator runs, passes proposals through the existing strict
  `ExperimentProposal` parser and charter guard, and persists rejected LLM
  output as metadata-only memory.
- `research-loop` can invoke the configured research LLM through the existing
  LangGraph LLM research graph and write only metadata/hash/length status for
  raw responses.
- `evidence-report` can invoke the configured fast summary model to add an
  optional `LLM Narrative Summary` section without changing deterministic
  validation, paper, memory, source-health, or cost metrics.
- `--offline-only` keeps deterministic behavior, while `--no-offline-only`
  requires a configured real LLM and fails closed if local credentials are
  missing.
- No live trading, wallet-key access, exchange order routing, MEV, premium RPC,
  or speed-edge execution path was added.

#### Immediate Phase 3: Real LLM Test Policy

Goal: Use the owner's real LLM for meaningful integration tests while keeping
deterministic adversarial tests for safety boundaries.

Testing policy:

- Positive integration and smoke tests should use the real configured LLM when
  credentials are available. This includes real `plan-experiments`, real
  research proposal generation, and real report-summary paths.
- Do not skip real LLM calls merely to save token budget during local
  development when the owner has requested real-model testing.
- Keep a small set of fake/injected LLM tests for cases that real models cannot
  reliably produce on demand:
  invalid JSON, schema violations, live-order requests, private-key requests,
  MEV or premium-RPC requests, high-capital requests, and malicious text that
  must be rejected by guards.
- Any test that uses a real LLM must assert that the API key and base URL are
  not copied into stdout, stderr, memory, reports, or generated artifacts.
- CI may remain fake/offline unless the operator explicitly provides local
  credentials and enables real LLM integration tests.

Completion standard:

- Real LLM tests prove the configured endpoint works.
- Fake adversarial tests prove the guardrails work.
- Neither test class leaks credentials or creates live execution authority.
- Secret leak checks cover stdout, stderr, memory JSONL, Markdown/JSON reports,
  generated artifacts, staged diffs, and scheduler/run manifests.
- External LLM provider failures are recorded as integration environment
  failures, not hidden as product success.

Phase 3 completion record: implemented by
`docs/goals/phase-reports/2026-05-23-phase-3-real-llm-test-policy-completion-report.md`.

Completed behavior:

- Real LLM integration tests now cover the configured adapter smoke path,
  `plan-experiments`, `research-loop`, and `evidence-report`.
- Real LLM tests are marked as both `integration` and `llm_integration`, run
  locally when credentials are configured, and require
  `CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS=1` in CI/shared automation.
- A reusable secret scanner covers stdout, stderr, memory JSONL, Markdown/JSON
  reports, generated artifacts, run manifests, and staged diffs without
  printing matched secret values.
- A deterministic policy contract keeps fake/injected adversarial coverage for
  invalid JSON, schema violations, live-order/private-key/MEV/premium-RPC/high
  capital, and malicious text.
- Phase 3 did not add live trading, wallet-key access, exchange order routing,
  MEV, premium RPC, speed-edge execution, or real-capital authority.

#### Immediate Phase 4: Evidence Run Infrastructure

Goal: Keep the existing evidence-run path operable after the LLM adapter is
connected, but do not treat formal profit validation as started until Phases
8, 9, 10, 11, and 12 are complete.

Initial strategy family:

- `funding_extremity_price_confirmation`

Infrastructure flow:

1. Pull CCXT OHLCV.
2. Pull CCXT funding history.
3. Run deterministic validation.
4. Run paper simulation.
5. Write memory.
6. Generate daily report with optional LLM summary.
7. Generate weekly report with optional LLM summary.

Required implementation:

- Write a run wrapper or exact runbook command set for daily operation.
- Establish a run manifest that records run id, inputs, network route, source
  health, artifacts, memory path, report path, and completion status.
- Add lock handling so overlapping runs cannot corrupt the SQLite database,
  memory file, report, or paper ledger.
- Add a failed-run marker or local notification hook for nonzero exits.
- Preserve daily artifacts under `var/` and keep them out of git.

Completion standard:

- The daily pipeline can run repeatedly without touching live trading,
  exchange order routing, wallet keys, or real capital.
- Each daily report explains data-source health, signals, deterministic
  validation, paper outcome, blocked reasons, and the next bounded experiment.
- Weekly reports summarize sample progress and degraded-family status.
- Output from this phase is operational smoke evidence only. The formal
  historical bootstrap and 30/60/90-observation validation campaign belong to
  Phase 7 after Phases 8-12.

Phase 4 completion record: implemented by
`docs/goals/phase-reports/2026-05-23-phase-4-evidence-run-infrastructure-completion-report.md`.

Completed behavior:

- `evidence-run` now owns a local lock by default at the database root
  (`<db parent>/locks/evidence-run.lock`) so different report directories still
  serialize against the same SQLite and memory artifacts.
- The command writes a machine-readable JSON payload, run manifest, latest JSON
  and manifest pointers, separate daily and research-loop Markdown reports, and
  a failed-run marker for nonzero exits.
- Run manifests record redacted inputs, run id, network route, source health,
  steps, decision reason codes, artifact paths, artifact existence, memory
  path, report paths, completion status, and safe flags.
- Source health now records `direct`, `proxy`, `blocked`, or `not_applicable`
  network route and redacts URLs, API keys, Dune parameter values, GraphQL
  variable values, and Graph query text from failure paths.
- Artifact path collisions are rejected before the pipeline runs, generated
  run ids are unique for fast retries, and the runbook documents exact cron and
  systemd wrapper shapes without requiring an external daemon.
- Phase 4 did not add live trading, wallet-key access, exchange order routing,
  MEV, premium RPC, speed-edge execution, or real-capital authority.

#### Immediate Phase 5: Data And Strategy Expansion

Goal: Start the expansion path after the real LLM adapter and evidence-run
infrastructure are working. This phase feeds the later Phase 8 and Phase 9
implementation plans.

Status as of 2026-05-23: complete.

Priority order:

1. Open interest.
2. Funding plus OI crowding.
3. Liquidation data if a free or cheap source is reliable.
4. Cross-exchange funding dispersion.
5. DeFi, stablecoin, and TVL regime watchlists.
6. DEX liquidity migration watchlists.

Completion standard:

- Every new data source has source-health reporting.
- Every new strategy has either a deterministic validator or an explicit
  watchlist-only adapter.
- Every validator and watchlist adapter fails closed with stable blocked
  reasons when required data is missing, stale, duplicated, skewed, or outside
  the owner's low-capital constraints.
- Weekly reports can compare strategy families side by side and identify which
  family should continue, stop, redesign, or receive additional data.

Phase 5 completion record: implemented by
`docs/goals/phase-reports/2026-05-23-phase-5-data-strategy-expansion-preparation-completion-report.md`.

Completed behavior:

- Weekly family summaries now include a recommended action of `continue`,
  `stop`, `redesign`, or `add_data` with stable reason codes.
- `expansion-prep-report` ranks source and strategy expansion candidates for
  Phase 8 and Phase 9 without probing providers or broadening the experiment
  planner.
- Source candidates fail closed when source-health records are missing,
  failed, credential-gated, or have no typed records.
- Strategy candidates fail closed when a deterministic validator or
  watchlist-only adapter is not registered.
- Phase 5 did not add live trading, wallet-key access, exchange order routing,
  MEV, premium RPC, speed-edge execution, or real-capital authority.

### Phase 6: Merged Phase 1 Entry Gate

Goal: Fold state hygiene and operator-baseline work into the entry gate for
Immediate Phase 1 instead of treating it as a later standalone feature phase.

Status as of 2026-05-23: merged into the completed Immediate Phase 0 closeout.
The next implementation phase is Immediate Phase 1: Real LLM Adapter.

This phase is not a separate implementation track. It is satisfied by the
Immediate Phase 0 / Phase 1 entry work: clean worktree, local configuration
settled, `.env` ignored, local tool directories decided, accidental draft files
handled, and operator docs aligned before the real LLM adapter is implemented.

Why this matters:

- The first milestone is complete, but the next feature work should not start
  from a dirty or ambiguous local state.
- Local untracked tool directories such as `.agents/` and `.claude/` exist in
  the working tree. They are not product code, but the repository should make a
  deliberate decision about whether to ignore or document them.
- Daily evidence collection will create local SQLite, memory, report, log,
  event, lock, and rollout artifacts. Those must stay out of git.

Deliverables:

- Update `docs/goals/project-completion-state.md` to record the published
  milestone commit and public repository URL.
- Decide whether `.agents/` and `.claude/` are local-only tool directories. If
  they are local-only, add ignore rules or a short operator note.
- Confirm `.env` is ignored, never staged, and contains only local operator
  configuration such as LLM credentials and proxy variables.
- Either delete the accidental `tests/test_llm_configured_client.py` draft
  before Phase 1 starts or explicitly incorporate it into the approved Phase 1
  TDD plan.
- Add a small operator baseline checklist to `docs/runbook.md` covering:
  clean git status before runs, expected ignored artifact paths, and how to
  distinguish local tool files from project deliverables.
- Add a local LLM/proxy configuration note to `docs/runbook.md` that lists
  variable names only and states that keys must remain local.
- Add a documentation contract test if the repo should enforce that generated
  SQLite files, `.env`, reports, logs, and local agent directories are not
  accidentally treated as committed product artifacts.

Completion standard:

- `git status --short` after a normal evidence run shows no accidental tracked
  artifacts.
- The state file records the last completed milestone commit and public URL.
- Operator docs make clear that local agent/tool config is outside the
  product unless explicitly committed.
- `.env` is ignored and not staged.
- `.agents/` and `.claude/` status is deliberate.
- No API key, bearer token, provider URL with embedded credentials, private
  key, seed phrase, database, report, cache, or generated artifact appears in a
  staged diff.
- Full tests, ruff, diff checks, and secret-safety review pass before the
  Immediate Phase 1 adapter work starts.
- Once those entry-gate checks pass, Phase 6 is recorded as merged into Phase 1
  readiness rather than scheduled as a separate future phase.

### Phase 8: Data Depth And Quality Expansion

Goal: Expand the public-data layer from basic OHLCV and funding into the slow
variables most likely to matter for low-capital, non-speed strategies.

Status as of 2026-05-24: complete.

Why this matters:

- Funding-only signals are often noisy. They become more useful when combined
  with open interest, liquidation, basis, volume, volatility, and liquidity
  regime data.
- DeFi and DEX snapshots are currently useful as watchlist inputs, but the
  system needs specific query catalogs and quality checks before they can
  become strategy evidence.
- Public APIs have missing data, inconsistent exchange support, rate limits,
  and symbol-format differences. The research loop needs to make those defects
  visible instead of hiding them.

Data sources to add or deepen:

- Direct public archive sources:
  - Binance Public Data OHLCV and futures archive files remain the first
    reproducible historical source.
  - Binance futures `metrics` archive is a priority historical source because
    it includes open interest, open-interest value, top-trader long/short,
    account long/short, and taker long/short volume ratios.
  - Binance premium index klines are a priority basis/premium source.
- CCXT multi-exchange OHLCV and funding history for Binance, OKX, Bybit, and
  any other exchange whose public API works reliably without trading keys.
- CCXT open interest and open-interest history where supported.
- Funding and open-interest cross-exchange snapshots for crowding detection.
- Direct futures REST sources that require explicit network-route tracking:
  - Binance funding history, current open interest, open-interest history,
    basis, global/top long-short ratios, and taker long-short ratio.
  - Bybit open-interest history.
  - OKX open interest and funding history.
- DexScreener pair and token endpoints for price, volume, and liquidity
  snapshots. These are watchlist inputs unless historical snapshots are stored
  locally over time.
- Optional Coinalyze or similar low-cost data for funding, open interest, and
  liquidation history if free or cheap limits are enough.
- DefiLlama fees, revenue, TVL, stablecoins, and yield pools as slow
  fundamentals.
- Dune query templates for protocol revenue, stablecoin flows, DEX volume,
  pool liquidity, and exchange inflow/outflow style slow signals.
- TheGraph query templates for pool liquidity, volume, reserve changes, and
  protocol-specific fundamentals where subgraphs are reliable.

Deliverables:

- A source coverage matrix in docs showing each provider, fields supported,
  rate-limit assumptions, credential requirements, and whether it is core or
  optional.
- A `source-probe` CLI or equivalent provider qualification workflow that can
  test each source with direct networking and with the local proxy route.
- Proxy-aware source health. The system must record `direct`, `proxy`,
  `blocked`, or `unavailable` as the source-probe network route and distinguish
  `ReachableViaProxy` from general provider success.
- Local proxy support through standard variables:
  `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, lowercase variants, `NO_PROXY`, and
  the project-specific `CRYPTO_ALPHA_AGENT_PROXY`.
- Provider status transitions:
  `Candidate`, `Reachable`, `ReachableViaProxy`, `Parseable`,
  `ResearchUsable`, and `ProductionResearchSource`.
- SQLite persistence for new slow-data record types only when they have a
  typed model and data-quality report.
- Source-health thresholds for missing rate, stale records, duplicate records,
  timestamp skew, and optional-source failure.
- Multi-source symbol normalization rules for `BTC/USDT`, perpetual symbols,
  exchange-specific funding symbols, and DEX chain/token identifiers.
- A query catalog for Dune and TheGraph with named research questions and
  expected output schema.

Completion standard:

- Daily reports can say which data sources were fresh, stale, missing, or
  failed.
- Source qualification evidence records the tested URL family, network route,
  HTTP status, parse status, typed record count, schema version if available,
  and blocked reason when a source fails.
- Strategy validators can require specific data fields and fail closed when
  those fields are unavailable.
- A data source can be marked `ProductionResearchSource` only after the probe
  is reachable, parseable, produces nonzero typed records, writes source
  health, and passes a multi-day canary for the fields used by a validator.
- Optional paid or credentialed data remains optional and redacted from logs,
  reports, scheduler plans, and memory.

Phase 8 completion record: implemented by
`docs/goals/phase-reports/2026-05-24-phase-8-data-depth-quality-expansion-completion-report.md`.

Completed behavior:

- Added multi-source symbol normalization for compact CEX spot symbols,
  perpetual settlement symbols, OKX swap symbols, and DEX chain/token
  identifiers.
- Added typed `open_interest` records, CCXT open-interest-history ingestion,
  CLI support through `--ccxt-feed open-interest-history`, and quality checks
  for non-positive values, gaps, stale rows, duplicate semantic records, and
  timestamp skew.
- Added `source-probe` with target catalog coverage for Binance USD-M, Bybit,
  OKX, DexScreener, DefiLlama, Dune, and The Graph. Probe results persist
  source-health evidence with route, provider status, status transitions, HTTP
  status, parse status, typed record count, URL family, schema version, and
  blocked reason.
- Added `docs/source-coverage-matrix.md` and `docs/source-query-catalog.md` to
  make source promotion and optional query work explicit before Phase 9.
- `ProductionResearchSource` remains a documented canary-gated promotion state;
  one-shot probes can only make a source `ResearchUsable`.
- Phase 8 did not add live trading, wallet-key access, exchange order routing,
  MEV, premium RPC, speed-edge execution, or real-capital authority.

### Phase 9: Strategy Validator Library Expansion

Goal: Add more deterministic strategy-family validators before asking AI to
invent broader experiments.

Why this matters:

- The current strongest executable family is funding extremity plus price
  confirmation.
- DeFi and DEX families are mostly watchlists. They do not yet produce
  execution-realistic paper candidates.
- The system needs several independent low-frequency or medium-frequency
  strategy families before it can discover which one may fit small capital.

Evidence-first rule:

- Do not add a strategy validator just because it is plausible or appears in
  research. Each candidate must first pass a feasibility screen against data
  that Phase 8 has qualified.
- For each candidate, map required fields to existing stored records or
  qualified provider outputs before implementation. Missing fields produce a
  `blocked_by_missing_data` or `blocked_by_unqualified_source` record instead
  of a validator.
- Before adding a validator to the project, run a small historical feasibility
  check or prototype over available data to prove timestamps align, sample size
  is nonzero, costs can be applied, and walk-forward can run or fail closed.
- Candidates that fail the feasibility screen are recorded as rejected or
  blocked with evidence, not implemented.

Candidate strategy families to screen:

- Funding crowding with open-interest confirmation:
  funding is extreme, open interest is expanding, price action confirms or
  rejects crowding, and the validator tests both trend-continuation and
  contrarian exits.
- Funding mean reversion after extreme prints:
  extreme funding is followed by neutralization or price reversal, filtered by
  open-interest change, volatility, and liquidity.
- Cross-exchange funding dispersion:
  exchanges show materially different funding regimes for the same asset, but
  the strategy is evaluated as slow directional or paper-only research unless
  execution complexity is later justified.
- Basis and carry regime watchlist:
  spot/perp or dated-futures style basis widens or compresses, with explicit
  borrow/funding/cost assumptions and no leverage requirement by default.
- Stablecoin and DeFi liquidity regime watchlist:
  stablecoin supply, protocol TVL, fees, revenue, and yields shift enough to
  create a research hypothesis for related assets or sectors.
- DEX liquidity migration watchlist:
  pool liquidity and volume migrate across venues or chains, producing
  watchlist signals instead of direct DEX execution quotes.
- Volatility compression and expansion filter:
  low realized volatility followed by funding, volume, or open-interest change
  creates a testable slow breakout or mean-reversion candidate.

Validator requirements:

- Each strategy family must have a typed `StrategyFamilySpec`.
- Each validator must produce trade count, net return, gross expectancy,
  fee-adjusted expectancy, slippage-adjusted expectancy, max drawdown,
  walk-forward split count, walk-forward pass rate, and blocked reasons.
- Every validator must fail closed on missing data, insufficient trades,
  negative expectancy, excessive drawdown, stale source data, or unsupported
  symbols.
- Watchlist-only families must state that they do not support paper
  simulation and must not be routed to paper outcomes.

Completion standard:

- At least three executable paper-simulated strategy families exist.
- At least three watchlist-only strategy families exist with clear research
  outputs.
- Weekly reports rank families by evidence strength and stop degraded families
  by default.

Phase 9 completion record: implemented by the 2026-05-24 Phase 9 round.

Completed behavior:

- Added `funding_open_interest_crowding` as the third executable
  paper-simulated strategy family. It maps to typed OHLCV, funding-rate, and
  open-interest records; filters funding extremes by open-interest expansion;
  reports expectancy, net return, max drawdown, cost-adjusted metrics,
  walk-forward metrics, and stable blocked reasons; and fails closed on missing
  open interest, stale source data, unsupported symbols, insufficient trades,
  negative expectancy, non-positive returns, and excessive drawdown.
- Tightened the shared funding-plus-price validator path so executable funding
  families can fail closed on unsupported symbols, stale source data, and
  excessive drawdown.
- Added `volatility_compression_expansion_watchlist` as the third
  watchlist-only family. It uses typed market candles to flag
  compression/expansion research candidates and explicitly does not support
  paper simulation.
- Updated the strategy registry to expose at least three executable families:
  `funding_extremity_price_confirmation`,
  `funding_mean_reversion_after_extreme`, and
  `funding_open_interest_crowding`.
- Updated the strategy registry to expose at least three research-only
  watchlists: `defi_yield_regime_watchlist`,
  `dex_liquidity_volume_watchlist`, and
  `volatility_compression_expansion_watchlist`.
- Updated `evidence-run` to ingest CCXT open-interest history only when an
  active registered strategy family requires the `open_interest` record type.
- Updated expansion-preparation reports so
  `funding_open_interest_crowding` and
  `volatility_compression_expansion_watchlist` are registered candidates, while
  cross-exchange dispersion, basis/carry, and broader DeFi fundamentals remain
  blocked by `blocked_by_missing_data` or `blocked_by_unqualified_source`
  until qualified multi-source data, cost assumptions, and canary evidence
  exist.
- Phase 9 did not add live trading, wallet-key access, exchange order routing,
  MEV, premium RPC, speed-edge execution, or real-capital authority.

### Phase 10: Execution Realism And Cost Model

Goal: Make validation and paper simulation conservative enough that a paper
edge is not an artifact of missing fees, bad fills, unrealistic holding costs,
or low-liquidity assumptions.

Why this matters:

- With only a few hundred USD, small fees, minimum order sizes, spread, and
  slippage can erase an apparent edge.
- Funding and basis strategies are sensitive to exact timestamp handling,
  funding interval alignment, exchange fees, and borrow or carry assumptions.
- Paper results must model missed trades, stale signals, and unavailable
  liquidity rather than assuming perfect fills.

Deliverables:

- Exchange-specific fee model for configured public venues, with maker/taker
  assumptions recorded per strategy run.
- Symbol-level minimum notional, quantity precision, and tick-size constraints
  where available from public exchange metadata.
- Slippage model that can use conservative fixed bps first, then volume or
  liquidity-adjusted bps when data supports it.
- Funding timestamp alignment checks so entries and exits do not accidentally
  look ahead.
- Stale-signal model that blocks paper outcomes when the signal would have
  been too old for ordinary manual or scripted execution.
- Missed-fill and partial-fill assumptions for strategies that depend on
  low-liquidity symbols.
- A pessimistic mode for validators and paper simulation, used as the default
  gate before rollout review.

Completion standard:

- Every paper outcome records notional, fees, slippage, gross PnL, net PnL,
  max drawdown, stale-signal status, and failure reason when blocked.
- A candidate that is only profitable before costs is rejected.
- A candidate that cannot trade within `max_notional_usd <= 25` is rejected
  for the current owner profile.

Phase 10 completion record:

- Added an offline execution-realism cost model with explicit
  `cost_model_mode` values. `pessimistic` is the default paper gate and records
  venue, maker/taker fee assumptions, applied fee rates, slippage bps,
  stale-signal status, and fill status for each paper outcome.
- Added symbol-market constraints for public-venue assumptions, including
  minimum notional, minimum quantity, quantity step, and tick size. Paper
  outcomes now block low-capital infeasibility with reasons such as
  `min_notional_exceeds_max_notional` instead of silently treating every capped
  notional as tradable.
- Added stale-signal, missed-fill, and `partial_fill` assumptions to paper
  simulation. `stale_signal` blocks delayed signal-to-entry paths, and
  `missed_fill_assumed` blocks low-volume paths when pessimistic volume
  participation cannot fill the effective notional.
- Added `pre_cost_only_profitable` rejection so trades with positive gross PnL
  but non-positive net PnL after fees and slippage cannot be recorded as closed
  paper outcomes.
- Added funding timestamp alignment checks so malformed or lookahead-prone
  `next_funding_at` values block validation with `funding_alignment_invalid`.
- Paper evidence packages now summarize total notional, gross PnL, fees,
  slippage, stale-signal counts, missed fills, partial fills, and cost model
  modes.
- Phase 10 did not add live trading, wallet-key access, exchange order routing,
  MEV, premium RPC, speed-edge execution, or real-capital authority.

### Phase 11: AI Researcher Upgrade

Goal: Make the AI useful for proposing experiments from accumulated evidence,
without giving it authority to invent unverifiable data or execute trades.

Why this matters:

- The current LLM layer is deliberately constrained. It can propose bounded
  research tasks, but it is not yet a strong autonomous researcher.
- AI becomes more valuable after the system has memory, failed experiments,
  source health, and strategy evidence to reason over.
- The danger is hallucinated data, repeated bad experiments, or unsafe strategy
  suggestions. The AI must remain inside contracts and validators.

Deliverables:

- Evidence retrieval context that summarizes recent validation evidence,
  paper outcomes, source health, stopped families, and blocked parameter sets.
- A stricter experiment proposal schema that requires:
  evidence references, parameter changes, expected edge mechanism,
  disconfirmation tests, stop conditions, required data fields, and selected
  validator.
- A strategy-template proposal mode where AI can suggest a new validator
  design, but implementation still requires deterministic tests and human
  review.
- A duplicate-experiment detector so the AI does not keep retesting rejected
  assumptions or stopped parameter sets.
- A hallucination guard that rejects proposals referencing unavailable data
  fields, unsupported sources, live execution, private RPC, MEV, wallet keys,
  or capital above the owner profile.
- A weekly AI research memo that explains what changed, what failed, what
  should stop, and which experiment is next.

Completion standard:

- AI proposals are accepted only when they cite existing evidence or request a
  supported data collection gap.
- AI cannot create a paper outcome directly. It can only select a registered
  validator or propose a new validator for implementation.
- Unsafe or unverifiable AI output is persisted as rejected memory, not silently
  ignored.

Phase 11 completion record:

- Added an AI research context builder that summarizes recent validation
  evidence, paper evidence with execution-realism fields, source health,
  stopped families, blocked parameter sets, available data fields, evidence
  refs, and registered validators.
- Tightened `plan-experiments` LLM proposal acceptance. Registered experiment
  proposals now require evidence refs, parameter changes, expected edge
  mechanism, disconfirmation tests, stop conditions, required data fields, and
  selected validator. Sparse, uncited, unsupported, duplicate, direct
  paper-outcome, live execution, private RPC, MEV, wallet-key, or over-capital
  proposals are rejected and persisted as rejected memory.
- Added design-only strategy-template proposals. AI can suggest a validator
  design, but the output is tagged as requiring deterministic tests and human
  review before implementation.
- Added canonical duplicate experiment detection for rejected blocked
  parameters and previously accepted proposals.
- Added `ai-research-memo`, a weekly read-only memo that explains what changed,
  what failed, what should stop, and which experiment is next.
- Phase 11 did not add live trading, wallet-key access, exchange order routing,
  MEV, private RPC, premium RPC, speed-edge execution, real-capital authority,
  or any ability for AI to create paper outcomes directly.

### Phase 12: Profit Evidence Review And Portfolio Governance - Complete

Goal: Turn accumulated evidence into explicit profit/no-profit decisions.

Why this matters:

- The primary objective is making money, but the system should not pretend a
  strategy is profitable just because it generated signals.
- A low-capital strategy must be judged by realistic expected USD return,
  drawdown, operational burden, failure rate, and robustness across regimes.
- The system needs a formal way to stop weak families and focus compute and
  attention on the most promising ones.

Deliverables:

- A weekly family scoreboard with:
  sample size, net PnL, cost-adjusted expectancy, max drawdown, hit rate,
  failure rate, source-health quality, stale-signal rate, and walk-forward
  stability.
- A profit review artifact that answers:
  whether the strategy is improving, whether it is worth more data collection,
  whether it should be stopped, and whether it is near an owner decision point.
- A stopped-family ledger with reason, date, evidence refs, and conditions
  required for revival.
- A paper-only portfolio selector that ranks families for future paper
  observations without allocating real capital.
- A monthly owner review report that compares the best paper strategy against
  doing nothing, fees, opportunity cost, and the owner's capital constraints.

Delivered:

- Added deterministic `governance-report` CLI output with
  `uses_real_capital=false` and `live_order_routing=false`.
- Added a weekly family scoreboard with sample size, net PnL,
  cost-adjusted expectancy, max drawdown, hit rate, failure rate,
  source-health quality, stale-signal rate, walk-forward stability, action,
  and evidence reason codes.
- Added a profit review artifact that states whether each family is improving,
  worth more data, should stop, or is near an owner decision review.
- Added a memory-derived stopped-family ledger with stopped date, reason
  codes, evidence refs, and revival conditions.
- Added a paper-only portfolio selector that ranks future paper observations
  without allocating real capital.
- Added a monthly owner review comparison against doing nothing, fees,
  slippage, opportunity cost, and the owner's capital constraint.

Completion standard:

- The governance layer can state for each active family:
  keep collecting, stop, redesign validator, add data, or escalate to an owner
  decision review.
- No strategy advances because of narrative alone. It advances only because
  paper evidence and validation evidence meet explicit gates.

### Phase 7: Final Evidence Campaign After Factory Buildout

Goal: After Phases 8, 9, 10, 11, and 12 are complete, use historical data to
bootstrap strategy evidence and then keep running `evidence-run` as new market
data arrives to build out-of-sample paper observations and failure evidence.

Why this matters:

- The system can simulate and record evidence, but evidence is meaningful only
  after source qualification, strategy validators, cost models, AI research
  guards, and governance scoreboards are in place.
- Historical data should be used first to reject weak ideas, tune validator
  requirements, and define what future out-of-sample evidence should confirm.
- Future daily samples are still needed because a historical result is not a
  money edge by itself. It may be overfit, stale, fee-sensitive, or dependent
  on a past market regime.
- The owner's capital is small, so the edge must remain positive after small
  notional limits, fees, slippage, stale signals, missed fills, and ordinary
  infrastructure.

Prerequisites before Phase 7 starts:

- Phase 8 source qualification is complete for every data field required by
  the target strategy families.
- Phase 9 has enough executable and watchlist-only strategy families to compare
  alternatives instead of overfitting one idea.
- Phase 10 cost and execution realism is active by default.
- Phase 11 AI researcher can propose bounded experiments from evidence without
  bypassing validators.
- Phase 12 governance can classify families as keep collecting, stop,
  redesign, add data, or near owner decision review.

Deliverables:

- Phase 7A historical bootstrap:
  - Pull reproducible Binance Public Data candle history for selected symbols
    and timeframes.
  - Pull or ingest funding history, open interest, basis, long/short, and other
    required fields through qualified public sources.
  - Run deterministic validation for every active executable strategy family
    over historical stored data.
  - Run `paper-sim-loop` over historical windows and record blocked or closed
    paper outcomes.
  - Generate a historical evidence report that states whether each family is
    usable, blocked, negative after costs, or worth future out-of-sample
    observation.
- Phase 7B ongoing collection:
  - Continue daily `evidence-run` as new data arrives.
  - Compare new outcomes against the historical bootstrap expectation.
  - Treat future observations as out-of-sample checks, not as a replacement for
    historical validation.
- Add or finalize an operator-controlled daily run wrapper or documented
  command set for offline store checks, `evidence-run`, weekly
  `evidence-report`, and artifact retention.
- Add or finalize run manifests that record run id, command arguments, source
  health, records written, report paths, memory path, network route, and
  completed/failed status.
- Add failure notification guidance for local operation, for example writing a
  failed-run marker file or using a local shell mail/notification hook outside
  the Python package.

Evidence targets:

- Historical bootstrap over multiple past windows before relying on future
  daily samples.
- At least 30 paper observations for one narrow strategy family before any
  rollout review can be considered meaningful.
- At least 60 paper observations before treating a paper edge as more than a
  preliminary signal.
- At least 90 calendar days of daily reports before making a profit/no-profit
  decision on the first strategy family.

Completion standard:

- The historical bootstrap run records exact sources, symbols, dates,
  parameters, validation metrics, paper outcomes, blocked reasons, costs, and
  network route.
- Weekly reports show sample-size progress, failed reasons, source-health
  reliability, and whether evidence is improving or degrading.
- The governance layer can classify every active family using the accumulated
  historical and out-of-sample evidence.
- No live capital, wallet keys, order routing, or exchange trade permissions
  are introduced.
- Phase 7 is not considered profit proof until future out-of-sample samples
  confirm or reject what the historical bootstrap suggested.

### Phase 13: Continuous Research Review And Reporting

Goal: Continuously inspect the generated research reports, evidence packages,
AI memos, strategy scoreboards, and finished artifacts, then write review
reports that judge whether the system is producing useful money-making
research or just generating activity.

Why this matters:

- The primary objective is making money, not building a complex agent for its
  own sake.
- Even after Phases 8-12 and the Phase 7 evidence campaign, the owner still
  needs a disciplined review loop that asks whether the outputs are improving,
  whether research is becoming more focused, and whether weak families are
  being stopped quickly enough.
- The system should produce review reports plus explicit decision records, not
  just raw output. A report that does not change what to test, stop,
  redesign, or collect next is not useful.
- Live execution remains blocked by the charter. Phase 13 is about evaluating
  research effectiveness and finished artifacts, not implementing trading or
  adding new product code.

Review inputs:

- Daily and weekly evidence reports.
- Historical bootstrap reports and out-of-sample paper observations.
- Strategy-family scoreboards and stopped-family ledgers.
- AI research memos, rejected proposal memory, and duplicate experiment
  records.
- Source-health reports and data-quality reports.
- Cost-model and execution-realism summaries.
- Owner decision artifacts from Phase 12.

Review cadence:

- Daily quick scan:
  whether new evidence arrived, whether sources failed, whether any strategy
  degraded, and whether the next experiment is still valid.
- Weekly review:
  compare strategy families, inspect stopped ideas, check whether AI proposals
  are becoming better or repetitive, and decide what to run next week.
- Monthly review:
  decide whether the project is moving toward profit evidence, needs a major
  redesign, should drop a strategy family, should add a data source, or should
  pause a line of research.

Outputs:

- A short review report for each cadence.
- A decision log entry for each active family or major report cycle.
- A list of follow-up questions, gaps, or blocked items for the next phase.

Required decisions:

- `keep_collecting`: evidence is improving but sample size is not enough.
- `stop_family`: evidence is negative, degraded, too costly, or too fragile.
- `redesign_validator`: the idea may be valid but the current validator is too
  weak, too optimistic, or missing fields.
- `add_data`: the blocker is data coverage or data quality.
- `retire_data_source`: the source is stale, unreliable, expensive, or not
  useful for decisions.
- `pause_project_line`: the research area is consuming effort without evidence
  that it can fit the owner's low-capital constraints.

Completion standard:

- No new product code is added in this phase; the output is review reports and
  decision records only.
- Every weekly and monthly review produces an explicit decision record.
- Each active strategy family has a current owner-facing status:
  keep collecting, stop, redesign, add data, or pause.
- The review can explain whether the project is closer to finding a
  cost-adjusted edge than it was in the previous period.
- Reported improvements are tied to metrics and evidence references, not AI
  narrative alone.
- The current code continues to report `live_execution_allowed=false`.

The constraints remain unchanged: low capital measured in a few hundred USD,
ordinary public APIs/RPC only, no speed edge or speed arbitrage, no MEV or
premium infrastructure dependency, no wallet-key access, no order routing, and
no live capital.

## Codex Goal Continuation

The long-running project completion loop is now defined in
`docs/goals/project-completion-goal.md`, with rolling state in
`docs/goals/project-completion-state.md`.

Use that Goal contract after each completed slice to:

- audit the current code, tests, docs, and plans against the final project
  definition of done;
- select the next smallest coherent gap;
- use subagents where work can be safely split or independently reviewed;
- finish the selected slice with tests, docs, verification, commit, and GitHub
  push;
- update `docs/goals/project-completion-state.md` and this roadmap before
  continuing.

The Goal loop does not weaken the charter. It must continue to reject live
execution, wallet-key access, exchange order routing, MEV, premium-RPC
dependency, speed-edge strategies, and secrets in git.

## Roadmap Update Rule

After each completed phase or major implementation branch, update this roadmap
with:

- What changed.
- What evidence exists.
- What remains blocked.
- The next smallest useful implementation slice.
