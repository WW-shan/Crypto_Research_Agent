from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


DOC_PATHS = {
    "readme": ROOT / "README.md",
    "runbook": ROOT / "docs" / "runbook.md",
    "roadmap": ROOT / "docs" / "roadmap.md",
    "rollout": ROOT / "docs" / "rollout-gates.md",
    "tiny_live": ROOT / "docs" / "tiny-live-readiness.md",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    return _read(path).lower()


def _combined_docs() -> str:
    return "\n".join(_normalized(path) for path in DOC_PATHS.values())


def _assert_contains(text: str, terms: list[str]) -> None:
    missing = [term for term in terms if term.lower() not in text]
    assert not missing, f"Missing documentation contract terms: {missing}"


def test_operator_workflow_contract_is_documented_across_docs() -> None:
    docs = _combined_docs()

    _assert_contains(
        docs,
        [
            "evidence-run",
            "plan-experiments",
            "rollout-review",
            "ingest",
            "paper-sim-loop",
            "evidence-report",
            "replay",
            "cron",
            "systemd",
            "log paths",
            "run locking",
            "idempotency",
            "failure notification",
            "artifact retention",
            "no wallet keys",
            "no live order routing",
            "ordinary public APIs",
            "few hundred USD",
            "30 paper observations",
            "evidence package preservation",
        ],
    )


def test_readme_documents_safe_operator_examples() -> None:
    readme = _normalized(DOC_PATHS["readme"])

    _assert_contains(
        readme,
        [
            "## setup",
            "uv sync --extra dev",
            "evidence-run",
            "--allow-network",
            "binance-public",
            "ccxt",
            "dexscreener",
            "defillama",
            "dune",
            "dune_api_key",
            "local operator config",
            "thegraph",
            "paper-sim-loop",
            "evidence-report --daily",
            "evidence-report --weekly",
            "plan-experiments",
            "rollout-review",
            "--artifact-out",
            "--evidence-package-out",
            "replay",
            "no live execution",
            "no live order routing",
        ],
    )


def test_runbook_documents_complete_operator_handoff() -> None:
    runbook = _normalized(DOC_PATHS["runbook"])

    _assert_contains(
        runbook,
        [
            "daily sequence",
            "weekly sequence",
            "binance public data",
            "ccxt",
            "dexscreener",
            "defillama",
            "dune",
            "the graph",
            "paper simulation workflow",
            "daily report workflow",
            "weekly report workflow",
            "replay/recovery workflow",
            "what to inspect",
            "failure reasons and meanings",
            "how to stop a degraded family",
            "evidence preservation",
            "external operator-controlled scheduling",
            "without making the agent an always-on daemon",
            "cron",
            "systemd",
            "one-run-at-a-time locking",
            "stdout",
            "stderr",
            "nonzero-exit notification",
            "daily markdown/json",
            "weekly reports",
            "memory",
            "sqlite",
            "rollout artifacts",
            "retention",
        ],
    )


def test_roadmap_rollout_and_tiny_live_contracts_are_current() -> None:
    roadmap = _normalized(DOC_PATHS["roadmap"])
    rollout = _normalized(DOC_PATHS["rollout"])
    tiny_live = _normalized(DOC_PATHS["tiny_live"])

    _assert_contains(
        roadmap,
        [
            "phase 2 strategy validation expanded",
            "phase 4 evidence accumulation operational",
            "external scheduler remains operator-controlled",
            "complete scheduling handoff",
            "live execution until future charter revision",
        ],
    )
    for doc in (rollout, tiny_live):
        _assert_contains(
            doc,
            [
                "rollout-review",
                "evidence package preservation",
                "max_observed_loss_usd",
                "30 observations",
                "no live execution",
            ],
        )
