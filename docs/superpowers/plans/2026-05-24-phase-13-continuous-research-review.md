# Phase 13 Continuous Research Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 13 with read-only review reports and explicit decision records, without adding product code or live execution.

**Architecture:** Treat existing generated reports as inputs and add committed Markdown review artifacts only. The plan uses the roadmap's Phase 13 cadence, local generated report evidence under ignored `var/`, and state/roadmap synchronization to close the final charter-compliant gap.

**Tech Stack:** Markdown documentation, existing Python CLI verification through `uv`, existing pytest/ruff/secret-scan tooling.

---

## File Structure

- Create: `docs/superpowers/specs/2026-05-24-phase-13-continuous-research-review-design.md`
- Create: `docs/goals/research-reviews/2026-05-24-daily-quick-scan.md`
- Create: `docs/goals/research-reviews/2026-05-24-weekly-effectiveness-review.md`
- Create: `docs/goals/research-reviews/2026-05-24-monthly-owner-review.md`
- Create: `docs/goals/decision-records/2026-05-24-phase-13-decision-log.md`
- Create: `docs/goals/phase-reports/2026-05-24-phase-13-continuous-research-review-completion-report.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`

Ignored local evidence generated during planning:

- `var/reports/phase13/daily-empty-ledger.md`
- `var/reports/phase13/weekly-empty-ledger.md`
- `var/reports/phase13/governance-empty-ledger.md`
- `var/reports/phase13/ai-research-memo-empty-ledger.md`
- `var/reports/phase13/historical-bootstrap-empty-ledger.md`
- `var/reports/phase13/historical-bootstrap-empty-ledger.json`
- `var/run-manifests/phase13/historical-bootstrap-empty-ledger.manifest.json`
- `var/phase13/research.sqlite`

Do not stage any `var/` artifact.

### Task 1: Record Design And Local Evidence

**Files:**
- Create: `docs/superpowers/specs/2026-05-24-phase-13-continuous-research-review-design.md`
- Create: `docs/superpowers/plans/2026-05-24-phase-13-continuous-research-review.md`

- [x] **Step 1: Verify baseline**

Run:

```bash
uv run --extra dev pytest -q
```

Expected: `912 passed, 4 skipped`.

- [x] **Step 2: Generate ignored local report evidence**

Run:

```bash
uv run --extra dev crypto-alpha-agent governance-report --db var/phase13/research.sqlite --memory var/phase13/memory.jsonl --out var/reports/phase13/governance-empty-ledger.md --current-capital-usd 300
uv run --extra dev crypto-alpha-agent historical-bootstrap --db var/phase13/research.sqlite --memory var/phase13/memory.jsonl --out var/reports/phase13/historical-bootstrap-empty-ledger.md --json-out var/reports/phase13/historical-bootstrap-empty-ledger.json --manifest-out var/run-manifests/phase13/historical-bootstrap-empty-ledger.manifest.json --run-id phase13-review-empty-ledger --price-symbol BTC/USDT --funding-symbol BTC/USDT:USDT --timeframe 1h --bootstrap-window 2026-03-01/2026-04-01 --current-capital-usd 300
uv run --extra dev crypto-alpha-agent evidence-report --daily --db var/phase13/research.sqlite --memory var/phase13/memory.jsonl --out var/reports/phase13/daily-empty-ledger.md --offline-only --strategy-family funding_extremity_price_confirmation --strategy-family funding_mean_reversion_after_extreme --strategy-family funding_open_interest_crowding
uv run --extra dev crypto-alpha-agent evidence-report --weekly --db var/phase13/research.sqlite --memory var/phase13/memory.jsonl --out var/reports/phase13/weekly-empty-ledger.md --offline-only
uv run --extra dev crypto-alpha-agent ai-research-memo --db var/phase13/research.sqlite --memory var/phase13/memory.jsonl --out var/reports/phase13/ai-research-memo-empty-ledger.md --current-capital-usd 300
```

Expected:

- all commands exit 0;
- outputs show `uses_real_capital=false`;
- outputs show `live_order_routing=false`;
- governance and bootstrap classify registered families as `add_data`;
- artifacts remain ignored under `var/`.

- [x] **Step 3: Write design and plan**

Record Smart Search evidence, local feasibility, chosen docs-only approach,
decision vocabulary, and safety boundaries in the spec and this plan.

### Task 2: Write Cadence Review Reports

**Files:**
- Create: `docs/goals/research-reviews/2026-05-24-daily-quick-scan.md`
- Create: `docs/goals/research-reviews/2026-05-24-weekly-effectiveness-review.md`
- Create: `docs/goals/research-reviews/2026-05-24-monthly-owner-review.md`

- [x] **Step 1: Daily quick scan**

Write a short report with:

- new evidence arrival;
- source failure status;
- degraded-family status;
- next experiment validity;
- safety flags.

Expected decision: `add_data` for current empty local ledgers and no stop
based on current evidence.

- [x] **Step 2: Weekly effectiveness review**

Write a family-by-family report for these registered families:

- `defi_yield_regime_watchlist`
- `dex_liquidity_volume_watchlist`
- `funding_extremity_price_confirmation`
- `funding_mean_reversion_after_extreme`
- `funding_open_interest_crowding`
- `volatility_compression_expansion_watchlist`

Expected decision: each family receives owner-facing status `add_data`.

- [x] **Step 3: Monthly owner review**

Write the monthly review that answers whether the project is closer to a
cost-adjusted edge.

Expected conclusion: structurally closer because the evidence factory,
governance, and bootstrap review layers exist; not closer in profit proof
because forward ledgers still have no 30/60/90 out-of-sample observations in
the local review sample.

### Task 3: Write Decision Log

**Files:**
- Create: `docs/goals/decision-records/2026-05-24-phase-13-decision-log.md`

- [x] **Step 1: Add family decisions**

Create one decision entry per registered family with:

- decision;
- owner-facing status;
- evidence refs;
- reason codes;
- next review trigger.

Expected: all family rows are `add_data`, not `owner_decision_review`.

- [x] **Step 2: Add major cycle decisions**

Add major cycle decisions for:

- data collection campaign;
- live execution and tiny-live line;
- data source retirement.

Expected:

- data collection campaign: `add_data`;
- live execution and tiny-live line: `pause_project_line`;
- data source retirement: no `retire_data_source` action yet because source
  usefulness has not been disproven by collected evidence.

### Task 4: Synchronize Roadmap And State

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`

- [x] **Step 1: Update roadmap Phase 13**

Add a delivered section with the committed review artifacts, family decisions,
local evidence commands, and the no-product-code/no-live boundary.

- [x] **Step 2: Update project completion state**

Record Phase 13 as the current completed round, link the review reports and
decision log, state that no current charter-compliant gaps remain, and append a
new round-history row.

### Task 5: Completion Report, Review, And Verification

**Files:**
- Create: `docs/goals/phase-reports/2026-05-24-phase-13-continuous-research-review-completion-report.md`

- [x] **Step 1: Write completion report**

Include Smart Search, local feasibility, local generated evidence, files
changed, subagent use, review passes, verification, secret safety, and remaining
gaps.

- [x] **Step 2: Review pass 1**

Run a requirements/spec review over:

```bash
docs/roadmap.md
docs/goals/project-completion-state.md
docs/goals/research-reviews/
docs/goals/decision-records/
docs/goals/phase-reports/2026-05-24-phase-13-continuous-research-review-completion-report.md
```

Expected: no unresolved Critical or Important Phase 13 requirement gaps.

- [x] **Step 3: Review pass 2**

Run a safety/quality review over the staged diff.

Expected:

- no product code changes;
- no `var/` files staged;
- no live execution enablement;
- no credentials, database dumps, generated local report artifacts, or local
  machine paths staged.

- [x] **Step 4: Verify**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git status --short
git diff --cached --name-only
git diff --cached --check
git diff --cached --no-ext-diff --unified=0
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

Expected:

- pytest passes with 912 passed and 4 skipped;
- ruff passes;
- diff checks pass;
- staged files are only Phase 13 docs;
- secret scan returns `[]`.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-05-24-phase-13-continuous-research-review-design.md docs/superpowers/plans/2026-05-24-phase-13-continuous-research-review.md docs/goals/research-reviews/2026-05-24-daily-quick-scan.md docs/goals/research-reviews/2026-05-24-weekly-effectiveness-review.md docs/goals/research-reviews/2026-05-24-monthly-owner-review.md docs/goals/decision-records/2026-05-24-phase-13-decision-log.md docs/goals/phase-reports/2026-05-24-phase-13-continuous-research-review-completion-report.md docs/roadmap.md docs/goals/project-completion-state.md
git commit -m "docs: add phase 13 review records"
```

Expected: one documentation-only Phase 13 commit, then merge/push to GitHub
from `main`.
