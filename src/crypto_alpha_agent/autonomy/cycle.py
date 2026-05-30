from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
from crypto_alpha_agent.llm.redaction import redact_text
from crypto_alpha_agent.llm.runtime import parse_structured_llm_json
from crypto_alpha_agent.pipeline.markdown import render_creation_cycle_markdown

_DEFAULT_RUNNER_COMMANDS = ["python -m pytest tests/test_creation_autonomy_store.py -q"]
_RUNNER_TIMEOUT_SECONDS = 300
_UNSAFE_COMMAND_EXIT_CODE = 126
_DEFAULT_RUNNER_IMAGE = "ghcr.io/ww-shan/crypto-alpha-agent:main"


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
    write_latest_json: bool = True,
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
    worktree_error: str | None = None
    if run_commands:
        worktrees = AutonomyWorktreeManager(
            repo_root=repo_path,
            autonomy_root=autonomy_path,
        )
        try:
            workdir = worktrees.create_task_worktree(task.task_id)
        except subprocess.SubprocessError as exc:
            worktree_error = redact_text(_subprocess_failure_text(exc))

    if worktree_error is None:
        builder_result = codex_runner.exec_prompt(workdir=workdir, prompt=builder_prompt)
    else:
        builder_result = CodexExecResult(
            command=["codex", "exec"],
            exit_code=1,
            stderr=f"Builder skipped because task worktree creation failed: {worktree_error}",
        )
    store.write_json(
        task.task_id,
        "builder-output.json",
        builder_result.model_dump(mode="json"),
    )

    runner_exit_code: int | None
    patch_path: Path | None = None
    patch_error: str | None = None
    if run_commands and worktree_error is None:
        runner_exit_code = _run_verification(
            commands=runner_commands,
            workdir=workdir,
            store=store,
            task_id=task.task_id,
        )
        try:
            patch_path = _write_patch(workdir=workdir, store=store, task_id=task.task_id)
        except subprocess.SubprocessError as exc:
            patch_error = redact_text(_subprocess_failure_text(exc))
    else:
        runner_exit_code = None
        reason = (
            "Verification skipped because task worktree creation failed."
            if worktree_error is not None
            else "Verification skipped because run_commands=false."
        )
        store.write_text(
            task.task_id,
            "runner.md",
            f"# Runner\n\n{reason}\n",
        )

    rejected_reason_codes = _rejected_reason_codes(
        builder_result=builder_result,
        runner_exit_code=runner_exit_code,
        run_commands=run_commands,
    )
    if worktree_error is not None:
        rejected_reason_codes.append("worktree_creation_failed")
    if patch_error is not None:
        rejected_reason_codes.append("patch_export_failed")
    promotion_error: str | None = None
    if not rejected_reason_codes and run_commands and worktrees is not None:
        try:
            worktrees.promote_task(
                task_id=task.task_id,
                message=f"Promote creation task {task.task_id}",
            )
        except Exception as exc:  # noqa: BLE001 - report promotion failures fail-closed.
            promotion_error = redact_text(exc)
            rejected_reason_codes.append("promotion_failed")
    accepted = not rejected_reason_codes

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
            promotion_error=promotion_error,
            worktree_error=worktree_error,
            patch_error=patch_error,
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
    store.write_latest_report(render_creation_cycle_markdown(report))
    if write_latest_json:
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
    if not hasattr(result, "exit_code"):
        raise CodexUnavailableError("Codex health check returned malformed result")
    exit_code = result.exit_code
    if exit_code == 0:
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
    env, redaction_secrets = _scrub_runner_env(os.environ)
    for command in commands:
        display_command = redact_text(command, secrets=redaction_secrets)
        argv, rejection_reason = _runner_argv(command)
        if rejection_reason is None:
            exit_code, stdout, stderr = _run_safe_command(
                argv=argv,
                workdir=workdir,
                env=env,
                redaction_secrets=redaction_secrets,
            )
        else:
            exit_code = _UNSAFE_COMMAND_EXIT_CODE
            stdout = ""
            stderr = redact_text(rejection_reason, secrets=redaction_secrets)
        if exit_code != 0:
            highest_exit_code = max(highest_exit_code, exit_code)
        sections.extend(
            [
                f"## `{display_command}`",
                "",
                f"Exit code: {exit_code}",
                "",
                "### stdout",
                "",
                "```",
                stdout,
                "```",
                "",
                "### stderr",
                "",
                "```",
                stderr,
                "```",
                "",
            ]
        )
    store.write_text(task_id, "runner.md", "\n".join(sections))
    return highest_exit_code


def _write_patch(*, workdir: Path, store: AutonomyStore, task_id: str) -> Path:
    try:
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
    finally:
        subprocess.run(
            ["git", "reset", "--mixed", "HEAD"],
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
    if not run_commands:
        reasons.append("verification_skipped")
    return reasons


def _next_actions(
    *,
    creation: CreationObject,
    rejected_reason_codes: list[str],
    runner_commands: list[str],
    run_commands: bool,
    promotion_error: str | None,
    worktree_error: str | None,
    patch_error: str | None,
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
    if "promotion_failed" in rejected_reason_codes:
        detail = "" if promotion_error is None else f": {promotion_error}"
        actions.append(f"Inspect promotion failure{detail}")
    if "worktree_creation_failed" in rejected_reason_codes:
        detail = "" if worktree_error is None else f": {worktree_error}"
        actions.append(f"Repair task worktree setup{detail}")
    if "patch_export_failed" in rejected_reason_codes:
        detail = "" if patch_error is None else f": {patch_error}"
        actions.append(f"Repair patch export{detail}")
    if "verification_skipped" in rejected_reason_codes:
        actions.append("Run verification commands before promotion.")
    return actions


def _runner_argv(command: str) -> tuple[list[str], str | None]:
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return [], f"Rejected unsafe verification command: {exc}"
    pytest_args = _pytest_args_from_runner_argv(argv)
    if pytest_args is not None:
        return pytest_args, None
    return [], f"Rejected unsafe verification command: {command}"


def _pytest_args_from_runner_argv(argv: list[str]) -> list[str] | None:
    if not argv:
        return None
    pytest_args: list[str] | None = None
    if argv[0] == "pytest":
        pytest_args = argv[1:]
    if len(argv) >= 3 and argv[0] == "uv" and argv[1:3] == ["run", "pytest"]:
        pytest_args = argv[3:]
    if len(argv) >= 3 and argv[0] == "python" and argv[1:3] == ["-m", "pytest"]:
        pytest_args = argv[3:]
    if pytest_args is None or _has_unsafe_pytest_args(pytest_args):
        return None
    return pytest_args


def _is_allowed_runner_argv(argv: list[str]) -> bool:
    return _pytest_args_from_runner_argv(argv) is not None


def _has_unsafe_pytest_args(args: list[str]) -> bool:
    if not any(_is_test_selector(arg) for arg in args):
        return True
    forbidden_prefixes = (
        "--basetemp",
        "--confcutdir",
        "--continue-on-collection-errors",
        "--cov",
        "--cov-report",
        "--fixtures",
        "--help",
        "--html",
        "--junitxml",
        "--override-ini",
        "--pyargs",
        "--rootdir",
        "--setup-plan",
        "--setup-show",
        "--trace-config",
        "--version",
    )
    forbidden_exact = {
        "--co",
        "--collect-only",
        "--fixtures-per-test",
        "--markers",
        "--trace",
        "-c",
        "-p",
        "-V",
        "-h",
    }
    for index, arg in enumerate(args):
        if (
            arg in forbidden_exact
            or arg.startswith(("-c", "-p"))
            or any(arg.startswith(prefix) for prefix in forbidden_prefixes)
        ):
            return True
        if index > 0 and args[index - 1] in forbidden_exact:
            return True
        if arg.startswith("-"):
            continue
        path = Path(arg)
        if path.is_absolute() or ".." in path.parts:
            return True
    return False


def _is_test_selector(arg: str) -> bool:
    if arg.startswith("-"):
        return False
    path = Path(arg.split("::", 1)[0])
    if path.is_absolute() or ".." in path.parts:
        return False
    return path.suffix == ".py" or path.parts[:1] == ("tests",)


def _run_safe_command(
    *,
    argv: list[str],
    workdir: Path,
    env: dict[str, str],
    redaction_secrets: list[str],
) -> tuple[int, str, str]:
    command = _docker_pytest_command(argv, workdir, env)
    return _run_sandboxed_command(
        command=command,
        workdir=workdir,
        env=_docker_runner_env(env),
        redaction_secrets=redaction_secrets,
    )


def _run_sandboxed_command(
    *,
    command: list[str],
    workdir: Path,
    env: dict[str, str],
    redaction_secrets: list[str],
) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=workdir,
            shell=False,
            text=True,
            capture_output=True,
            timeout=_RUNNER_TIMEOUT_SECONDS,
            env=env,
        )
    except FileNotFoundError as exc:
        return (
            127,
            "",
            redact_text(f"Docker is required for sandboxed verification: {exc}", secrets=redaction_secrets),
        )
    except subprocess.TimeoutExpired as exc:
        return (
            124,
            redact_text(_process_output(exc.stdout), secrets=redaction_secrets),
            redact_text(_process_output(exc.stderr), secrets=redaction_secrets),
        )
    return (
        int(result.returncode),
        redact_text(result.stdout, secrets=redaction_secrets),
        redact_text(result.stderr, secrets=redaction_secrets),
    )


def _docker_pytest_command(pytest_args: list[str], workdir: Path, env: dict[str, str]) -> list[str]:
    image = (
        env.get("CRYPTO_ALPHA_AGENT_RUNNER_IMAGE")
        or env.get("CRYPTO_ALPHA_AGENT_IMAGE")
        or _DEFAULT_RUNNER_IMAGE
    )
    mount_spec = f"type=bind,source={workdir},target=/workspace"
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--pids-limit",
        "128",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec",
        "--mount",
        mount_spec,
        "--workdir",
        "/workspace",
        "-e",
        "PYTHONPATH=/workspace/src",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
        "--entrypoint",
        "/app/.venv/bin/python",
        image,
        "-m",
        "pytest",
        "-o",
        "cache_dir=/tmp/pytest-cache",
        *pytest_args,
    ]


def _docker_runner_env(env: dict[str, str]) -> dict[str, str]:
    return {
        name: value
        for name, value in env.items()
        if name in {"PATH", "HOME"} or name.startswith("DOCKER_")
    }


def _process_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _subprocess_failure_text(exc: subprocess.SubprocessError) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        detail = str(exc)
        if exc.stderr:
            detail = f"{detail}; stderr={_process_output(exc.stderr)}"
        if exc.stdout:
            detail = f"{detail}; stdout={_process_output(exc.stdout)}"
        return detail
    return str(exc)


def _scrub_runner_env(env: os._Environ[str]) -> tuple[dict[str, str], list[str]]:
    clean: dict[str, str] = {}
    redaction_secrets: list[str] = []
    for name, value in env.items():
        if _should_scrub_runner_env_var(name):
            if value:
                redaction_secrets.append(value)
            continue
        clean[name] = value
        if value and _is_authenticated_proxy_url(name, value):
            redaction_secrets.append(value)
            redaction_secrets.extend(_proxy_credentials(name, value))
    return clean, redaction_secrets


_RUNNER_SECRET_ENV_MARKERS = (
    "API_KEY",
    "API_SECRET",
    "MNEMONIC",
    "PASSWORD",
    "PRIVATE_KEY",
    "SECRET",
    "SECRET_KEY",
    "SEED_PHRASE",
    "TOKEN",
)
_RUNNER_TRADING_ENV_MARKERS = (
    "ALCHEMY",
    "BINANCE",
    "BITFINEX",
    "BITGET",
    "BITMEX",
    "BROKER",
    "BYBIT",
    "CCXT",
    "COINBASE",
    "DERIBIT",
    "EXCHANGE",
    "FTX",
    "KRAKEN",
    "KUCOIN",
    "OKX",
    "TRADING",
    "WALLET",
    "WEB3",
)


def _should_scrub_runner_env_var(name: str) -> bool:
    upper_name = name.upper()
    return any(marker in upper_name for marker in _RUNNER_TRADING_ENV_MARKERS) or any(
        marker in upper_name for marker in _RUNNER_SECRET_ENV_MARKERS
    )


_RUNNER_SAFE_PROXY_ENV_NAMES = {
    "ALL_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "all_proxy",
    "http_proxy",
    "https_proxy",
    "no_proxy",
}


def _is_authenticated_proxy_url(name: str, value: str) -> bool:
    if not _is_runner_proxy_env_name(name):
        return False
    parsed = urlsplit(value)
    return bool(parsed.scheme and parsed.hostname and (parsed.username or parsed.password))


def _proxy_credentials(name: str, value: str) -> list[str]:
    if not _is_runner_proxy_env_name(name):
        return []
    parsed = urlsplit(value)
    return [secret for secret in (parsed.username, parsed.password) if secret]


def _is_runner_proxy_env_name(name: str) -> bool:
    return name in _RUNNER_SAFE_PROXY_ENV_NAMES or name.upper() in _RUNNER_SAFE_PROXY_ENV_NAMES


def _llm_metadata(llm_runtime: Any) -> Any:
    metadata = getattr(llm_runtime, "metadata", None)
    if not callable(metadata):
        return None
    return metadata()
