# Evidence Recovery Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the active-family validation-to-paper evidence path, or document a concrete source/data/validation blocker, without live execution or stopped-family override.

**Architecture:** Start with source qualification and local evidence inspection over the existing CLI and SQLite store. Run the current `funding_open_interest_crowding` path first because it is active, public-data-only, and already wired to require open-interest ingestion; use `funding_mean_reversion_after_extreme` only as the fallback active family. Make product-code changes only if a command proves a repository defect, and close the round with state, roadmap, and phase-report documentation.

**Tech Stack:** Python 3.12, `uv`, existing `crypto-alpha-agent` CLI, SQLite, JSON/JQ inspection, existing source-health/validation/paper ledgers, pytest, ruff, staged secret scan.

---

## Source Evidence And Design Inputs

- Design spec:
  `docs/superpowers/specs/2026-06-08-evidence-recovery-campaign-design.md`.
- Smart Search evidence directory:
  `var/smart-search-evidence/2026-06-08-completion-roadmap/`.
- Fetched external evidence:
  - Binance USD-M funding history:
    `var/smart-search-evidence/2026-06-08-completion-roadmap/02-binance-funding.md`.
  - Binance USD-M open interest:
    `var/smart-search-evidence/2026-06-08-completion-roadmap/03-binance-open-interest.md`.
  - DexScreener API:
    `var/smart-search-evidence/2026-06-08-completion-roadmap/05-dexscreener-api.md`.
  - CCXT docs fetch:
    `var/smart-search-evidence/2026-06-08-completion-roadmap/04-ccxt-docs.md`
    is empty because fetch failed, so CCXT OI support must be proven by local
    probe/ingest output.

## Local Feasibility Baseline

Current inspected facts before this plan:

- `git status --short --branch` showed `main...origin/main [ahead 1]` after
  the design-spec commit.
- `var/research.sqlite` tables include `source_records`,
  `validation_evidence`, and `paper_outcomes`.
- Existing record counts:
  - `defi_yield|defillama|15940`
  - `dex_pair|dexscreener|30`
  - `funding_rate|ccxt|229`
  - `market_candle|ccxt|422`
  - `source_health` rows for several sources
  - no `open_interest` records.
- Existing validation/paper evidence belongs only to
  `funding_extremity_price_confirmation`, which is stopped.
- Current supported CLI surfaces were confirmed with:
  - `uv run --extra dev crypto-alpha-agent source-probe --help`
  - `uv run --extra dev crypto-alpha-agent ingest --help`
  - `uv run --extra dev crypto-alpha-agent evidence-run --help`
  - `uv run --extra dev crypto-alpha-agent governance-report --help`

## Execution Constraints

- Do not run `--allow-stopped-family` in this campaign.
- Do not include `funding_extremity_price_confirmation` in active evidence
  runs.
- Keep `.env`, databases, memory, reports, manifests, logs, and `var/`
  artifacts out of git.
- Use the local operator proxy only as configuration for public data access.
  Do not print or commit proxy values.
- Preserve `uses_real_capital=false` and `live_order_routing=false`.
- The Goal contract asks for subagent use each round, but the available
  subagent tool is restricted to cases where the user explicitly asks for
  subagents. Unless the owner explicitly authorizes subagents, document that
  constraint in the phase report and perform the required review locally.

## File Structure

Committed documentation expected if the campaign reaches a closeout point:

- Create: `docs/superpowers/plans/2026-06-08-evidence-recovery-campaign.md`
- Modify: `docs/goals/project-completion-state.md`
- Modify: `docs/roadmap.md` only if the roadmap changes.
- Create:
  `docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md`

Ignored runtime artifacts expected under `var/`:

- `var/reports/evidence-recovery/`
- `var/run-manifests/evidence-recovery/`
- `var/reports/governance/evidence-recovery-*.md` if the directory exists or
  is created.

Product-code files are not expected to change. If a real defect blocks the
campaign, stop implementation in this plan, document the blocker with command
evidence, and write a separate TDD plan for the specific defect before editing
code.

## Task 1: Baseline Snapshot And Safety Check

**Files:**
- Read: `docs/goals/project-completion-state.md`
- Read: `docs/roadmap.md`
- Read: `docs/runbook.md`
- Read: `docs/rollout-gates.md`
- Read: `docs/tiny-live-readiness.md`
- Read: `var/reports/daily/2026-06-07-proxy-fixed.evidence-run.json`
- Read: `var/run-manifests/evidence-run/proxy-fixed-20260607T142806Z.json`

- [ ] **Step 1: Confirm current git state**

Run:

```bash
git status --short --branch
```

Expected: only committed design/plan work is ahead of `origin/main`, and there
are no untracked runtime artifacts staged.

- [ ] **Step 2: Confirm current active-family evidence gap**

Run:

```bash
sqlite3 var/research.sqlite \
  "select strategy_family, count(*) from validation_evidence group by strategy_family order by strategy_family;
   select strategy_family, count(*) from paper_outcomes group by strategy_family order by strategy_family;
   select record_type, source, count(*) from source_records group by record_type, source order by record_type, source;"
```

Expected:

- validation/paper evidence exists only for
  `funding_extremity_price_confirmation`;
- no `open_interest` records exist before Task 2;
- source records show existing CCXT funding and OHLCV history.

- [ ] **Step 3: Confirm latest successful public-data run did not create new evidence**

Run:

```bash
jq '{
  run_id,
  status,
  network_route,
  stopped_family_override_used,
  steps,
  report_summary: {
    validation_evidence_written: .report.validation_evidence_written,
    paper_outcomes_written: .report.paper_outcomes_written,
    decision_reason_codes: .report.decision_reason_codes,
    skipped_strategy_families: .report.skipped_strategy_families,
    llm_decision: .report.llm_interpretation.decision,
    next_actions: .report.llm_interpretation.next_actions
  }
}' var/reports/daily/2026-06-07-proxy-fixed.evidence-run.json
```

Expected:

- `status` is `success`;
- `network_route` is `proxy`;
- `validation_evidence_written` is `0`;
- `paper_outcomes_written` is `0`;
- `skipped_strategy_families` contains
  `funding_extremity_price_confirmation`;
- no stopped-family override was used.

## Task 2: Open-Interest Source Qualification

**Files:**
- Runtime write: `var/research.sqlite`
- Runtime write: source-health rows inside `source_records`
- Runtime write: possible `open_interest` rows inside `source_records`

- [ ] **Step 1: List source-probe targets**

Run:

```bash
uv run --extra dev crypto-alpha-agent source-probe --list-targets
```

Expected: output includes `binance_usdm_open_interest_history`.

- [ ] **Step 2: Record no-network probe evidence**

Run:

```bash
uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_open_interest_history
```

Expected:

- command exits 0;
- records a blocked/no-network source-health row;
- output keeps `uses_real_capital=false` and `live_order_routing=false`.

- [ ] **Step 3: Probe the proxy route without exposing proxy values**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; \
uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_open_interest_history \
  --allow-network \
  --route proxy'
```

Expected:

- command exits 0 if Binance open-interest history is reachable through the
  local proxy;
- output and stored source-health do not print proxy values;
- failure is acceptable only if it records a stable source-health failure code
  that can be cited in the phase report.

- [ ] **Step 4: Ingest a small CCXT open-interest-history sample**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; \
uv run --extra dev crypto-alpha-agent ingest \
  --source ccxt \
  --allow-network \
  --ccxt-feed open-interest-history \
  --exchange binance \
  --symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 24 \
  --db var/research.sqlite \
  --current-capital-usd 300'
```

Expected:

- if CCXT supports the configured symbol/feed, the command writes positive
  `open_interest` records;
- if the exchange method or symbol shape is unsupported, the command fails or
  records source-health failure without leaking proxy values;
- do not edit product code in this step.

- [ ] **Step 5: Inspect stored open-interest rows**

Run:

```bash
sqlite3 var/research.sqlite \
  "select
     json_extract(payload_json, '$.symbol') as symbol,
     json_extract(payload_json, '$.venue') as venue,
     count(*) as rows,
     min(observed_at) as first_observed_at,
     max(observed_at) as last_observed_at,
     min(cast(json_extract(payload_json, '$.open_interest') as real)) as min_open_interest,
     max(cast(json_extract(payload_json, '$.open_interest') as real)) as max_open_interest
   from source_records
   where record_type='open_interest'
   group by symbol, venue
   order by symbol, venue;"
```

Expected:

- at least one row group for `BTC/USDT:USDT` if ingestion succeeded;
- `min_open_interest` is greater than 0;
- if no rows exist, Task 3 should not treat OI as qualified evidence.

## Task 3: Active-Family Evidence Run For OI Crowding

**Files:**
- Runtime write: `var/research.sqlite`
- Runtime write: `var/memory/evidence.jsonl`
- Runtime write: `var/reports/evidence-recovery/`
- Runtime write: `var/run-manifests/evidence-recovery/`

- [ ] **Step 1: Run evidence recovery for `funding_open_interest_crowding`**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; \
RUN_ID="evidence-recovery-oi-$(date -u +%Y%m%dT%H%M%SZ)"; \
mkdir -p var/reports/evidence-recovery var/run-manifests/evidence-recovery var/run-manifests/failed/evidence-recovery; \
uv run --extra dev crypto-alpha-agent evidence-run \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --report-out "var/reports/evidence-recovery/${RUN_ID}.md" \
  --research-report-out "var/reports/evidence-recovery/${RUN_ID}.research.md" \
  --weekly-report-out "var/reports/evidence-recovery/${RUN_ID}.weekly.md" \
  --json-out "var/reports/evidence-recovery/${RUN_ID}.json" \
  --manifest-out "var/run-manifests/evidence-recovery/${RUN_ID}.manifest.json" \
  --failed-marker-out "var/run-manifests/failed/evidence-recovery/${RUN_ID}.json" \
  --latest-report-out var/reports/evidence-recovery/latest.md \
  --latest-json-out var/reports/evidence-recovery/latest.json \
  --latest-manifest-out var/run-manifests/evidence-recovery/latest.json \
  --allow-network \
  --ccxt-exchange binance \
  --symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 200 \
  --strategy-family funding_open_interest_crowding \
  --run-id "${RUN_ID}"'
```

Expected:

- command either exits 0 with an evidence-run payload or writes a failed marker
  with a stable failure reason;
- it must not use `--allow-stopped-family`;
- it must not include `funding_extremity_price_confirmation`;
- if OI is qualified, steps include `ingest_ccxt_open_interest`;
- `uses_real_capital=false` and `live_order_routing=false`.

- [ ] **Step 2: Inspect the latest recovery payload**

Run:

```bash
jq '{
  run_id,
  status,
  network_route,
  stopped_family_override_used,
  uses_real_capital,
  live_order_routing,
  steps,
  report_summary: {
    strategy_families: .report.strategy_families,
    skipped_strategy_families: .report.skipped_strategy_families,
    validation_evidence_written: .report.validation_evidence_written,
    paper_outcomes_written: .report.paper_outcomes_written,
    decision_reason_codes: .report.decision_reason_codes,
    source_health_failures: .report.source_health.failures,
    llm_decision: .report.llm_interpretation.decision,
    next_actions: .report.llm_interpretation.next_actions
  }
}' var/reports/evidence-recovery/latest.json
```

Expected:

- `strategy_families` contains `funding_open_interest_crowding`;
- `skipped_strategy_families` is empty;
- if validation is blocked, reason codes are stable and citeable;
- if validation writes evidence, `validation_evidence_written` is greater than
  0;
- if paper simulation runs, `paper_outcomes_written` may be greater than 0.

- [ ] **Step 3: Inspect validation and paper ledgers for the new run**

Run:

```bash
RUN_ID="$(jq -r '.run_id' var/reports/evidence-recovery/latest.json)"
sqlite3 var/research.sqlite \
  "select strategy_family, approved, blocked_reasons_json, count(*)
   from validation_evidence
   where run_id like '${RUN_ID}%'
   group by strategy_family, approved, blocked_reasons_json
   order by strategy_family, approved, blocked_reasons_json;
   select strategy_family, status, count(*)
   from paper_outcomes
   where run_id like '${RUN_ID}%'
   group by strategy_family, status
   order by strategy_family, status;"
```

Expected:

- ledger rows agree with the payload summary;
- if no rows exist, the phase report must record this as an implementation or
  runtime blocker and cite the payload/manifest.

## Task 4: Fallback Active-Family Run For Mean Reversion

**Files:**
- Runtime write: `var/research.sqlite`
- Runtime write: `var/memory/evidence.jsonl`
- Runtime write: `var/reports/evidence-recovery/`
- Runtime write: `var/run-manifests/evidence-recovery/`

- [ ] **Step 1: Decide whether fallback is needed**

Use Task 3 evidence:

- If `funding_open_interest_crowding` writes validation evidence and any paper
  outcome or stable paper blocker, skip Task 4 and continue to Task 5.
- If `funding_open_interest_crowding` is blocked by OI source support, missing
  OI records, stale OI, no OI expansion, or LLM/runtime failure, run Task 4.

- [ ] **Step 2: Run evidence recovery for `funding_mean_reversion_after_extreme`**

Run:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; \
RUN_ID="evidence-recovery-mean-reversion-$(date -u +%Y%m%dT%H%M%SZ)"; \
mkdir -p var/reports/evidence-recovery var/run-manifests/evidence-recovery var/run-manifests/failed/evidence-recovery; \
uv run --extra dev crypto-alpha-agent evidence-run \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --report-out "var/reports/evidence-recovery/${RUN_ID}.md" \
  --research-report-out "var/reports/evidence-recovery/${RUN_ID}.research.md" \
  --weekly-report-out "var/reports/evidence-recovery/${RUN_ID}.weekly.md" \
  --json-out "var/reports/evidence-recovery/${RUN_ID}.json" \
  --manifest-out "var/run-manifests/evidence-recovery/${RUN_ID}.manifest.json" \
  --failed-marker-out "var/run-manifests/failed/evidence-recovery/${RUN_ID}.json" \
  --latest-report-out var/reports/evidence-recovery/latest.md \
  --latest-json-out var/reports/evidence-recovery/latest.json \
  --latest-manifest-out var/run-manifests/evidence-recovery/latest.json \
  --allow-network \
  --ccxt-exchange binance \
  --symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 200 \
  --strategy-family funding_mean_reversion_after_extreme \
  --run-id "${RUN_ID}"'
```

Expected:

- command either exits 0 with active-family evidence or writes a failed marker;
- no stopped-family override is used;
- validation and paper ledgers agree with the payload.

- [ ] **Step 3: Inspect fallback evidence**

Run:

```bash
jq '{
  run_id,
  status,
  network_route,
  stopped_family_override_used,
  uses_real_capital,
  live_order_routing,
  report_summary: {
    strategy_families: .report.strategy_families,
    validation_evidence_written: .report.validation_evidence_written,
    paper_outcomes_written: .report.paper_outcomes_written,
    decision_reason_codes: .report.decision_reason_codes,
    llm_decision: .report.llm_interpretation.decision,
    next_actions: .report.llm_interpretation.next_actions
  }
}' var/reports/evidence-recovery/latest.json
```

Expected:

- the summary is sufficient to decide `continue`, `add_data`,
  `redesign_validator`, or `stop`;
- if no validation evidence is written, record a blocker rather than repeating
  no-op runs.

## Task 5: Product-Code Defect Gate

**Files:**
- No product-code edits in this plan.
- If a defect is proven, document it in
  `docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md`
  and create a follow-up TDD plan before code changes.

- [ ] **Step 1: Decide whether a product-code blocker exists**

A product-code blocker exists only if a command proves a repository defect such
as:

- CLI cannot run a documented active-family path;
- evidence-run does not trigger OI ingestion for a family that declares
  `open_interest`;
- ledger rows contradict payload summaries;
- source-health route or failure redaction is incorrect;
- a supported record is stored under the wrong type or symbol.

If all failures are provider unreachability, missing data, no OI expansion, no
qualified trades, stopped-family memory, or insufficient sample size, skip code
changes and proceed to documentation closeout.

- [ ] **Step 2: If a product-code blocker exists, stop this plan's execution**

Write the blocker into the campaign report with:

- exact command;
- exit code;
- redacted failure text;
- affected file or module if identifiable;
- why the failure is a product defect rather than missing provider data;
- proposed TDD test target for the next plan.

Expected: no product-code file is edited under this plan.

- [ ] **Step 3: If no product-code blocker exists, continue to governance**

Expected: the campaign produces either usable evidence or a data/source/strategy
blocker that can be represented in docs without code changes.

## Task 6: Governance And Readiness Reconciliation

**Files:**
- Runtime write: `var/reports/evidence-recovery/governance-latest.md`

- [ ] **Step 1: Build governance report after recovery run**

Run:

```bash
mkdir -p var/reports/evidence-recovery
uv run --extra dev crypto-alpha-agent governance-report \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/evidence-recovery/governance-latest.md \
  --current-capital-usd 300
```

Expected:

- command exits 0 if the real LLM runtime is healthy;
- report keeps `Real capital: false` and `Live order routing: false`;
- active families classify as `add_data`, `redesign_validator`, `stop`, or a
  stronger action based only on evidence;
- `owner_decision_review` is not expected unless paper and walk-forward
  thresholds are actually met.

- [ ] **Step 2: Inspect governance report**

Run:

```bash
sed -n '1,260p' var/reports/evidence-recovery/governance-latest.md
```

Expected:

- the `Weekly Family Scoreboard`, `Profit Review`, `Stopped-Family Ledger`,
  and `Paper-Only Portfolio Selector` are internally consistent with Task 3
  and Task 4 outcomes.

## Task 7: State, Roadmap, And Campaign Report

**Files:**
- Modify: `docs/goals/project-completion-state.md`
- Modify: `docs/roadmap.md` only if campaign status changes the public roadmap.
- Create:
  `docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md`

- [ ] **Step 1: Update completion state**

Edit `docs/goals/project-completion-state.md` to record:

- campaign name and date;
- design spec and plan paths;
- Smart Search evidence path;
- exact source-probe and evidence-run commands executed;
- whether OI records were written;
- active family tested;
- validation evidence count;
- paper outcome count;
- governance action;
- current gap to 30/60/90 evidence targets;
- whether the next action is continue collecting, add data, redesign, stop, or
  owner review;
- no live execution and no stopped-family override.

- [ ] **Step 2: Update roadmap if needed**

If the campaign creates a new material roadmap state, edit `docs/roadmap.md`
under the Active Next Step or post-milestone evidence section.

Expected:

- if the run only documents a blocker, roadmap should say the next practical
  work is the named blocker;
- if evidence was produced, roadmap should say the next practical work is
  accumulating out-of-sample observations for the named active family.

- [ ] **Step 3: Write campaign report**

Create
`docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md`
with these sections:

- Phase name, date, commit or pending commit reference, owner objective, and
  whether this was operations-only or included code changes.
- Smart Search query, evidence paths, fetched sources, and external findings.
- Local feasibility findings and files inspected.
- Substep validation results for source-probe, OI ingest, evidence-run,
  fallback run if used, governance report, and any rejected candidates.
- Files changed and runtime artifacts produced.
- Subagent constraint: record that the Goal contract requested subagent use but
  the available subagent tool was restricted because the user did not explicitly
  ask for subagents.
- Review passes, Critical or Important findings, fixes, and re-review status.
- Verification commands and exact pass/fail results.
- Secret-safety result and confirmation that `.env`, keys, databases, memory,
  reports, caches, and `var/` artifacts were not staged.

## Task 8: Review, Verification, Commit, And Push

**Files:**
- Review every changed tracked file.

- [ ] **Step 1: Requirements review**

Review the design spec and this plan against the current diff.

Expected:

- every success criterion in the spec is either satisfied by evidence or
  documented as a blocker;
- no stopped-family override was used;
- no live execution path was introduced.

- [ ] **Step 2: Safety and quality review**

Run:

```bash
git status --short
git diff -- docs/goals/project-completion-state.md docs/roadmap.md docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md
```

Expected:

- no `var/` files staged or intended for commit;
- no secrets or local proxy values in tracked docs;
- runtime evidence is referenced by path and summarized, not copied wholesale.

- [ ] **Step 3: Final verification**

Run:

```bash
uv run --extra dev ruff check .
git diff --check
git status --short --branch
```

Expected:

- ruff and diff checks pass;
- status contains only intended tracked docs before staging.

- [ ] **Step 4: Stage intended docs only**

Run:

```bash
git add \
  docs/superpowers/plans/2026-06-08-evidence-recovery-campaign.md \
  docs/goals/project-completion-state.md \
  docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md
```

If `docs/roadmap.md` was deliberately updated, add it explicitly:

```bash
git add docs/roadmap.md
```

Expected: no `var/`, `.env`, database, memory, cache, or log file is staged.

- [ ] **Step 5: Staged review and secret scan**

Run:

```bash
git diff --cached --name-only
git diff --cached --check
git diff --cached --no-ext-diff --unified=0
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

Expected:

- staged file list contains only intended docs;
- secret scan returns no findings.

- [ ] **Step 6: Commit and push**

Run:

```bash
git commit -m "docs: record evidence recovery campaign"
git push
```

Expected:

- commit succeeds;
- push updates `origin/main`;
- `git status --short --branch` shows `main...origin/main` with no local
  changes after the push.
