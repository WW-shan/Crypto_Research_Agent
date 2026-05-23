from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


_API_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
_GITHUB_TOKEN_PATTERN = re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")
_PRIVATE_KEY_BLOCK_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}", re.IGNORECASE)
_AUTHORIZATION_PATTERN = re.compile(
    r"\bAuthorization\b\s*[:=]\s*(?:Bearer\s+)?[A-Za-z0-9._~+/-]{12,}",
    re.IGNORECASE,
)
_MNEMONIC_VALUE_PATTERN = re.compile(
    r"\b(?:seed phrase|mnemonic)\b\s*[:=]\s*(?:[a-z]{3,12}\s+){2,}[a-z]{3,12}",
    re.IGNORECASE,
)
_SENSITIVE_ENV_NAME_PATTERN = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|BASE_URL|PROXY|PRIVATE|MNEMONIC|SEED)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SecretScanFinding:
    surface: str
    label: str
    pattern: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "surface": self.surface,
            "label": self.label,
            "pattern": self.pattern,
        }


class EmptyStagedDiffError(RuntimeError):
    """Raised when a staged scan would cover nothing while untracked files exist."""


def collect_sensitive_environment_values(
    *,
    env_file: str | Path | None = Path(".env"),
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file is not None:
        path = Path(env_file)
        if path.exists():
            values.update(_parse_env_file(path))
    source_env = env if env is not None else os.environ
    for key, value in source_env.items():
        if value:
            values[key] = value
    return {
        key: value
        for key, value in values.items()
        if _SENSITIVE_ENV_NAME_PATTERN.search(key) and len(value) >= 8
    }


def scan_text(
    text: object,
    *,
    surface: str,
    secret_values: Mapping[str, str] | Iterable[str] = (),
) -> list[SecretScanFinding]:
    value = str(text)
    public_surface = _redact_public_surface(surface, secret_values)
    findings: list[SecretScanFinding] = []
    _append_if_match(
        findings,
        public_surface,
        "api_key_like",
        "api_key_pattern",
        _API_KEY_PATTERN,
        value,
    )
    _append_if_match(
        findings,
        public_surface,
        "github_token_like",
        "github_token_pattern",
        _GITHUB_TOKEN_PATTERN,
        value,
    )
    _append_if_match(
        findings,
        public_surface,
        "private_key_block",
        "private_key_block_pattern",
        _PRIVATE_KEY_BLOCK_PATTERN,
        value,
    )
    _append_if_match(
        findings,
        public_surface,
        "bearer_token",
        "bearer_pattern",
        _BEARER_PATTERN,
        value,
    )
    _append_if_match(
        findings,
        public_surface,
        "authorization_header",
        "authorization_pattern",
        _AUTHORIZATION_PATTERN,
        value,
    )
    _append_if_match(
        findings,
        public_surface,
        "mnemonic_or_seed_value",
        "mnemonic_value_pattern",
        _MNEMONIC_VALUE_PATTERN,
        value,
    )
    for label, secret in _iter_secret_values(secret_values):
        if secret and len(secret) >= 8 and secret in value:
            findings.append(
                SecretScanFinding(
                    surface=public_surface,
                    label=_redact_public_surface(label, secret_values),
                    pattern="configured_secret_value",
                )
            )
    return _deduplicate_findings(findings)


def scan_paths(
    paths: Iterable[str | Path],
    *,
    secret_values: Mapping[str, str] | Iterable[str] = (),
) -> list[SecretScanFinding]:
    findings: list[SecretScanFinding] = []
    for path_like in paths:
        path = Path(path_like)
        if not path.exists() or not path.is_file():
            continue
        findings.extend(
            scan_text(
                path.read_text(encoding="utf-8", errors="replace"),
                surface=str(path),
                secret_values=secret_values,
            )
        )
    return findings


def scan_git_staged_diff(
    *,
    repo_path: str | Path = Path("."),
    secret_values: Mapping[str, str] | Iterable[str] = (),
    fail_on_empty_with_untracked: bool = False,
) -> list[SecretScanFinding]:
    repo = Path(repo_path)
    result = subprocess.run(
        ["git", "diff", "--cached", "--no-ext-diff", "--unified=0"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    if fail_on_empty_with_untracked and not result.stdout.strip():
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        if untracked.stdout.strip():
            raise EmptyStagedDiffError(
                "staged diff is empty while untracked files exist; stage intended files first"
            )
    return scan_text(result.stdout, surface="staged_diff", secret_values=secret_values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan local text surfaces for secret leaks.")
    parser.add_argument("--staged", action="store_true", help="Scan git staged diff.")
    parser.add_argument(
        "--fail-on-empty-with-untracked",
        action="store_true",
        help="Fail if --staged scans an empty diff while untracked files exist.",
    )
    parser.add_argument("--path", action="append", default=[], help="Path to scan. May be repeated.")
    parser.add_argument("--repo", type=Path, default=Path("."), help="Repository path for staged scan.")
    args = parser.parse_args(argv)

    secret_values = collect_sensitive_environment_values(env_file=args.repo / ".env")
    findings: list[SecretScanFinding] = []
    try:
        if args.staged:
            findings.extend(
                scan_git_staged_diff(
                    repo_path=args.repo,
                    secret_values=secret_values,
                    fail_on_empty_with_untracked=args.fail_on_empty_with_untracked,
                )
            )
        if args.path:
            findings.extend(scan_paths(args.path, secret_values=secret_values))
    except EmptyStagedDiffError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps([finding.to_public_dict() for finding in findings], sort_keys=True))
    return 1 if findings else 0


def _append_if_match(
    findings: list[SecretScanFinding],
    surface: str,
    label: str,
    pattern_label: str,
    pattern: re.Pattern[str],
    value: str,
) -> None:
    if pattern.search(value):
        findings.append(
            SecretScanFinding(
                surface=surface,
                label=label,
                pattern=pattern_label,
            )
        )


def _iter_secret_values(
    secret_values: Mapping[str, str] | Iterable[str],
) -> Iterable[tuple[str, str]]:
    if isinstance(secret_values, Mapping):
        for label, value in secret_values.items():
            yield str(label), str(value)
        return
    for index, value in enumerate(secret_values):
        yield f"configured_secret_{index}", str(value)


def _deduplicate_findings(findings: list[SecretScanFinding]) -> list[SecretScanFinding]:
    unique: dict[tuple[str, str, str], SecretScanFinding] = {}
    for finding in findings:
        unique[(finding.surface, finding.label, finding.pattern)] = finding
    return list(unique.values())


def _redact_public_surface(
    surface: str,
    secret_values: Mapping[str, str] | Iterable[str],
) -> str:
    redacted = str(surface)
    for _label, secret in sorted(
        _iter_secret_values(secret_values),
        key=lambda item: len(item[1]),
        reverse=True,
    ):
        if secret and len(secret) >= 8:
            redacted = redacted.replace(secret, "<redacted>")
    for pattern in (
        _API_KEY_PATTERN,
        _GITHUB_TOKEN_PATTERN,
        _PRIVATE_KEY_BLOCK_PATTERN,
        _BEARER_PATTERN,
        _AUTHORIZATION_PATTERN,
        _MNEMONIC_VALUE_PATTERN,
    ):
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        parsed[key] = _unquote_env_value(value.strip())
    return parsed


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


if __name__ == "__main__":
    sys.exit(main())
