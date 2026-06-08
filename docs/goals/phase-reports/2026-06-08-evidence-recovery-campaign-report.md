# Evidence Recovery Campaign Report

## Phase

- Date: 2026-06-08
- Round: 19
- Slice: Evidence Recovery Campaign
- Owner objective: design the remaining completion roadmap and execute the
  approved phases until the project satisfies
  `docs/goals/project-completion-goal.md` or reaches a documented blocker.
- Mode: operations and documentation only; no product-code changes.
- Commit reference: pushed closeout commit chain on `main` containing this
  report.
- Safety: `uses_real_capital=false`, `live_order_routing=false`, no wallet
  access, no exchange order routing, and no stopped-family override.

## Smart Search Evidence

Evidence directory:

`var/smart-search-evidence/2026-06-08-completion-roadmap/`

Commands and artifacts used before design:

- Smart Search doctor: passed with configured search/fetch providers.
- Deep research query:
  `Design the remaining roadmap for a low-capital crypto alpha research agent: public data ingestion, validation evidence, paper outcomes, rollout gates, and no live execution`.
- Broad source search:
  `official documentation Binance futures funding rate open interest API CCXT proxy configuration DexScreener API DefiLlama API walk-forward validation trading systems`.
- Fetched source artifacts:
  - `02-binance-funding.md`
  - `03-binance-open-interest.md`
  - `04-ccxt-docs.md`
  - `05-dexscreener-api.md`

External findings used:

- Binance USD-M funding history exposes a public funding-rate endpoint with
  `symbol`, `startTime`, `endTime`, and `limit`.
- Binance USD-M current open-interest endpoint is public, requires `symbol`,
  and returns open-interest fields.
- DexScreener remains suitable for discovery/watchlist use unless enough local
  snapshots exist for historical evidence.
- The CCXT docs fetch failed and produced an empty local artifact, so CCXT
  open-interest support was treated as unverified until local source-probe and
  ingest commands proved it.

## Local Feasibility

Files and surfaces inspected:

- `docs/project-charter.md`
- `docs/roadmap.md`
- `docs/runbook.md`
- `docs/rollout-gates.md`
- `docs/tiny-live-readiness.md`
- `docs/project-asset-assessment.md`
- `docs/goals/project-completion-goal.md`
- `docs/goals/project-completion-state.md`
- `src/crypto_alpha_agent/pipeline/evidence_runner.py`
- `src/crypto_alpha_agent/data/ingestion.py`
- `src/crypto_alpha_agent/data/source_probe.py`
- `src/crypto_alpha_agent/strategy/registry.py`
- `src/crypto_alpha_agent/strategy/funding_oi_crowding.py`
- `src/crypto_alpha_agent/cli.py`
- Existing SQLite ledgers under `var/research.sqlite`
- Existing reports under `var/reports/`

Baseline findings:

- The worktree started from `main...origin/main [ahead 1]` after the design
  spec commit, then `ahead 2` after the implementation plan commit.
- Existing validation and paper evidence belonged only to
  `funding_extremity_price_confirmation`, which was already stopped.
- Before this campaign, no `open_interest` source records existed.
- `proxy-fixed-20260607T142806Z` had restored CCXT OHLCV/funding,
  DexScreener, and DefiLlama collection through the proxy route, but wrote no
  validation evidence and no paper outcomes because the stopped default family
  was skipped.

## Substep Results

### Source-Probe Target List

Command:

```bash
uv run --extra dev crypto-alpha-agent source-probe --list-targets
```

Result: exit 0. The output included
`binance_usdm_open_interest_history` with `feed=open_interest_history`.
The real LLM judgement used `gpt-5.5` and kept
`uses_real_capital=false`, `live_order_routing=false`.

### No-Network OI Probe

Command:

```bash
uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_open_interest_history
```

Result: exit 2 by design. The source-health result recorded
`blocked_reason=network_not_allowed`, `network_route=blocked`, and no live
flags. This confirmed fail-closed no-network behavior.

### Proxy OI Probe

Command:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; \
uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_open_interest_history \
  --allow-network \
  --route proxy'
```

Result: exit 0. The probe returned HTTP 200, `parse_status=parsed`,
`provider_status=ResearchUsable`, and `typed_record_count=1`. No proxy values
were printed.

### CCXT OI Ingest

Command:

```bash
bash -lc 'set -a; source .env >/dev/null 2>&1; set +a; \
uv run --extra dev crypto-alpha-agent ingest \
  --source ccxt \
  --allow-network \
  --ccxt-feed open-interest-history \
  --exchange binance \
  --symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 24 \
  --db var/research.sqlite \
  --current-capital-usd 300'
```

Result: exit 0. The command fetched 24 records and wrote 24 typed
`open_interest` records. SQLite inspection showed:

- symbol: `BTC/USDT:USDT`
- venue: `binance`
- observed window: 2026-06-07T02:00:00+00:00 through
  2026-06-08T01:00:00+00:00
- open-interest range: 98293.307 to 103160.276

### OI Crowding Evidence Run

Run id: `evidence-recovery-oi-20260608T015547Z`

Result: exit 0, `network_route=proxy`, no stopped-family override.

Source health:

- CCXT OHLCV: 200 records
- CCXT funding history: 200 records
- CCXT open-interest history: 200 records
- DexScreener, DefiLlama, Dune, and TheGraph: skipped as not configured in
  this run

Evidence:

- validation evidence written: 1
- paper outcomes written: 1
- paper status: `blocked`
- validation approved: false
- blocked reasons:
  - `no_extreme_funding`
  - `insufficient_trades`
  - `non_positive_expectancy`
  - `non_positive_net_return`
  - `unstable_walk_forward_performance`

The evidence-run LLM interpretation was `keep_collecting`, but deterministic
governance later classified the family as `stop`.

### Mean-Reversion Fallback Evidence Run

Run id: `evidence-recovery-mean-reversion-20260608T020000Z`

Result: exit 0, `network_route=proxy`, no stopped-family override.

Source health:

- CCXT OHLCV: 200 records
- CCXT funding history: 200 records
- optional sources skipped as not configured

Evidence:

- validation evidence written: 1
- paper outcomes written: 1
- paper status: `blocked`
- validation approved: false
- blocked reasons:
  - `no_extreme_funding`
  - `insufficient_trades`
  - `non_positive_expectancy`
  - `non_positive_net_return`
  - `unstable_walk_forward_performance`

The evidence-run LLM interpretation was `useful_for_research`, but
deterministic governance later classified the family as `stop`.

### Governance Report

Command:

```bash
uv run --extra dev crypto-alpha-agent governance-report \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/evidence-recovery/governance-latest.md \
  --current-capital-usd 300
```

Result: exit 0. The report preserved `Real capital: false` and
`Live order routing: false`.

Final governance actions:

- `funding_extremity_price_confirmation`: `stop`
- `funding_mean_reversion_after_extreme`: `stop`
- `funding_open_interest_crowding`: `stop`
- `defi_yield_regime_watchlist`: `add_data`
- `dex_liquidity_volume_watchlist`: `add_data`
- `volatility_compression_expansion_watchlist`: `add_data`

Paper-only portfolio selector: no candidate.

Monthly owner review: `add_data`, reason `no_paper_portfolio_candidate`.

## Blocker

The campaign restored the mechanics of the active funding validation-to-paper
path, including open-interest ingestion. It did not restore a viable paper
candidate.

The documented blocker is profit-evidence quality:

- all executable funding families are now stopped by governance;
- new paper outcomes are blocked;
- validation evidence is not approved;
- sample size is far below the 30/60/90 targets;
- walk-forward stability is weak;
- cost-adjusted expectancy is not positive;
- there is no paper-only portfolio candidate and no tiny-live review path.

This is not a source-connectivity blocker and not a product-code defect. The
next safe action is a new evidence-first design for strategy redesign or a
different public-data-backed family. Repeating the stopped funding families is
not useful without explicit owner review and fresh positive validation
evidence.

## Files Changed

Tracked files:

- `docs/superpowers/specs/2026-06-08-evidence-recovery-campaign-design.md`
- `docs/superpowers/plans/2026-06-08-evidence-recovery-campaign.md`
- `docs/goals/project-completion-state.md`
- `docs/roadmap.md`
- `docs/goals/phase-reports/2026-06-08-evidence-recovery-campaign-report.md`

Runtime artifacts, not staged:

- `var/reports/evidence-recovery/evidence-recovery-oi-20260608T015547Z.*`
- `var/reports/evidence-recovery/evidence-recovery-mean-reversion-20260608T020000Z.*`
- `var/reports/evidence-recovery/latest.*`
- `var/reports/evidence-recovery/governance-latest.md`
- `var/run-manifests/evidence-recovery/evidence-recovery-oi-20260608T015547Z.manifest.json`
- `var/run-manifests/evidence-recovery/evidence-recovery-mean-reversion-20260608T020000Z.manifest.json`
- `var/run-manifests/evidence-recovery/latest.json`
- `var/research.sqlite`
- `var/memory/evidence.jsonl`

## Subagents And Worktree

The Goal contract requests subagent use. The available subagent tool in this
session was restricted to cases where the user explicitly asks for subagents,
so no subagent was spawned. Reviews were performed locally.

The executing-plans workflow recommends an isolated worktree. This campaign
depended on gitignored local operator artifacts in the current workspace:
`.env`, `var/research.sqlite`, `var/memory/evidence.jsonl`, and existing
reports. A new worktree would not contain those artifacts without copying or
linking local secrets and runtime data. The round therefore stayed in the
current owner-confirmed workspace and records that exception here.

## Review Passes

Specification/requirements review:

- The campaign followed the approved design: source evidence first, local
  feasibility second, source qualification before strategy use, active families
  only, no stopped-family override, no live path.
- Success criterion 1 was partially satisfied mechanically: active families
  wrote validation evidence and paper outcomes. It failed economically because
  the outcomes were blocked and governance stopped the families.
- Success criterion 2 is satisfied: the blocker is documented with source,
  validation, paper, and governance evidence.

Safety/quality review:

- No product-code files were edited.
- Runtime artifacts remained under `var/`.
- `.env`, proxy values, database contents, memory JSONL, reports, and manifests
  were not staged.
- All committed docs summarize runtime evidence by path and key facts rather
  than copying secrets or raw local configuration.

## Verification

Completed before writing this report:

- source-probe list targets: exit 0
- no-network source-probe: exit 2, fail-closed as expected
- proxy source-probe: exit 0
- CCXT OI ingest: exit 0, 24 records written
- OI crowding evidence-run: exit 0
- mean-reversion fallback evidence-run: exit 0
- governance-report: exit 0
- SQLite ledger inspections confirmed payload and ledgers agree

Final closeout verification:

- `uv run --extra dev ruff check .`: passed.
- `git diff --check`: passed.
- requirements review over tracked docs: passed; the campaign either met the
  approved design mechanically or documented the profit-evidence blocker.
- safety review: passed; no product-code files were edited and no `var/`
  artifacts were staged.
- `git diff --cached --name-only`: contained only the intended docs.
- `git diff --cached --check`: passed.
- `git diff --cached --no-ext-diff --unified=0`: reviewed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`:
  returned `[]`.

## Secret Safety

Commands that needed local operator configuration loaded `.env` inside a
subshell with stdout redirected away from the source command. Outputs did not
print API keys, proxy values, provider headers, wallet material, or local
secrets. Runtime artifacts remain ignored under `var/` and must not be staged.
