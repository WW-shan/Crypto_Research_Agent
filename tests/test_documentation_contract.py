from __future__ import annotations

import re
from pathlib import Path

from crypto_alpha_agent.cli import build_parser


ROOT = Path(__file__).resolve().parents[1]


DOC_PATHS = {
    "readme": ROOT / "README.md",
    "runbook": ROOT / "docs" / "runbook.md",
    "roadmap": ROOT / "docs" / "roadmap.md",
    "rollout": ROOT / "docs" / "rollout-gates.md",
    "tiny_live": ROOT / "docs" / "tiny-live-readiness.md",
    "source_coverage": ROOT / "docs" / "source-coverage-matrix.md",
    "source_query_catalog": ROOT / "docs" / "source-query-catalog.md",
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
            "source-probe",
            "source coverage matrix",
            "query catalog",
            "reachableviaproxy",
            "productionresearchsource",
            "plan-experiments",
            "rollout-review",
            "ingest",
            "paper-sim-loop",
            "evidence-report",
            "expansion-prep-report",
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


def test_docs_do_not_include_local_paths_or_forbidden_live_flags() -> None:
    docs = _combined_docs()
    forbidden_patterns = {
        "local user path": r"/users/[^/\s]+/",
        "aws access key": r"akia[0-9a-z]{16}",
        "openai api key": r"sk-[0-9a-z_-]{20,}",
        "github token": r"ghp_[0-9a-z]{20,}",
        "private key block": r"begin [a-z ]*private key",
        "live enabled true": r"live_execution_enabled\s*[:=]\s*true",
        "real capital true": r"uses_real_capital\s*[:=]\s*true",
        "live routing true": r"live_order_routing\s*[:=]\s*true",
    }

    violations = [
        label
        for label, pattern in forbidden_patterns.items()
        if re.search(pattern, docs, flags=re.IGNORECASE)
    ]
    assert violations == []


def test_each_operator_doc_keeps_the_no_live_boundary() -> None:
    required_terms = {
        "readme": ["no live execution", "no live order routing"],
        "runbook": ["no wallet keys", "no live order routing", "no live execution"],
        "roadmap": ["no wallet-key access", "no order routing", "no live capital"],
        "rollout": ["does not place orders", "no live execution"],
        "tiny_live": ["does not execute live trades", "live_execution_enabled", "false"],
    }

    for doc_name, terms in required_terms.items():
        _assert_contains(_normalized(DOC_PATHS[doc_name]), terms)


def test_documented_representative_cli_examples_parse(tmp_path) -> None:
    db_path = tmp_path / "research.sqlite"
    db_path.write_text("", encoding="utf-8")
    event_path = tmp_path / "research-observability.jsonl"
    event_path.write_text("", encoding="utf-8")
    parser = build_parser()

    commands = [
        ["source-probe", "--list-targets"],
        [
            "source-probe",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--target",
            "binance_usdm_open_interest_history",
            "--route",
            "direct",
        ],
        ["ingest", "--offline-check", "--db", str(tmp_path / "research.sqlite")],
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "ccxt",
            "--allow-network",
            "--ccxt-feed",
            "ohlcv",
            "--exchange",
            "binance",
            "--symbol",
            "BTC/USDT",
            "--timeframe",
            "1h",
            "--limit",
            "200",
        ],
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "dexscreener",
            "--allow-network",
            "--query",
            "ETH USDC",
        ],
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "defillama",
            "--allow-network",
            "--min-tvl-usd",
            "10000",
        ],
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "dune",
            "--allow-network",
            "--dune-query-id",
            "123456",
            "--dune-api-key",
            "[REDACTED]",
            "--dune-param",
            "chain=ethereum",
        ],
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "thegraph",
            "--allow-network",
            "--subgraph-url",
            "https://api.thegraph.com/subgraphs/name/example/example",
            "--graph-query",
            "{ pools(first: 5) { id } }",
        ],
        [
            "evidence-run",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--report-out",
            str(tmp_path / "daily.md"),
            "--weekly-report-out",
            str(tmp_path / "weekly.md"),
            "--current-capital-usd",
            "300",
            "--allow-network",
            "--ccxt-exchange",
            "binance",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
            "--limit",
            "200",
            "--strategy-family",
            "funding_extremity_price_confirmation",
        ],
        [
            "paper-sim-loop",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
            "--memory",
            str(tmp_path / "memory.jsonl"),
        ],
        [
            "evidence-report",
            "--daily",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(tmp_path / "daily.md"),
        ],
        [
            "evidence-report",
            "--weekly",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(tmp_path / "weekly.md"),
        ],
        [
            "expansion-prep-report",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(tmp_path / "phase5.md"),
            "--current-capital-usd",
            "300",
        ],
        [
            "plan-experiments",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--max-proposals",
            "3",
        ],
        [
            "rollout-review",
            "--db",
            str(db_path),
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--artifact-out",
            str(tmp_path / "rollout.json"),
            "--evidence-package-out",
            str(tmp_path / "evidence-package.json"),
        ],
        ["replay", "--events", str(event_path), "--date", "2026-05-18"],
    ]

    for command in commands:
        parser.parse_args(command)


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
            "source-probe",
            "open-interest-history",
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
            "source qualification workflow",
            "source-probe",
            "source coverage matrix",
            "query catalog",
            "productionresearchsource",
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
