# Phase 13 Continuous Research Review Design

## Goal

Create the read-only review layer required by Phase 13: daily, weekly, and
monthly review reports plus explicit decision records that judge whether the
system is getting closer to cost-adjusted crypto alpha under the owner's
low-capital charter.

## Context

Phase 13 follows the roadmap after Phase 7 historical bootstrap and Phase 12
profit governance. The project already has safe public-data ingestion,
historical bootstrap reports, daily and weekly evidence reports, AI research
memos, profit governance scoreboards, stopped-family ledgers, paper-only
portfolio selection, and rollout review artifacts. The remaining gap is not
more product code. It is an owner-facing review trail that turns those outputs
into clear keep, stop, redesign, add-data, retire-source, or pause decisions.

Smart Search evidence was collected under
`/tmp/smart-search-evidence/20260524-phase13-review/`:

- `smart-search doctor --format json` returned `ok=true`.
- `smart-search deep "Phase 13 continuous research review reporting decision records trading strategy evidence review scorecards stop keep redesign add data pause" --format json` generated a deep-research plan.
- `01-search.json` supported decision journals, trading review cadence,
  strategy scorecards, stop/keep/redesign framing, backtesting limits, and
  forward paper testing.
- `02-fetch-decision-journal.md` supported recording what was known and
  believed at decision time to reduce hindsight bias.
- `03-fetch-journal-review.md` supported a daily quick review, weekly main
  review, and monthly big-picture review cadence.
- `04-fetch-strategy-metrics.md` supported using profit factor, max drawdown,
  Sharpe/risk-adjusted return, win rate, and expectancy as review metrics.
- `05-fetch-backtesting.md` supported treating backtests as due diligence, not
  profit proof, and accounting for costs before drawing conclusions.

Local feasibility was verified in an isolated worktree:

- Baseline `uv run --extra dev pytest -q` passed with 912 tests, 4 skipped,
  and 2 dependency warnings.
- Existing read-only CLI artifacts were generated against empty local ledgers
  under ignored `var/phase13/`, `var/reports/phase13/`, and
  `var/run-manifests/phase13/`.
- `governance-report` classified every registered family as `add_data` with
  `uses_real_capital=false` and `live_order_routing=false`.
- `historical-bootstrap` confirmed the forward evidence target policy
  `future_evidence_run_observations_only`, blocked network source collection
  when `--allow-network` was omitted, and kept real capital and live order
  routing disabled.
- `evidence-report --daily`, `evidence-report --weekly`, and
  `ai-research-memo` produced read-only outputs with no LLM use in
  `--offline-only` report mode and no live routing.

## Alternatives Considered

1. Documentation-only review artifacts. This matches Phase 13's completion
   standard because the project already has report builders and the roadmap
   explicitly says no new product code should be added.
2. Add a new review CLI or SQLite decision ledger. This would make future
   automation easier but violates the phase's "review reports and decision
   records only" boundary.
3. Add tests around documentation contracts. This would be safe, but still
   expands code/test surface for a phase whose deliverable is the review trail.

The chosen approach is option 1.

## Artifact Model

Phase 13 produces committed Markdown artifacts:

- Daily quick scan report: new evidence arrival, source failures, degraded
  strategies, next experiment validity, and same-day safety status.
- Weekly effectiveness review: family-by-family comparison, AI proposal
  quality, stopped-family state, and next-week actions.
- Monthly owner review: whether the project is closer to cost-adjusted edge,
  whether to redesign, add data, retire sources, pause project lines, or keep
  collecting.
- Decision log: one current owner-facing decision per active family plus major
  cycle decisions.

Generated local reports under `var/` are evidence inputs only. They remain
ignored and are not staged.

## Decision Vocabulary

The review artifacts use the Phase 13 decision vocabulary:

- `keep_collecting`
- `stop_family`
- `redesign_validator`
- `add_data`
- `retire_data_source`
- `pause_project_line`

For compatibility with existing governance reports, family rows may also cite
Phase 12 governance actions such as `owner_decision_review`, but no Phase 13
decision may approve real capital or order routing.

## Safety

The review is read-only. It does not create new strategy logic, validators,
source adapters, order routing, wallet access, private infrastructure, MEV,
speed-edge logic, or real-capital controls. It records that the current code
continues to expose disabled execution flags through
`live_execution_allowed=false`, `live_execution_enabled=false`,
`uses_real_capital=false`, and `live_order_routing=false` in the relevant
guards and artifacts.

## Completion Criteria

Phase 13 is complete when:

- daily, weekly, and monthly review reports are committed;
- each active registered family has a current owner-facing decision;
- the weekly and monthly reviews both point to an explicit decision record;
- the review says whether the project is closer to cost-adjusted edge and ties
  that answer to local metrics, reports, and evidence references;
- roadmap and project completion state say there are no remaining
  charter-compliant gaps in the current project vision;
- full tests, ruff, diff checks, and secret checks pass;
- the documentation-only commit is pushed.
