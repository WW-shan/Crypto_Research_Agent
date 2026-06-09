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
    "vps": ROOT / "docs" / "vps-deployment.md",
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
            "historical-bootstrap",
            "historical bootstrap report",
            "future out-of-sample",
            "30/60/90 evidence targets",
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
            "governance-report",
            "ai-research-memo",
            "expansion-prep-report",
            "replay",
            "cron",
            "systemd",
            "docker compose",
            "crypto-alpha-daily.timer",
            "var/reports/iteration/latest.json",
            "failed marker",
            "auto_executes_changes=false",
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
            "funding_open_interest_crowding",
            "volatility_compression_expansion_watchlist",
            "blocked_by_missing_data",
            "blocked_by_unqualified_source",
            "cost_model_mode",
            "pessimistic",
            "min_notional_exceeds_max_notional",
            "stale_signal",
            "pre_cost_only_profitable",
            "missed_fill_assumed",
            "partial_fill",
            "strategy-template proposal",
            "selected validator",
            "required data fields",
            "weekly family scoreboard",
            "profit review",
            "stopped-family ledger",
            "paper-only portfolio selector",
            "monthly owner review",
            "binance_usdm_global_long_short_account_ratio",
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
            "evidence-universe-lab",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "candidate-state.jsonl"),
            "--symbol",
            "BTC/USDT",
            "--timeframe",
            "1h",
            "--start-year",
            "2026",
            "--start-month",
            "1",
            "--end-year",
            "2026",
            "--end-month",
            "5",
            "--out-dir",
            str(tmp_path / "evidence-universe-lab"),
            "--json-out",
            str(tmp_path / "evidence-universe-lab.json"),
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
            "governance-report",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(tmp_path / "governance.md"),
            "--current-capital-usd",
            "300",
        ],
        [
            "historical-bootstrap",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(tmp_path / "phase7.md"),
            "--json-out",
            str(tmp_path / "phase7.json"),
            "--manifest-out",
            str(tmp_path / "phase7.manifest.json"),
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
            "--bootstrap-window",
            "2026-03-01/2026-04-01",
            "--bootstrap-window",
            "2026-04-01/2026-05-01",
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
            "ai-research-memo",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(tmp_path / "ai-memo.md"),
            "--current-capital-usd",
            "300",
        ],
        [
            "iteration-cycle",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(tmp_path / "iteration-cycle.md"),
            "--json-out",
            str(tmp_path / "iteration-cycle.json"),
            "--current-capital-usd",
            "300",
            "--max-candidates",
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
            "historical-bootstrap",
            "historical bootstrap report",
            "future out-of-sample",
            "30/60/90 evidence targets",
            "paper-sim-loop",
            "funding_open_interest_crowding",
            "volatility_compression_expansion_watchlist",
            "evidence-report --daily",
            "evidence-report --weekly",
            "plan-experiments",
            "ai-research-memo",
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
            "evidence-universe-lab",
            "weekly sequence",
            "source qualification workflow",
            "source-probe",
            "source coverage matrix",
            "query catalog",
            "historical bootstrap workflow",
            "historical-bootstrap",
            "30/60/90 evidence targets",
            "future out-of-sample",
            "productionresearchsource",
            "binance public data",
            "ccxt",
            "dexscreener",
            "defillama",
            "dune",
            "the graph",
            "paper simulation workflow",
            "funding_open_interest_crowding",
            "volatility_compression_expansion_watchlist",
            "daily report workflow",
            "weekly report workflow",
            "ai research memo workflow",
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


def test_llm_native_runtime_contract_is_documented() -> None:
    runbook = _read(DOC_PATHS["runbook"])
    roadmap = _read(DOC_PATHS["roadmap"])
    spec_path = ROOT / "docs" / "superpowers" / "specs" / "2026-05-24-llm-native-runtime-design.md"

    assert "llm-health-check" in runbook
    assert "--offline-only" not in runbook
    assert "LLM-Native Runtime" in roadmap
    assert spec_path.exists()


def test_project_reality_audit_documents_phase_status_and_owner_target_gaps() -> None:
    audit_path = ROOT / "docs" / "goals" / "project-reality-audit-2026-05-29.md"
    state_path = ROOT / "docs" / "goals" / "project-completion-state.md"

    audit = _read(audit_path).lower()
    state = _read(state_path).lower()
    roadmap = _read(DOC_PATHS["roadmap"]).lower()

    _assert_contains(
        audit,
        [
            "complete runtime flow",
            "phase 0",
            "phase 13",
            "llm-native runtime",
            "really implemented",
            "remaining gaps",
            "autonomous code-writing loop",
            "autonomous new data source discovery",
            "auto-iteration loop",
            "30/60/90 out-of-sample",
            "no live order routing",
            "deterministic modules remain calculators and constraints",
        ],
    )
    _assert_contains(
        state,
        [
            "reality audit",
            "owner autonomy target",
            "autonomous code-writing loop",
            "new data source discovery",
        ],
    )
    _assert_contains(
        roadmap,
        [
            "owner autonomy target reality check",
            "not yet implemented",
            "autonomous code-writing loop",
        ],
    )


def test_evidence_universe_path_map_is_persisted() -> None:
    roadmap = _normalized(DOC_PATHS["roadmap"])
    state = _normalized(ROOT / "docs" / "goals" / "project-completion-state.md")

    required_terms = [
        "Evidence Universe Expansion and Multi-Hypothesis Feasibility Lab",
        "source and universe expansion",
        "data-quality and lookahead-risk gate",
        "candidate screen registry",
        "multi-hypothesis feasibility lab",
        "event-driven backtest readiness and cost realism",
        "paper queue only after feasibility plus backtest pass",
        "30/60/90 paper observation tracking",
        "governance state machine and stopped/redesign memory",
        "automated daily collection and ranking reports",
        "backtest_passed",
        "paper_collecting",
        "lookahead",
        "cost sensitivity",
        "live execution remains blocked",
    ]
    _assert_contains(roadmap, required_terms)
    _assert_contains(state, required_terms)


def test_phase14_iteration_cycle_contract_is_documented() -> None:
    phase_report_path = (
        ROOT
        / "docs"
        / "goals"
        / "phase-reports"
        / "2026-05-29-phase-14-llm-native-autonomous-iteration-controller-completion-report.md"
    )
    state_path = ROOT / "docs" / "goals" / "project-completion-state.md"

    assert phase_report_path.exists()
    docs = "\n".join(
        [
            _combined_docs(),
            _normalized(state_path),
            _normalized(phase_report_path),
        ]
    )

    _assert_contains(
        docs,
        [
            "iteration-cycle",
            "IterationCandidate",
            "autonomous code-writing loop remains proposal-only",
            "autonomous new data source discovery remains probe-gated",
            "auto_executes_changes=false",
        ],
    )


def test_vps_docker_operations_contract_is_documented() -> None:
    vps = _read(DOC_PATHS["vps"])
    docs = "\n".join([_combined_docs(), vps.lower()])

    _assert_contains(
        docs,
        [
            "Docker Compose",
            "systemd",
            "crypto-alpha-daily.timer",
            "crypto-alpha-weekly.timer",
            "crypto-alpha-monthly.timer",
            "crypto-alpha-backup.timer",
            "crypto-alpha-creation.timer",
            "var/research.sqlite",
            "var/memory/evidence.jsonl",
            "var/reports/daily/latest.md",
            "var/reports/iteration/latest.json",
            "var/reports/creation/latest.md",
            "var/reports/creation/latest.json",
            "var/autonomy/backlog.jsonl",
            "var/autonomy/active-worktree",
            "ops/creation-cycle.sh",
            "creation-cycle",
            "Codex must be available or the creation cycle exits nonzero",
            "pytest ...",
            "python -m pytest ...",
            "uv run pytest ...",
            "--network none",
            "CRYPTO_ALPHA_AGENT_RUNNER_IMAGE",
            "var/run-manifests/latest.json",
            "failed marker",
            ".env stays outside git",
            "llm-health-check",
            "no live order routing",
            "auto_executes_changes=false",
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
            "phase 7: final evidence campaign after factory buildout",
            "historical bootstrap report",
            "future out-of-sample paper observations",
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
