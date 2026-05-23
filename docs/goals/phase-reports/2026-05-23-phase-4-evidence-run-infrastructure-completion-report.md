# Immediate Phase 4 Completion Report: Evidence Run Infrastructure

## Scope

- Date: 2026-05-23.
- Phase: Immediate Phase 4: Evidence Run Infrastructure.
- Plan:
  `docs/superpowers/plans/2026-05-23-phase-4-evidence-run-infrastructure.md`.
- Boundary: operational evidence-run infrastructure only. This phase did not
  start the formal historical bootstrap or 30/60/90 observation campaign.

## Research And Feasibility

- Smart Search evidence is under
  `/tmp/smart-search-evidence/2026-05-23-phase4-evidence-run-infrastructure/`.
- Smart Search doctor recorded a timeout on the main route, but source fetch
  and documentation retrieval were usable.
- Fetched and applied Python documentation for:
  - exclusive local file creation with `os.open`;
  - atomic artifact replacement with `os.replace`;
  - deterministic JSON serialization with `json`.
- A local prototype confirmed lock contention detection and atomic JSON
  replacement before implementation.
- Local audit found that the existing CLI overwrote the research-loop Markdown
  report with the daily evidence report and lacked product-level lock,
  manifests, failed markers, latest pointers, and route-aware source health.

## Delivered

- Added `crypto_alpha_agent.pipeline.evidence_run_ops`:
  - exclusive local `EvidenceRunLock`;
  - `EvidenceRunManifest` and artifact status models;
  - atomic text/JSON artifact writers;
  - network route detection;
  - manifest input redaction and failure redaction.
- Updated `evidence-run`:
  - database-root default lock at `<db parent>/locks/evidence-run.lock`;
  - distinct daily report and research-loop report paths;
  - JSON payload, manifest, latest payload/manifest pointers, and failed-run
    marker artifacts;
  - nonzero exit code `2` for lock contention, path collision, thrown failure,
    or reported failed core pipeline step;
  - artifact path collision rejection before pipeline execution;
  - unique generated run ids for fast retries.
- Updated source health:
  - network route recorded as direct, proxy, blocked, or not applicable;
  - source failures redact URLs, API keys, Dune parameter values, Graph
    variable values, and Graph query text.
- Updated README, runbook, roadmap, and project state for the Phase 4 operator
  command set and retention expectations.

## Reviews

- Initial read-only gap audit found missing durable manifest, product-level
  lock, report artifact separation, failed marker, latest pointers, route
  recording, and complete secret handling.
- Review pass 1 found Critical issues in manifest secret redaction and default
  lock scoping. It also found Important issues around path collisions,
  same-second run-id reuse, URL redaction, and predicted artifact status.
- Fixes added regression coverage for:
  - default lock contention across report directories sharing one DB root;
  - Dune parameter, Graph variable, and Graph query redaction across stdout,
    JSON payload, manifest, and failed marker;
  - artifact path collision rejection;
  - safe default artifact filenames for unsafe user-supplied run ids;
  - generated run-id uniqueness;
  - slow-source failure redaction.
- Re-review confirmed no remaining Critical or Important findings. The only
  residual Minor note was that the code enum also permits `unknown` for
  network route while the runbook documents the operational routes normally
  produced by the CLI.

## Verification

Focused verification already run:

```bash
uv run --extra dev pytest tests/test_evidence_runner.py -q
```

Result: 19 passed.

```bash
uv run --extra dev pytest tests/test_scheduler_cli.py tests/test_documentation_contract.py -q
```

Result: 17 passed.

```bash
uv run --extra dev pytest tests/test_complete_evidence_system.py::test_complete_safe_autonomous_evidence_system tests/test_evidence_degradation.py -q
```

Result: 16 passed.

Final verification before commit:

- `uv run --extra dev pytest -q` passed with 797 tests after a transient real
  LLM summary rejection passed on immediate single-test rerun.
- `uv run --extra dev ruff check .` passed.
- `git diff --check` passed.
- `git diff --cached --check` passed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`
  passed with `[]`.

## Safety

Phase 4 preserved the charter boundaries:

- no wallet-key access;
- no exchange order routing;
- no live order submission;
- no real-capital execution;
- no MEV, mempool, bridge-race, flash-loan, premium-RPC, or speed-edge path;
- no secrets persisted in manifests, failed markers, reports, memory, stdout,
  or staged diffs by the new paths.

## Next Phase

Phase 4 was committed as `a31bda7 feat: add evidence run infrastructure` and
pushed to GitHub. The next roadmap slice is Immediate Phase 5: Data And
Strategy Expansion.
