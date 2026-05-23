# Phase Completion Reports

This directory stores one completion report for every completed roadmap Phase
or Immediate Phase.

Each report must let a future agent or owner understand what happened without
reading the full chat history. Use this filename pattern:

```text
YYYY-MM-DD-phase-<phase-or-immediate-phase>-completion-report.md
```

Each report must include:

- Phase name, date, commit or pending commit reference, owner objective, and
  whether the round was implementation, review-only, or documentation-only.
- Smart Search query, evidence paths, fetched sources, and external findings
  used before design.
- Local code/data feasibility findings, files inspected, existing patterns
  reused, and blockers found.
- Substep validation or prototype results, including rejected or blocked
  candidates and exact blocked reasons.
- Files changed, tests added or updated, docs changed, and artifacts produced.
- Subagents used, their assignments, and how their findings were reviewed.
- Review passes, Critical or Important findings, fixes, and re-review status.
- Verification commands and exact pass/fail results.
- Secret-safety result and confirmation that `.env`, keys, databases, reports,
  caches, and local artifacts were not staged.
- Remaining gaps, next Phase recommendation, and any owner decisions required.

Link the report from `docs/goals/project-completion-state.md` before marking a
Phase complete.
