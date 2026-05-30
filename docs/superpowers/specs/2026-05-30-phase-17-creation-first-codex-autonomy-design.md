# Phase 17 Creation-First Codex Autonomy Design

## Goal

Build a Codex-only autonomous creation loop for the research agent.

The target is not another fixed pipeline. The target is a tool that can read its
own reports, notice stalled or missing research directions, search for new
evidence, invent new strategy families, add data sources, write code, run
experiments, and feed the result back into the next round.

The operating principle is:

```text
create first -> test what was created -> learn from the result -> create again
```

Validation remains useful, but it is feedback for iteration rather than a
front-loaded approval chain.

## Current Fit

The project already has the pieces needed for research execution:

- real LLM preflight and structured LLM calls;
- daily evidence runs;
- public market data collection;
- source probes and source health records;
- registered strategy families;
- strategy validators;
- paper simulation;
- reports, memory, ledgers, and operational wrappers.

The missing layer is creation:

```text
latest reports / stalled families / missing data / market evidence
  -> Codex proposes new research objects
  -> Codex writes code
  -> project runs real experiments
  -> failures and successes become the next creation backlog
```

Phase 17 adds that layer.

## Design Stance

This phase borrows the useful boundaries from CCG workflow, but does not copy
the full CCG runtime.

Keep:

- role-shaped prompts;
- persistent task artifacts;
- state and loop history;
- creation backlog;
- fresh Codex review sessions;
- run reports that explain what changed and what to try next.

Do not keep:

- Claude or Gemini dependencies;
- slash-command workflow requirements;
- heavy approval chains;
- multi-model routing;
- hard gates for ordinary research failures;
- CCG wrapper defaults that bypass sandboxing.

Only Codex is required.

## Product Shape

Add a product command:

```bash
uv run crypto-alpha-agent creation-cycle \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --task-root var/autonomy/tasks \
  --worktree-root var/autonomy/worktrees \
  --reports-root var/reports \
  --max-creations 1
```

Add an operations wrapper:

```bash
ops/creation-cycle.sh
```

The wrapper runs as a one-shot systemd timer job on the VPS. Each timer tick
starts one creation cycle, writes artifacts, exits, and lets the next timer tick
continue from the stored backlog.

## Minimal Hard Stops

The system should not be blocked by normal research uncertainty.

Hard stop only when:

- Codex or the configured real LLM cannot be reached;
- a proposed change tries to use real capital, route live orders, touch wallets,
  or read exchange trading secrets;
- a proposed command tries to modify files outside the project or its isolated
  worktree;
- the git/worktree state cannot be made safe enough to write a patch.

Everything else is soft feedback:

- tests failing;
- missing source data;
- poor source health;
- weak paper simulation;
- validator rejection;
- incomplete evidence;
- bad strategy performance;
- duplicate or stale family ideas.

Soft feedback does not stop creation. It changes the next prompt and the next
backlog item.

## Roles

Each role is a Codex prompt mode. Roles are used to keep thinking focused, not
to create a strict approval bureaucracy.

### Director

Reads recent reports, stopped families, current backlog, source health, and
strategy registry state. Chooses the next creation target:

- continue a promising idea;
- pivot away from a stopped family;
- search for new data;
- create a new family;
- improve a validator;
- fix a system issue blocking research.

### Scout

Searches for external evidence and internal project clues. It may use
smart-search CLI, repository search, recent reports, exchange documentation, and
market data summaries.

Its output is a short opportunity note with links or local artifact paths.

### Creator

Turns the opportunity into a creation object:

- `family_idea`;
- `data_source_idea`;
- `validator_idea`;
- `strategy_idea`;
- `experiment_idea`;
- `system_improvement_idea`.

The creation object describes the hypothesis, the first useful code change, the
expected experiment, and what would make the idea worth continuing.

### Builder

Runs Codex in an isolated worktree and writes code for the selected creation
object. It can add modules, modify registry entries, add probes, add validators,
add experiments, and update tests.

Builder is allowed to create working code. It is not limited to changing config.

### Runner

Runs the relevant deterministic commands after the build:

- focused unit tests;
- strategy validator checks;
- source probe checks;
- paper simulation where applicable;
- report generation where applicable.

Runner records failures instead of hiding them.

### Critic

Reads the patch and run output, then decides the next state:

- continue this creation;
- split it into smaller ideas;
- request more data;
- rewrite implementation;
- mark it stale;
- archive it as failed evidence.

Critic does not need to block all failed work. Its job is to keep the loop
learning.

## Creation Object

Each cycle creates or advances one object in `var/autonomy/backlog.jsonl`.

Minimal fields:

```json
{
  "id": "creation-20260530-001",
  "kind": "family_idea",
  "title": "Funding open interest crowding",
  "hypothesis": "Crowded long/short positioning can be detected through funding and open interest changes.",
  "why_now": "Recent reports show funding data exists but open interest coverage is missing.",
  "first_code_change": "Add an open-interest-backed family and source probe path.",
  "expected_experiment": "Collect funding plus open interest and run paper simulation.",
  "status": "active",
  "continuation_reason": "Needs source coverage and first validator run."
}
```

This is a working memory object, not a rigid approval schema.

## Task Artifacts

Every cycle writes a directory:

```text
var/autonomy/tasks/<task-id>/
  task.json
  director.md
  scout.md
  creation.json
  builder-prompt.md
  builder-output.jsonl
  patch.diff
  runner.md
  critic.md
  next-backlog.jsonl
```

The latest summary is also written to:

```text
var/reports/creation/latest.md
var/reports/creation/latest.json
```

The report should answer:

- what did Codex try to create;
- what evidence or reports caused that choice;
- what code changed;
- what actually ran;
- what failed;
- what should happen next.

## Codex Execution

The command checks Codex before starting work. If the check fails, the creation
cycle exits nonzero.

Read/planning roles can run without writing project files. Builder runs in an
isolated git worktree:

```text
var/autonomy/worktrees/<task-id>/
```

There is also one persistent active autonomy worktree:

```text
var/autonomy/active-worktree/
```

The first implementation uses this rule:

- Builder creates changes in the task worktree.
- Runner executes focused checks in the task worktree.
- If the task worktree can still import the package and run the next
  `creation-cycle` command, the patch is promoted into
  `var/autonomy/active-worktree/`.
- Future creation cycles run from the active autonomy worktree, so the tool can
  keep evolving itself.
- The owner's main checkout is not auto-pushed or auto-merged. Each promoted
  patch is still exported as `patch.diff` for inspection.

This keeps creation moving while avoiding ambiguity about where self-written
code becomes active.

Builder uses a controlled Codex exec call similar to:

```bash
codex exec \
  --cd var/autonomy/worktrees/<task-id> \
  --sandbox workspace-write \
  --ask-for-approval never \
  --json -
```

The builder prompt includes:

- the creation object;
- relevant report snippets;
- allowed project intent;
- forbidden live-capital behavior;
- commands the runner will execute.

The system saves the patch and run output. Failed creations remain useful: they
stay in the task directory, feed Critic, and can become revised backlog items.

## Scheduling

Use a systemd timer on the VPS:

```text
systemd timer -> ops/creation-cycle.sh -> creation-cycle -> Codex workers
```

The timer should be frequent enough for iteration, but each run should remain a
bounded one-shot process. The loop state lives in `var/autonomy/`, so stopping
or restarting the VPS does not erase the agent's memory.

The existing GHCR/Docker runtime can continue to run evidence jobs. The creation
cycle can either run on the host checkout or in a future autonomy image that has
Codex CLI installed and authenticated.

## Relationship To Deterministic Modules

Deterministic modules stay, but their meaning changes.

They are not substitutes for LLM-native work and they do not define autonomous
success by themselves. They are feedback sources for the next creation cycle:

- normalization tells Creator what fields are really available;
- schema validation tells Builder what shape code must satisfy;
- source quality tells Director which data source ideas are weak;
- validators tell Critic why a strategy failed;
- paper simulation tells Director whether to continue or pivot;
- cost model and risk guard prevent fake profitability;
- secret redaction keeps reports shareable;
- evidence ledger gives later cycles memory.

## Success Criteria

Phase 17 is successful when a VPS run can:

- fail closed when Codex/LLM is unavailable;
- read the latest project reports and backlog;
- create or advance a new research object;
- use Codex to write real project code in an isolated worktree;
- run focused verification and research commands;
- save patch, run output, and critique artifacts;
- update the creation backlog for the next timer run;
- move beyond a stopped family by proposing another family, data source, or
  experiment direction.

The first valuable outcome does not need to be profitable. It needs to prove
that the tool can create and iterate without being hand-fed the next family.

## Out Of Scope

- live trading;
- exchange order routing;
- wallet access;
- private key access;
- automatic real-capital deployment;
- requiring Claude or Gemini;
- requiring the full CCG installation;
- treating test failure as a reason to stop future creation.

## First Implementation Slice

The smallest useful slice is:

1. add creation-cycle command and task artifact store;
2. add Codex health check;
3. add Director and Creator prompts;
4. create one backlog item from latest reports;
5. run Builder in an isolated worktree;
6. run focused tests or a safe report command;
7. write creation report and updated backlog.

Scout/smart-search integration and richer Critic behavior can come immediately
after this slice works end to end.
