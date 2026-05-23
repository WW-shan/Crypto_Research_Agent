from __future__ import annotations

import json
import subprocess

from crypto_alpha_agent.security.secret_scan import (
    EmptyStagedDiffError,
    collect_sensitive_environment_values,
    scan_git_staged_diff,
    scan_paths,
    scan_text,
)


def test_secret_scan_reports_configured_secrets_without_exposing_values() -> None:
    secret = "cfg-test-secret-value-123456"
    base_url = "https://provider.example/root"

    findings = scan_text(
        f"Authorization: Bearer {secret} at {base_url}",
        surface="stdout",
        secret_values={"api_key": secret, "base_url": base_url},
    )

    public = json.dumps([finding.to_public_dict() for finding in findings], sort_keys=True)
    assert findings
    assert "stdout" in public
    assert secret not in public
    assert base_url not in public
    assert "Bearer" not in public
    assert "Authorization" not in public


def test_secret_scan_covers_memory_reports_artifacts_manifests_and_staged_diff(tmp_path) -> None:
    secret = "cfg-test-secret-value-abcdef"
    base_url = "https://provider.example/root"
    configured = {"OPENAI_API_KEY": secret, "OPENAI_BASE_URL": base_url}
    memory_path = tmp_path / "memory.jsonl"
    markdown_report = tmp_path / "daily.md"
    json_artifact = tmp_path / "artifact.json"
    run_manifest = tmp_path / "run-manifest.json"
    for path in (memory_path, markdown_report, json_artifact, run_manifest):
        path.write_text(f"leaked {secret} via {base_url}\n", encoding="utf-8")

    path_findings = scan_paths(
        [memory_path, markdown_report, json_artifact, run_manifest],
        secret_values=configured,
    )
    public_paths = json.dumps([finding.to_public_dict() for finding in path_findings], sort_keys=True)

    assert {finding.surface for finding in path_findings} == {
        str(memory_path),
        str(markdown_report),
        str(json_artifact),
        str(run_manifest),
    }
    assert secret not in public_paths
    assert base_url not in public_paths

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    staged_file = repo / "staged.txt"
    staged_file.write_text(f"staged {secret}\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged.txt"], cwd=repo, check=True, capture_output=True, text=True)

    staged_findings = scan_git_staged_diff(repo_path=repo, secret_values=configured)
    public_staged = json.dumps([finding.to_public_dict() for finding in staged_findings], sort_keys=True)

    assert any(finding.surface == "staged_diff" for finding in staged_findings)
    assert secret not in public_staged
    assert base_url not in public_staged


def test_secret_scan_redacts_secret_values_from_public_labels_and_surfaces(tmp_path) -> None:
    secret = "cfg-test-secret-value-in-path"
    secret_dir = tmp_path / secret
    secret_dir.mkdir()
    report_path = secret_dir / "daily.md"
    report_path.write_text(f"leaked {secret}\n", encoding="utf-8")

    findings = scan_paths([report_path], secret_values={secret: secret})
    public = json.dumps([finding.to_public_dict() for finding in findings], sort_keys=True)

    assert findings
    assert secret not in public
    assert "<redacted>" in public


def test_collect_sensitive_environment_values_filters_to_secret_like_names(tmp_path) -> None:
    env_file = tmp_path / ".env"
    proxy_value = "http://127.0.0.1:" + "10808"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_TYPE=responses",
                "OPENAI_API_KEY=cfg-test-secret-value-abcdef",
                "OPENAI_BASE_URL=https://provider.example/root",
                f"HTTP_PROXY={proxy_value}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    values = collect_sensitive_environment_values(
        env_file=env_file,
        env={"OPENAI_API_KEY": "cfg-shell-secret-value-abcdef"},
    )

    assert values["OPENAI_API_KEY"] == "cfg-shell-secret-value-abcdef"
    assert values["OPENAI_BASE_URL"] == "https://provider.example/root"
    assert values["HTTP_PROXY"] == proxy_value
    assert "OPENAI_API_TYPE" not in values


def test_secret_scan_staged_diff_can_fail_on_empty_diff_with_untracked_files(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "untracked.txt").write_text("local artifact\n", encoding="utf-8")

    try:
        scan_git_staged_diff(repo_path=repo, fail_on_empty_with_untracked=True)
    except EmptyStagedDiffError as exc:
        assert "untracked files exist" in str(exc)
    else:
        raise AssertionError("empty staged diff with untracked files should fail")


def test_secret_scan_catches_realistic_staged_secret_after_stage(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    staged_file = repo / "staged.py"
    fake_key = "sk-" + "liveabcdefghijklmnopqrstuvwxyz"
    staged_file.write_text(f'API_KEY = "{fake_key}"\n', encoding="utf-8")
    subprocess.run(["git", "add", "staged.py"], cwd=repo, check=True, capture_output=True, text=True)

    findings = scan_git_staged_diff(repo_path=repo, fail_on_empty_with_untracked=True)

    assert any(finding.surface == "staged_diff" for finding in findings)
