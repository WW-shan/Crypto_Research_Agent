# Autonomous Crypto Alpha Research Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a discovery-first LangGraph system that finds crypto alpha opportunities, turns them into testable hypotheses, validates them with backtests/paper trading, and only then allows tightly gated live execution.

**Architecture:** The system stays open on discovery and strict on execution. Every candidate opportunity flows through normalization, feasibility scoring, risk gating, reflection, and memory before any trade proposal is allowed. LangGraph owns orchestration, checkpoints, and human approval nodes; a structured event log powers long-term memory and regression analysis.

**Tech Stack:** Python 3.12, uv, LangGraph, LangChain, Pydantic, ccxt, web3.py, requests/gql, Dune API, The Graph, DefiLlama, vectorbt, backtrader, SQLite first, optional Postgres/vector store later, pytest, ruff, mypy, Docker.

---

## File Map

- `pyproject.toml`: dependency and tool configuration.
- `README.md`: setup, workflow, and operator instructions.
- `.env.example`: required API keys and runtime flags.
- `src/crypto_alpha_agent/config.py`: config models and env loading.
- `src/crypto_alpha_agent/state.py`: LangGraph state schema and event models.
- `src/crypto_alpha_agent/orchestrator.py`: graph assembly and routing.
- `src/crypto_alpha_agent/agents/*.py`: scanner, researcher, coder, validator, reflector, risk guardian, memory manager.
- `src/crypto_alpha_agent/tools/*.py`: CEX, chain, Dune, The Graph, DefiLlama, backtest, storage adapters.
- `src/crypto_alpha_agent/memory/*.py`: event store, vector memory, retrieval helpers.
- `src/crypto_alpha_agent/risk/*.py`: scoring rules, budget guardrails, execution policy.
- `src/crypto_alpha_agent/backtest/*.py`: vectorbt/backtrader wrappers and result normalization.
- `src/crypto_alpha_agent/cli.py`: daily run, replay, and report commands.
- `tests/**/*.py`: unit, integration, and graph flow tests.
- `configs/default.yaml`: runtime defaults and budgets.
- `docs/architecture.md`: operator-facing architecture summary.
- `docs/runbook.md`: start/stop, recovery, and incident handling.

---

## Phase 0: Repository Bootstrap

### Task 1: Create the project skeleton and test harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/crypto_alpha_agent/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Write the failing smoke test**

```python
def test_package_imports():
    import crypto_alpha_agent
    assert crypto_alpha_agent.__name__ == "crypto_alpha_agent"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `pytest tests/test_smoke.py -q`
Expected: import error because the package does not exist yet.

- [ ] **Step 3: Add the minimal package and config**

Create the package directory, add `__init__.py`, and define the first dependency set in `pyproject.toml` with `langgraph`, `pydantic`, `pytest`, `ruff`, `ccxt`, `web3`, `requests`, `vectorbt`, and `backtrader`.

- [ ] **Step 4: Run the test and confirm it passes**

Run: `pytest tests/test_smoke.py -q`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src tests README.md .env.example
git commit -m "chore: bootstrap crypto alpha research agent"
```

**Exit criteria:** The package imports, tests run, and the dependency set is pinned.

---

## Phase 1: Canonical Data Model and Config

### Task 2: Define the opportunity schema and run configuration

**Files:**
- Create: `src/crypto_alpha_agent/config.py`
- Create: `src/crypto_alpha_agent/state.py`
- Create: `tests/test_state_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
def test_opportunity_event_fields():
    from crypto_alpha_agent.state import OpportunityEvent

    event = OpportunityEvent(
        source="dune",
        venue="binance",
        asset="BTC",
        edge_type="funding_rate",
        capital_required_usd=100.0,
        speed_dependency="low",
        rpc_dependency="none",
        expected_net_pnl_usd=12.5,
        confidence=0.74,
    )

    assert event.edge_type == "funding_rate"
    assert event.confidence > 0.7
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `pytest tests/test_state_models.py -q`
Expected: model import or validation failure.

- [ ] **Step 3: Implement the minimal Pydantic models**

Define:
- `OpportunityEvent`
- `ResearchState`
- `ExecutionProposal`
- `AgentDecision`
- `RuntimeConfig`

Include fields for:
- source, venue, asset, chain, protocol
- edge type, evidence, confidence, freshness
- capital required, fee estimate, gas estimate, slippage estimate
- speed dependency, rpc dependency, inventory dependency
- expected gross pnl, expected net pnl, downside, time to expiry
- action mode: research only / paper / gated live

- [ ] **Step 4: Run the test and confirm it passes**

Run: `pytest tests/test_state_models.py -q`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/config.py src/crypto_alpha_agent/state.py tests/test_state_models.py
git commit -m "feat: define canonical research state"
```

**Exit criteria:** The entire system speaks one opportunity schema.

---

## Phase 2: Data Ingestion and Normalization

### Task 3: Add the market/data connectors

**Files:**
- Create: `src/crypto_alpha_agent/tools/cex.py`
- Create: `src/crypto_alpha_agent/tools/dune.py`
- Create: `src/crypto_alpha_agent/tools/thegraph.py`
- Create: `src/crypto_alpha_agent/tools/defillama.py`
- Create: `tests/test_tools_normalization.py`

- [ ] **Step 1: Write failing normalization tests**

```python
def test_cex_snapshot_normalization():
    from crypto_alpha_agent.tools.cex import normalize_cex_snapshot

    raw = {"binance": {"BTC/USDT": {"bid": 65000, "ask": 65010}}}
    snap = normalize_cex_snapshot(raw)

    assert snap.best_bid == 65000
    assert snap.best_ask == 65010
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest tests/test_tools_normalization.py -q`
Expected: missing functions/import errors.

- [ ] **Step 3: Implement thin adapters only**

Keep each adapter one responsibility:
- CEX snapshots from `ccxt`
- Dune SQL execution
- The Graph subgraph queries
- DefiLlama protocol and yield data

Normalize every result into `OpportunityEvent`-compatible structures and preserve raw evidence blobs.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `pytest tests/test_tools_normalization.py -q`
Expected: `pass`.

- [ ] **Step 5: Commit**

```bash
git add src/crypto_alpha_agent/tools tests
git commit -m "feat: add normalized market data adapters"
```

**Exit criteria:** Every data source returns the same canonical shape.

### Task 4: Add rate limiting, retries, and source health

**Files:**
- Create: `src/crypto_alpha_agent/tools/http.py`
- Modify: `src/crypto_alpha_agent/tools/*.py`
- Create: `tests/test_tool_retries.py`

- [ ] **Step 1: Write a retry test**
- [ ] **Step 2: Confirm failures on first request**
- [ ] **Step 3: Add bounded retry + backoff + timeout**
- [ ] **Step 4: Confirm retry passes and health metrics are emitted**
- [ ] **Step 5: Commit**

**Exit criteria:** No connector can silently hang or DOS the API budget.

---

## Phase 3: LangGraph Orchestration

### Task 5: Build the graph state machine

**Files:**
- Create: `src/crypto_alpha_agent/orchestrator.py`
- Create: `tests/test_graph_routing.py`

- [ ] **Step 1: Write a graph routing test**

```python
def test_graph_routes_from_scan_to_hypothesis():
    from crypto_alpha_agent.orchestrator import build_graph

    graph = build_graph()
    state = graph.invoke({"mode": "research"})
    assert "opportunities" in state
```

- [ ] **Step 2: Run the test and confirm it fails**
- [ ] **Step 3: Implement the LangGraph nodes and edges**

Core nodes:
- `scan_market`
- `detect_anomaly`
- `generate_hypothesis`
- `score_feasibility`
- `code_strategy`
- `backtest`
- `critique`
- `update_memory`
- `risk_guard`
- `human_checkpoint`
- `proposal_finalize`

Edges must support:
- normal forward flow
- rejection loop back to hypothesis generation
- critique loop back to strategy coder
- human approval pauses
- persistence resume

- [ ] **Step 4: Run the test and confirm it passes**
- [ ] **Step 5: Commit**

**Exit criteria:** The system can loop, branch, pause, and resume.

### Task 6: Add checkpoints and recovery

**Files:**
- Create: `src/crypto_alpha_agent/checkpointing.py`
- Modify: `src/crypto_alpha_agent/orchestrator.py`
- Create: `tests/test_checkpoint_resume.py`

- [ ] **Step 1: Write a resume test**
- [ ] **Step 2: Confirm a paused run restores state**
- [ ] **Step 3: Add durable checkpoint storage**
- [ ] **Step 4: Confirm resume after interruption**
- [ ] **Step 5: Commit**

**Exit criteria:** Every run can survive process death.

---

## Phase 4: Discovery and Feasibility

### Task 7: Implement the market scanner and anomaly detector

**Files:**
- Create: `src/crypto_alpha_agent/agents/scanner.py`
- Create: `src/crypto_alpha_agent/agents/anomaly.py`
- Create: `tests/test_scanner_outputs.py`

- [ ] **Step 1: Write a scanner output test**
- [ ] **Step 2: Confirm it fails with no scanner**
- [ ] **Step 3: Implement a broad scanner that does not hardcode one strategy**

Scanner inputs should include:
- CEX order books, spreads, funding, borrow rates
- DEX pools, liquidity depth, TVL, reward programs
- chain events, contract changes, bridge flows
- social/news cues only as weak signals

- [ ] **Step 4: Implement anomaly scoring**

The anomaly detector should separate:
- statistical outliers
- structural discontinuities
- one-off noise
- impossible-to-trade mirages

- [ ] **Step 5: Confirm the tests pass and commit**

**Exit criteria:** The system emits broad, ranked anomalies, not preselected trades.

### Task 8: Implement hypothesis generation and evidence collection

**Files:**
- Create: `src/crypto_alpha_agent/agents/hypothesis.py`
- Create: `tests/test_hypothesis_generation.py`

- [ ] **Step 1: Write a hypothesis generation test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Implement hypothesis templates**

Each hypothesis must state:
- what changed
- why it might be an edge
- what evidence supports it
- how long it may persist
- what would disprove it

- [ ] **Step 4: Add evidence bundles to the state**
- [ ] **Step 5: Confirm the tests pass and commit**

**Exit criteria:** Every candidate is a falsifiable research hypothesis.

### Task 9: Implement the feasibility scorer

**Files:**
- Create: `src/crypto_alpha_agent/risk/feasibility.py`
- Create: `tests/test_feasibility_scoring.py`

- [ ] **Step 1: Write a feasibility test**

```python
def test_low_capital_high_speed_trade_is_rejected():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=5000,
        current_capital_usd=300,
        speed_dependency="high",
        rpc_dependency="high",
        expected_net_pnl_usd=8,
    )
    assert score.approved is False
```

- [ ] **Step 2: Run the test and confirm it fails**
- [ ] **Step 3: Implement the scoring model**

Hard reject rules must cover:
- capital above budget
- speed dependency too high
- RPC dependency too high
- net pnl below minimum expected cost of ownership
- non-repeatable opportunities
- unbounded downside

- [ ] **Step 4: Run the test and confirm it passes**
- [ ] **Step 5: Commit**

**Exit criteria:** The system can say "this is real but not for you."

---

## Phase 5: Strategy Generation and Validation

### Task 10: Add the strategy coder and safe code sandbox

**Files:**
- Create: `src/crypto_alpha_agent/agents/coder.py`
- Create: `src/crypto_alpha_agent/tools/sandbox.py`
- Create: `tests/test_coder_sandbox.py`

- [ ] **Step 1: Write a sandbox test**
- [ ] **Step 2: Confirm generated code is blocked from unsafe imports**
- [ ] **Step 3: Implement constrained code generation**

The coder may only emit:
- backtest scripts
- data transforms
- indicator definitions
- execution proposals

It may not emit:
- arbitrary shell execution
- direct wallet-draining calls
- unrestricted network code

- [ ] **Step 4: Confirm sandboxed execution works on a toy script**
- [ ] **Step 5: Commit**

**Exit criteria:** LLM-written code can be run without giving it full trust.

### Task 11: Integrate vectorbt/backtrader validation

**Files:**
- Create: `src/crypto_alpha_agent/backtest/vectorbt_runner.py`
- Create: `src/crypto_alpha_agent/backtest/backtrader_runner.py`
- Create: `tests/test_backtest_results.py`

- [ ] **Step 1: Write a backtest result normalization test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Implement adapters that produce one comparable result format**

Required metrics:
- net return
- max drawdown
- win rate
- trade count
- average holding time
- fee-adjusted expectancy
- slippage-adjusted expectancy

- [ ] **Step 4: Confirm a toy strategy passes end-to-end**
- [ ] **Step 5: Commit**

**Exit criteria:** Backtest outputs can be compared across strategies and venues.

### Task 12: Add critique and reflection loops

**Files:**
- Create: `src/crypto_alpha_agent/agents/reflector.py`
- Create: `tests/test_reflection_loop.py`

- [ ] **Step 1: Write a critique test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Implement self-critique prompts and rejection reasons**

Reflection must answer:
- what assumption failed
- what evidence was missing
- whether the result is likely overfit
- whether costs were underestimated
- whether the opportunity is repeatable

- [ ] **Step 4: Confirm rejected strategies loop back correctly**
- [ ] **Step 5: Commit**

**Exit criteria:** The system can learn from failure instead of only scoring success.

---

## Phase 6: Memory and Ranking

### Task 13: Build long-term memory and retrieval

**Files:**
- Create: `src/crypto_alpha_agent/memory/store.py`
- Create: `src/crypto_alpha_agent/memory/retrieval.py`
- Create: `tests/test_memory_roundtrip.py`

- [ ] **Step 1: Write a memory round-trip test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Implement structured event storage and embedding storage**

Memory must keep:
- opportunities
- hypotheses
- scores
- rejected reasons
- backtest artifacts
- paper-trade outcomes

- [ ] **Step 4: Confirm retrieval returns relevant prior cases**
- [ ] **Step 5: Commit**

**Exit criteria:** The system remembers what worked and what was illusion.

### Task 14: Add ranking and portfolio of candidate ideas

**Files:**
- Create: `src/crypto_alpha_agent/risk/ranker.py`
- Create: `tests/test_ranking_policy.py`

- [ ] **Step 1: Write a ranking test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Rank by expected net value, confidence, repeatability, and capital efficiency**
- [ ] **Step 4: Confirm top-N selection is stable**
- [ ] **Step 5: Commit**

**Exit criteria:** The system chooses a small number of good candidates instead of many noisy ones.

---

## Phase 7: Paper Trading and Controlled Execution

### Task 15: Add the paper-trade execution lane

**Files:**
- Create: `src/crypto_alpha_agent/execution/paper.py`
- Create: `tests/test_paper_execution.py`

- [ ] **Step 1: Write a paper execution test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Implement paper fills, fees, slippage, and latency simulation**
- [ ] **Step 4: Confirm paper PnL matches the validation contract**
- [ ] **Step 5: Commit**

**Exit criteria:** The system can simulate execution without touching real capital.

### Task 16: Add risk guardian and human approval checkpoints

**Files:**
- Create: `src/crypto_alpha_agent/risk/guardian.py`
- Create: `src/crypto_alpha_agent/agents/approvals.py`
- Create: `tests/test_risk_guardian.py`

- [ ] **Step 1: Write a risk gate test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Implement approval thresholds and kill-switch rules**

Required guards:
- max capital per opportunity
- max daily loss
- max consecutive failures
- allowed venue list
- wallet and API permission scoping
- manual approval for live execution

- [ ] **Step 4: Confirm a blocked opportunity cannot reach execution**
- [ ] **Step 5: Commit**

**Exit criteria:** Nothing reaches live execution without explicit policy approval.

### Task 17: Add the Hummingbot/Freqtrade integration boundary

**Files:**
- Create: `src/crypto_alpha_agent/execution/hummingbot_adapter.py`
- Create: `src/crypto_alpha_agent/execution/freqtrade_adapter.py`
- Create: `tests/test_execution_adapter_contract.py`

- [ ] **Step 1: Write adapter contract tests**
- [ ] **Step 2: Confirm they fail**
- [ ] **Step 3: Implement one narrow adapter per engine**
- [ ] **Step 4: Confirm paper mode works through the adapter**
- [ ] **Step 5: Commit**

**Exit criteria:** The agent can hand a validated idea to an existing execution engine instead of re-implementing trading infra.

---

## Phase 8: Observability and Operations

### Task 18: Add logging, metrics, and replayable reports

**Files:**
- Create: `src/crypto_alpha_agent/observability/logging.py`
- Create: `src/crypto_alpha_agent/observability/reports.py`
- Create: `tests/test_report_generation.py`

- [ ] **Step 1: Write a report generation test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Implement structured logs and daily reports**
- [ ] **Step 4: Confirm reports can be regenerated from persisted events**
- [ ] **Step 5: Commit**

**Exit criteria:** Every decision is explainable after the fact.

### Task 19: Add CLI commands and operator runbook

**Files:**
- Create: `src/crypto_alpha_agent/cli.py`
- Create: `docs/runbook.md`
- Create: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write a CLI smoke test**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Implement `scan`, `research`, `backtest`, `paper`, `report`, and `replay` commands**
- [ ] **Step 4: Confirm help and a dry run work**
- [ ] **Step 5: Commit**

**Exit criteria:** A human can operate and recover the system without reading internals.

---

## Phase 9: Validation and Release Gates

### Task 20: Add the end-to-end regression suite

**Files:**
- Create: `tests/test_end_to_end_loop.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write an e2e loop test from scan to paper trade**
- [ ] **Step 2: Confirm it fails**
- [ ] **Step 3: Make the graph run from scan through critique and memory**
- [ ] **Step 4: Confirm the e2e test passes on synthetic data**
- [ ] **Step 5: Commit**

**Exit criteria:** The whole closed loop works on a deterministic fixture.

### Task 21: Define rollout gates from paper to tiny live

**Files:**
- Create: `docs/rollout-gates.md`
- Create: `src/crypto_alpha_agent/risk/rollout.py`
- Create: `tests/test_rollout_gates.py`

- [ ] **Step 1: Write rollout gate tests**
- [ ] **Step 2: Confirm they fail**
- [ ] **Step 3: Encode hard thresholds for live eligibility**

Suggested live gates:
- positive net expectancy after all costs
- low failure rate over a fixed sample
- stable performance across walk-forward splits
- no manual override violations
- max loss under budget

- [ ] **Step 4: Confirm live is blocked until the gates pass**
- [ ] **Step 5: Commit**

**Exit criteria:** Live execution is a reward for validated behavior, not a default.

---

## Execution Order

1. Bootstrap the repo and test harness.
2. Define the schema and config.
3. Add data connectors and normalization.
4. Build the LangGraph state machine and persistence.
5. Implement broad discovery and anomaly detection.
6. Add hypothesis generation and feasibility scoring.
7. Add strategy coding, sandboxing, and validation.
8. Add critique, reflection, and long-term memory.
9. Add paper trading and risk gating.
10. Integrate with existing execution engines.
11. Add observability, CLI, and recovery tooling.
12. Run end-to-end regression tests.
13. Only after repeated positive paper results, consider a tiny live lane.

## Decision Rule

The system must never hardcode a single opportunity type. Discovery stays broad; execution stays narrow. Anything that requires strong latency, strong RPC, private order flow, or more capital than the current budget should stay in research mode and never reach the live lane.
