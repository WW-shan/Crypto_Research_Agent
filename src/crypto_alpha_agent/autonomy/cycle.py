from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from crypto_alpha_agent.autonomy.codex_runner import CodexRunner, CodexUnavailableError
from crypto_alpha_agent.autonomy.context import build_creation_context
from crypto_alpha_agent.autonomy.models import (
    CodexExecResult,
    CreationCycleReport,
    CreationObject,
    CreationRoleNote,
)
from crypto_alpha_agent.autonomy.prompts import render_builder_prompt, render_creator_prompt
from crypto_alpha_agent.autonomy.store import AutonomyStore
from crypto_alpha_agent.autonomy.worktrees import AutonomyWorktreeManager
from crypto_alpha_agent.llm.runtime import parse_structured_llm_json

_DEFAULT_RUNNER_COMMANDS = ["python -m pytest tests/test_creation_autonomy_store.py -q"]


def run_creation_cycle(
    *,
    repo_root: str | Path,
    db_path: str | Path,
    memory_path: str | Path,
    reports_root: str | Path,
    autonomy_root: str | Path,
    llm_runtime: Any,
    codex: CodexRunner | Any | None = None,
    max_creations: int = 1,
    run_commands: bool = True,
) -> CreationCycleReport:
    repo_path = Path(repo_root)
    reports_path = Path(reports_root)
    autonomy_path = Path(autonomy_root)
    db_path = Path(db_path)
    memory_path = Path(memory_path)
    codex_runner = CodexRunner() if codex is None else codex

    health_result = codex_runner.health_check(workdir=repo_path)
    _ensure_health_check_succeeded(health_result)

    context = build_creation_context(
        reports_root=reports_path,
        autonomy_root=autonomy_path,
    )
    task_id = _task_id(context)
    creator_prompt = render_creator_prompt(task_id=task_id, context=context)
    creation = _parse_creation(llm_runtime.llm(creator_prompt))
    runner_commands = creation.verification_commands or list(_DEFAULT_RUNNER_COMMANDS)

    store = AutonomyStore(root=autonomy_path, reports_root=reports_path)
    task = store.create_task(task_id=task_id, creation=creation)
    store.write_role_note(
        task.task_id,
        "director",
        CreationRoleNote(
            role="director",
            summary=(
                f"Create one object from {len(context['context_refs'])} report refs; "
                f"max_creations={max_creations}."
            ),
            evidence_refs=list(context["context_refs"]),
        ),
    )
    store.write_json(task.task_id, "creation.json", creation.model_dump(mode="json"))

    builder_prompt = render_builder_prompt(
        creation_json=creation.model_dump(mode="json"),
        runner_commands=runner_commands,
    )
    store.write_text(task.task_id, "builder-prompt.md", builder_prompt)

    workdir = task.path
    worktrees: AutonomyWorktreeManager | None = None
    if run_commands:
        worktrees = AutonomyWorktreeManager(
            repo_root=repo_path,
            autonomy_root=autonomy_path,
        )
        workdir = worktrees.create_task_worktree(task.task_id)

    builder_result = codex_runner.exec_prompt(workdir=workdir, prompt=builder_prompt)
    store.write_json(
        task.task_id,
        "builder-output.json",
        builder_result.model_dump(mode="json"),
    )

    runner_exit_code: int | None
    patch_path: Path | None = None
    if run_commands:
        runner_exit_code = _run_verification(
            commands=runner_commands,
            workdir=workdir,
            store=store,
            task_id=task.task_id,
        )
        patch_path = _write_patch(workdir=workdir, store=store, task_id=task.task_id)
    else:
        runner_exit_code = None
        store.write_text(
            task.task_id,
            "runner.md",
            "# Runner\n\nVerification skipped because run_commands=false.\n",
        )

    rejected_reason_codes = _rejected_reason_codes(
        builder_result=builder_result,
        runner_exit_code=runner_exit_code,
        run_commands=run_commands,
    )
    accepted = not rejected_reason_codes
    if accepted and run_commands and worktrees is not None:
        worktrees.promote_task(
            task_id=task.task_id,
            message=f"Promote creation task {task.task_id}",
        )

    report = CreationCycleReport(
        task_id=task.task_id,
        creation=creation,
        accepted=accepted,
        status=creation.status if accepted else "needs_fix",
        report_path=str(reports_path / "creation" / "latest.md"),
        json_path=str(reports_path / "creation" / "latest.json"),
        task_path=str(task.path),
        patch_path=None if patch_path is None else str(patch_path),
        runner_exit_code=runner_exit_code,
        rejected_reason_codes=rejected_reason_codes,
        next_actions=_next_actions(
            creation=creation,
            rejected_reason_codes=rejected_reason_codes,
            runner_commands=runner_commands,
            run_commands=run_commands,
        ),
    )
    latest_json_payload = {
        "report": report.model_dump(mode="json"),
        "llm_metadata": _llm_metadata(llm_runtime),
        "inputs": {
            "db_path": str(db_path),
            "memory_path": str(memory_path),
            "max_creations": max_creations,
            "run_commands": run_commands,
        },
    }
    store.write_latest_report(_render_creation_cycle_markdown(report))
    store.write_latest_json(latest_json_payload)
    store.append_backlog(creation)
    return report


def _parse_creation(raw_response: Any) -> CreationObject:
    if isinstance(raw_response, str):
        parsed = parse_structured_llm_json(raw_response, CreationObject)
        return CreationObject.model_validate(parsed.model_dump(mode="json"))
    if isinstance(raw_response, CreationObject):
        return CreationObject.model_validate(raw_response.model_dump(mode="json"))
    if isinstance(raw_response, BaseModel):
        return CreationObject.model_validate(raw_response.model_dump(mode="json"))
    return CreationObject.model_validate(raw_response)


def _ensure_health_check_succeeded(result: Any) -> None:
    exit_code = getattr(result, "exit_code", None)
    if exit_code in (None, 0):
        return
    detail = getattr(result, "stderr", "") or getattr(result, "stdout", "") or exit_code
    raise CodexUnavailableError(f"Codex health check failed: {detail}")


def _task_id(context: dict[str, Any]) -> str:
    context_text = json.dumps(context, sort_keys=True, allow_nan=False, default=str)
    digest = hashlib.sha256(context_text.encode("utf-8")).hexdigest()[:10]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"creation-{timestamp}-{digest}"


def _run_verification(
    *,
    commands: list[str],
    workdir: Path,
    store: AutonomyStore,
    task_id: str,
) -> int:
    sections = ["# Runner", ""]
    highest_exit_code = 0
    for command in commands:
        result = subprocess.run(
            command,
            cwd=workdir,
            shell=True,
            text=True,
            capture_output=True,
        )
        exit_code = int(result.returncode)
        if exit_code != 0:
            highest_exit_code = max(highest_exit_code, exit_code)
        sections.extend(
            [
                f"## `{command}`",
                "",
                f"Exit code: {exit_code}",
                "",
                "### stdout",
                "",
                "```",
                result.stdout,
                "```",
                "",
                "### stderr",
                "",
                "```",
                result.stderr,
                "```",
                "",
            ]
        )
    store.write_text(task_id, "runner.md", "\n".join(sections))
    return highest_exit_code


def _write_patch(*, workdir: Path, store: AutonomyStore, task_id: str) -> Path:
    subprocess.run(
        ["git", "add", "-N", "."],
        cwd=workdir,
        text=True,
        capture_output=True,
        check=True,
    )
    result = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=workdir,
        text=True,
        capture_output=True,
        check=True,
    )
    return store.write_text(task_id, "patch.diff", result.stdout)


def _rejected_reason_codes(
    *,
    builder_result: CodexExecResult,
    runner_exit_code: int | None,
    run_commands: bool,
) -> list[str]:
    reasons: list[str] = []
    if builder_result.exit_code != 0:
        reasons.append("codex_builder_failed")
    if run_commands and runner_exit_code != 0:
        reasons.append("verification_failed")
    return reasons


def _next_actions(
    *,
    creation: CreationObject,
    rejected_reason_codes: list[str],
    runner_commands: list[str],
    run_commands: bool,
) -> list[str]:
    if not rejected_reason_codes:
        if run_commands:
            return [creation.continuation_reason]
        return ["Run verification commands before promotion.", creation.continuation_reason]
    actions: list[str] = []
    if "codex_builder_failed" in rejected_reason_codes:
        actions.append("Inspect builder-output.json and rerun the builder.")
    if "verification_failed" in rejected_reason_codes:
        actions.append(f"Fix failing verification: {', '.join(runner_commands)}")
    return actions


def _llm_metadata(llm_runtime: Any) -> Any:
    metadata = getattr(llm_runtime, "metadata", None)
    if not callable(metadata):
        return None
    return metadata()


def _render_creation_cycle_markdown(report: CreationCycleReport) -> str:
    lines = [
        "# Creation Cycle Report",
        "",
        f"- Task: {report.task_id}",
        f"- Title: {report.creation.title}",
        f"- Accepted: {report.accepted}",
        f"- Status: {report.status}",
        f"- Runner exit code: {report.runner_exit_code}",
    ]
    if report.patch_path:
        lines.append(f"- Patch: {report.patch_path}")
    if report.rejected_reason_codes:
        lines.extend(["", "Rejected reasons:"])
        lines.extend(f"- {reason}" for reason in report.rejected_reason_codes)
    if report.next_actions:
        lines.extend(["", "Next actions:"])
        lines.extend(f"- {action}" for action in report.next_actions)
    lines.extend(
        [
            "",
            "## Hypothesis",
            "",
            report.creation.hypothesis,
            "",
            "## First Code Change",
            "",
            report.creation.first_code_change,
        ]
    )
    return "\n".join(lines) + "\n"
