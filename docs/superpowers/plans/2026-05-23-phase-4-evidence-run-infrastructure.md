# Phase 4 Evidence Run Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `evidence-run` operationally repeatable by adding product-level manifests, locking, failed-run markers, artifact preservation, and secret-safe run records without starting the formal Phase 7 evidence campaign.

**Architecture:** Keep the existing evidence pipeline as the research engine and add a small operations layer around it. `run_daily_evidence_pipeline()` keeps producing a typed `EvidenceRunnerReport`; the CLI becomes responsible for one-run-at-a-time locking, distinct research/daily/weekly artifacts, JSON capture, manifest writing, latest pointers, and failed-run markers. All persisted operational records use redacted inputs and keep `uses_real_capital=false` and `live_order_routing=false`.

**Tech Stack:** Python 3.12, Pydantic, argparse CLI, SQLite-backed existing ledgers, JSON/Markdown artifacts, stdlib `os.open(..., O_CREAT | O_EXCL)` for lock creation, `os.replace` for atomic file replacement, pytest, ruff.

---

## External Evidence

Evidence directory: `/tmp/smart-search-evidence/2026-05-23-phase4-evidence-run-infrastructure/`.

Commands run:

```bash
smart-search doctor --format json --output /tmp/smart-search-evidence/2026-05-23-phase4-evidence-run-infrastructure/00-doctor.json
smart-search deep "Immediate Phase 4 Evidence Run Infrastructure for a Python crypto research agent: one-shot CLI run manifests, local file locks, failed-run markers, artifact retention, retry-safe operator evidence pipeline, no live trading or secrets" --budget deep --format json --output /tmp/smart-search-evidence/2026-05-23-phase4-evidence-run-infrastructure/01-deep-plan.json
smart-search fetch "https://docs.python.org/3/library/os.html#os.open" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase4-evidence-run-infrastructure/02-python-os-open.md
smart-search fetch "https://docs.python.org/3/library/os.html#os.replace" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase4-evidence-run-infrastructure/03-python-os-replace.md
smart-search fetch "https://docs.python.org/3/library/json.html" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase4-evidence-run-infrastructure/04-python-json.md
```

Notes:

- `doctor` reported `ok=false` because the main xAI route timed out, but Tavily fetch and Context7 docs capability were reachable. The timeout is recorded as an external-provider limitation; no native web fallback was used.
- `smart-search deep` produced a high-difficulty, fetch-before-claim plan for run manifests, locks, failed markers, retention, and secret-safe operation.
- Python docs evidence supports `os.open` with bitwise-combined flags for low-level file descriptors, `os.rename`/`os.replace` style atomic replacement on same filesystem, and JSON serialization with `sort_keys`/`indent`.

Small validation/prototype:

```bash
uv run --extra dev python - <<'PY'
from pathlib import Path
import os, json, tempfile
with tempfile.TemporaryDirectory() as tmp:
    lock = Path(tmp) / 'run.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, b'{"run_id":"one"}')
    os.close(fd)
    try:
        os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print('lock_conflict_detected')
    target = Path(tmp) / 'manifest.json'
    temp = Path(tmp) / 'manifest.tmp'
    temp.write_text(json.dumps({'status':'success'}, sort_keys=True), encoding='utf-8')
    os.replace(temp, target)
    print(target.read_text(encoding='utf-8'))
PY
```

Result:

```text
lock_conflict_detected
{"status": "success"}
```

## Local Feasibility

Read and verified:

- `docs/roadmap.md` says Immediate Phase 4 requires a daily run wrapper or command set, run manifest, lock handling, failed-run marker/local notification hook, artifact preservation under `var/`, repeated safe operation, and no formal Phase 7 validation campaign.
- `docs/runbook.md` currently documents an external `flock` wrapper, stdout/stderr capture, and retention guidance, but product code does not implement manifest/lock/failed-marker/latest behavior.
- `src/crypto_alpha_agent/pipeline/evidence_runner.py` already performs ingestion, validation, paper simulation, memory feedback, source-health summaries, and Markdown research-loop artifact writing.
- `src/crypto_alpha_agent/cli.py` currently overwrites the runner's research-loop Markdown report with the daily evidence Markdown report at the same `--report-out` path.
- `tests/test_evidence_runner.py` has deterministic CCXT fixtures and currently passes with 8 tests.

Subagent gap audit:

- `Herschel` (`019e5525-9963-7f93-8885-69bd131436b0`) found Critical gaps: no persisted manifest, no product-level lock, and ambiguous report preservation. Important gaps: no failed-run marker, no latest/retention pointers, no network route in source health/manifest, and partial secret-safety for failure strings and direct credential flags.

## File Map

- Create `src/crypto_alpha_agent/pipeline/evidence_run_ops.py`: lock context manager, manifest models, atomic JSON/text writes, latest-copy helper, redacted input builder, network route detection, failed-marker writer.
- Modify `src/crypto_alpha_agent/pipeline/evidence_runner.py`: add source-health `network_route`, redact core-source failure strings, and allow a separate `research_report_out` path without changing core research behavior.
- Modify `src/crypto_alpha_agent/cli.py`: add `evidence-run` operational arguments, acquire default lock, write distinct research/daily/weekly Markdown, JSON capture, manifest, latest pointers, and failed markers around nonzero/exception paths.
- Modify `tests/test_evidence_runner.py`: add RED/GREEN tests for manifest persistence, lock contention, failed marker creation, artifact preservation, latest pointers, source-health route, and redaction.
- Modify `docs/runbook.md`: update `evidence-run` operations commands to use the product lock/manifest/failed marker paths.
- Modify `docs/roadmap.md`: add Phase 4 completion record after verification.
- Modify `docs/goals/project-completion-state.md`: start/complete Round 6 and fix Round 5 commit from `pending` to `9fb1945`.
- Create `docs/goals/phase-reports/2026-05-23-phase-4-evidence-run-infrastructure-completion-report.md`: Phase completion report.

## Task 1: Manifest, Lock, And Atomic Artifact Utility

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/evidence_run_ops.py`
- Test: `tests/test_evidence_runner.py`

- [ ] **Step 1: Write failing utility tests**

Add tests:

```python
def test_evidence_run_lock_blocks_second_holder_and_removes_file(tmp_path):
    from crypto_alpha_agent.pipeline.evidence_run_ops import EvidenceRunLock, EvidenceRunLockError

    lock_path = tmp_path / "locks" / "evidence-run.lock"
    with EvidenceRunLock(lock_path, run_id="run-a"):
        assert lock_path.exists()
        try:
            with EvidenceRunLock(lock_path, run_id="run-b"):
                raise AssertionError("second lock should not be acquired")
        except EvidenceRunLockError as exc:
            assert exc.reason_code == "evidence_run_lock_held"
    assert not lock_path.exists()
```

```python
def test_write_json_artifact_replaces_atomically_and_updates_latest(tmp_path):
    from crypto_alpha_agent.pipeline.evidence_run_ops import write_json_artifact

    target = tmp_path / "manifests" / "run.json"
    latest = tmp_path / "manifests" / "latest.json"
    write_json_artifact(target, {"status": "success", "run_id": "run-a"}, latest_path=latest)
    write_json_artifact(target, {"status": "failed", "run_id": "run-a"}, latest_path=latest)

    assert json.loads(target.read_text(encoding="utf-8"))["status"] == "failed"
    assert json.loads(latest.read_text(encoding="utf-8"))["status"] == "failed"
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_runner.py::test_evidence_run_lock_blocks_second_holder_and_removes_file tests/test_evidence_runner.py::test_write_json_artifact_replaces_atomically_and_updates_latest -q
```

Expected: fail because `crypto_alpha_agent.pipeline.evidence_run_ops` does not exist.

- [ ] **Step 3: Implement utility module**

Implement:

- `EvidenceRunLockError(RuntimeError)` with `reason_code="evidence_run_lock_held"`.
- `EvidenceRunLock(path, run_id)` using `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)`, writes a small JSON lock payload, closes the fd, and removes the lock file on exit if still owned by that run id.
- `write_json_artifact(path, payload, latest_path=None)` using same-directory temp file and `os.replace`.
- `write_text_artifact(path, text, latest_path=None)` using the same atomic replace pattern.
- `network_route_from_environment(env=os.environ, allow_network=True)` returning `blocked`, `proxy`, or `direct`.
- `redacted_evidence_run_inputs(args_or_mapping)` that stores paths, symbols, booleans, and credential-configured booleans only; never store `dune_api_key`, proxy values, raw provider URLs containing credentials, or raw GraphQL documents in failure surfaces.

- [ ] **Step 4: Run GREEN tests**

Run the two utility tests above and expect pass.

## Task 2: Source Health Route And Research Report Preservation

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/evidence_runner.py`
- Test: `tests/test_evidence_runner.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_evidence_runner_records_network_route_and_redacts_core_failure(tmp_path, monkeypatch):
    class FailingCoreCollector:
        def fetch_ohlcv(self, *args, **kwargs):
            raise RuntimeError("failed via https://secret.example/path")

    monkeypatch.setenv("CRYPTO_ALPHA_AGENT_PROXY", "http://127.0.0.1:" + "10808")
    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "research.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        ccxt_collector=FailingCoreCollector(),
    )

    assert report.source_health.items[0].network_route == "proxy"
    assert report.source_health.items[0].failure == "failed via [REDACTED_URL]"
```

```python
def test_evidence_runner_can_write_research_report_to_distinct_path(tmp_path):
    research_out = tmp_path / "daily.research.md"
    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=research_out,
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        run_id="distinct-report",
        ccxt_collector=DeterministicCcxtCollector(),
    )

    assert report.report_artifact == str(research_out)
    assert research_out.exists()
    assert "Research Loop Report" in research_out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_runner.py::test_evidence_runner_records_network_route_and_redacts_core_failure tests/test_evidence_runner.py::test_evidence_runner_can_write_research_report_to_distinct_path -q
```

Expected: first test fails because `network_route` is missing and core failure is not URL-redacted; second may pass but locks report preservation behavior.

- [ ] **Step 3: Implement runner updates**

Add `network_route` to `SourceHealthSummary` as `Literal["direct", "proxy", "blocked", "not_applicable", "unknown"] = "unknown"`. Populate it for core, optional, not-configured, and blocked source health. Redact core-source failures through the existing `_redact_failure()`.

- [ ] **Step 4: Run GREEN tests**

Run the two tests and expect pass.

## Task 3: CLI Operational Wrapper

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_evidence_runner.py`

- [ ] **Step 1: Write failing CLI operation tests**

Add tests:

```python
def test_evidence_run_cli_persists_manifest_json_latest_and_distinct_artifacts(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda exchange_id: DeterministicCcxtCollector(),
    )
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    daily_out = tmp_path / "reports" / "daily" / "2026-05-23.md"
    weekly_out = tmp_path / "reports" / "weekly" / "2026-W21.md"
    research_out = tmp_path / "reports" / "daily" / "2026-05-23.research.md"
    json_out = tmp_path / "reports" / "daily" / "2026-05-23.json"
    manifest_out = tmp_path / "run-manifests" / "2026-05-23.json"

    exit_code = main([
        "evidence-run", "--db", str(db_path), "--memory", str(memory_path),
        "--report-out", str(daily_out), "--weekly-report-out", str(weekly_out),
        "--research-report-out", str(research_out), "--json-out", str(json_out),
        "--manifest-out", str(manifest_out),
        "--allow-network", "--symbol", "BTC/USDT",
        "--funding-symbol", "BTC/USDT:USDT", "--timeframe", "1h",
        "--run-id", "phase4-cli",
    ])

    payload = json.loads(capsys.readouterr().out)
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["manifest_out"] == str(manifest_out)
    assert manifest["run_id"] == "phase4-cli"
    assert manifest["status"] == "success"
    assert manifest["artifacts"]["daily_report"] == str(daily_out)
    assert manifest["artifacts"]["research_report"] == str(research_out)
    assert manifest["artifacts"]["json_payload"] == str(json_out)
    assert daily_out.exists() and research_out.exists() and weekly_out.exists() and json_out.exists()
    assert "Daily Evidence Report" in daily_out.read_text(encoding="utf-8")
    assert "Research Loop Report" in research_out.read_text(encoding="utf-8")
    assert json.loads(json_out.read_text(encoding="utf-8"))["command"] == "evidence-run"
    assert (manifest_out.parent / "latest.json").exists()
```

```python
def test_evidence_run_cli_lock_contention_writes_failure_marker(tmp_path, capsys, monkeypatch):
    from crypto_alpha_agent.pipeline.evidence_run_ops import EvidenceRunLock

    lock_path = tmp_path / "locks" / "evidence-run.lock"
    failed_marker = tmp_path / "run-manifests" / "failed" / "phase4-lock.json"
    with EvidenceRunLock(lock_path, run_id="already-running"):
        exit_code = main([
            "evidence-run", "--db", str(tmp_path / "research.sqlite"),
            "--memory", str(tmp_path / "memory.jsonl"),
            "--report-out", str(tmp_path / "daily.md"),
            "--manifest-out", str(tmp_path / "manifest.json"),
            "--failed-marker-out", str(failed_marker),
            "--lock-path", str(lock_path),
            "--allow-network", "--symbol", "BTC/USDT",
            "--funding-symbol", "BTC/USDT:USDT", "--timeframe", "1h",
            "--run-id", "phase4-lock",
        ])

    payload = json.loads(capsys.readouterr().out)
    marker = json.loads(failed_marker.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["status"] == "failed"
    assert payload["reason_code"] == "evidence_run_lock_held"
    assert marker["status"] == "failed"
    assert marker["reason_code"] == "evidence_run_lock_held"
```

```python
def test_evidence_run_cli_failure_marker_redacts_configured_values(tmp_path, capsys, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("provider failed with " + kwargs["dune_api_key"])

    monkeypatch.setattr("crypto_alpha_agent.cli.run_daily_evidence_pipeline", boom)
    failed_marker = tmp_path / "failed.json"
    secret = "cfg-phase4-secret-value-abcdef"
    exit_code = main([
        "evidence-run", "--db", str(tmp_path / "research.sqlite"),
        "--memory", str(tmp_path / "memory.jsonl"),
        "--report-out", str(tmp_path / "daily.md"),
        "--failed-marker-out", str(failed_marker),
        "--allow-network", "--symbol", "BTC/USDT",
        "--funding-symbol", "BTC/USDT:USDT", "--timeframe", "1h",
        "--include-dune", "--dune-query-id", "1", "--dune-api-key", secret,
        "--run-id", "phase4-secret",
    ])

    payload_text = capsys.readouterr().out
    marker_text = failed_marker.read_text(encoding="utf-8")
    assert exit_code == 2
    assert secret not in payload_text
    assert secret not in marker_text
```

- [ ] **Step 2: Run RED CLI tests**

Run the three tests and expect fail because CLI args and operational wrapper do not exist.

- [ ] **Step 3: Implement CLI operational wrapper**

Add args:

- `--research-report-out`: optional distinct research-loop Markdown path; default `report_out.with_name(report_out.stem + ".research.md")`.
- `--json-out`: optional JSON capture path; default `report_out.with_suffix(".json")`.
- `--manifest-out`: optional manifest path; default `db.parent / "run-manifests" / "evidence-run" / f"{run_id}.json"` after report resolves run id.
- `--latest-manifest-out`: optional; default `manifest_out.parent / "latest.json"`.
- `--latest-report-out`: optional; default `report_out.parent / "latest.md"`.
- `--latest-json-out`: optional; default `json_out.parent / "latest.json"`.
- `--lock-path`: optional; default `db.parent / "locks" / "evidence-run.lock"`.
- `--failed-marker-out`: optional; default `manifest_out.parent / "failed" / f"{run_id}.json"`.
- `--no-lock`: explicit escape hatch for tests/operators; do not use in runbook examples.

Wrap `_handle_evidence_run` with:

1. Resolve preliminary run id from `args.run_id` or UTC timestamp for lock/failed marker naming.
2. Acquire `EvidenceRunLock` unless `--no-lock`.
3. Call `run_daily_evidence_pipeline(..., report_out=research_report_out, ...)`.
4. Build daily and weekly evidence reports into separate files.
5. Build payload, write `json_out`, write manifest, and update latest copies.
6. On lock contention or exception, write failed marker with redacted message and return safe JSON with exit-like status. Because `main()` currently always returns `0`, make `_handle_evidence_run` include `exit_code` and update `main()` to return `payload.get("exit_code", 0)` for all handlers. Existing commands without `exit_code` remain unchanged.

- [ ] **Step 4: Run GREEN CLI tests**

Run the three CLI tests and `tests/test_evidence_runner.py -q`.

## Task 4: Documentation And State

**Files:**
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-23-phase-4-evidence-run-infrastructure-completion-report.md`

- [ ] **Step 1: Update runbook**

Document product-level `evidence-run` command with:

- `--manifest-out var/run-manifests/evidence-run/YYYY-MM-DD.json`
- `--json-out var/reports/daily/YYYY-MM-DD.json`
- `--research-report-out var/reports/daily/YYYY-MM-DD.research.md`
- `--lock-path var/locks/evidence-run.lock`
- `--failed-marker-out var/run-manifests/evidence-run/failed/YYYY-MM-DD.json`
- latest pointers and retention expectations.

- [ ] **Step 2: Update roadmap and state**

Roadmap: mark Immediate Phase 4 complete after verification and set Immediate Phase 5 as next.

State: move to Round 6, record Phase 4 evidence, and repair Round 5 commit to `9fb1945 test: formalize real llm policy`.

- [ ] **Step 3: Write completion report**

Include Smart Search evidence, local feasibility, subagent audit, prototype results, files changed, review passes, verification, staged secret scan, and next phase recommendation.

## Task 5: Review, Verification, Commit, Push

**Files:**
- No predetermined source files; fix review findings where relevant.

- [ ] **Step 1: Run focused tests**

```bash
uv run --extra dev pytest tests/test_evidence_runner.py -q
```

- [ ] **Step 2: Run two review passes**

Review pass 1: spec/requirements review for Phase 4.

Review pass 2: code-quality/secret-safety review for Phase 4.

Fix all Critical or Important issues and re-review after fixes.

- [ ] **Step 3: Run full verification**

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git status --short --branch --untracked-files=all
```

- [ ] **Step 4: Stage and run staged secret checks**

```bash
git add docs src tests
git diff --cached --check
git diff --cached --name-only
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

- [ ] **Step 5: Commit and push**

```bash
git commit -m "feat: add evidence run operations"
git push origin main
```

## Self-Review

- Spec coverage: Tasks cover the manifest, lock, failed marker, artifact preservation, latest pointers, network route, source-health/failure redaction, runbook/state/report updates, review, verification, commit, and push.
- Placeholder scan: No `TODO`, `TBD`, or unspecified implementation steps remain.
- Type consistency: `EvidenceRunLock`, `EvidenceRunLockError`, `write_json_artifact`, and CLI argument names are used consistently across tasks.
- Scope check: This plan does not add new data sources, strategy validators, cost modeling, AI researcher behavior, portfolio governance, formal evidence campaign targets, live trading, wallets, order routing, MEV, premium RPC, or real-capital execution.
