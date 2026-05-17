# Rollout Gates

Live execution is not a default mode. A strategy earns tiny-live eligibility
only after deterministic, local evaluation of paper results and walk-forward
evidence. The `rollout-review` CLI produces an eligibility decision, a tiny-live
readiness artifact, and a strategy-specific evidence package for audit. It does
not place orders, call exchanges, open wallets, or bypass the risk guardian.
There is no live execution in this rollout review path.
The rollout review path does not place orders.

## Default Policy

The default `RolloutPolicy` is intentionally fail-closed:

| Gate | Default |
| --- | --- |
| Minimum paper trades | 30 |
| Maximum failure rate | 10% |
| Minimum walk-forward splits | 3 |
| Minimum split expectancy | Greater than 0.0 USD |
| Maximum observed loss budget | 100.0 USD |

Eligibility requires all gates to pass. Missing data blocks rollout instead of
being treated as neutral evidence.

The artifact is review-only. It keeps `live_execution_enabled=false`; there is
no live execution and it never becomes a live order routing command.

## Evidence Requirements

Paper evidence is represented as `PaperTradeObservation` records:

- stable trade identifier
- gross PnL in USD
- total costs in USD
- failure flag
- manual override violation flag

Walk-forward evidence is represented as `WalkForwardSplit` records:

- stable split identifier
- cost-adjusted expectancy in USD

The evaluator also requires `max_observed_loss_usd` from the paper period. This
must come from offline evidence and is compared to the rollout loss budget. A
review cannot be approved if the evidence package is missing or inconsistent.

## Blocking Reason Codes

The evaluator returns stable reason codes for automation and review:

| Reason code | Meaning |
| --- | --- |
| `insufficient_sample_size` | Fewer paper observations than the policy minimum. |
| `insufficient_walk_forward_splits` | Fewer walk-forward splits than the policy minimum. |
| `non_positive_cost_adjusted_expectancy` | Average paper PnL after costs is not positive. |
| `failure_rate_above_limit` | Paper failure rate exceeds the policy maximum. |
| `duplicate_paper_trade_evidence` | Paper evidence contains duplicate trade identifiers. |
| `duplicate_walk_forward_split` | Walk-forward evidence contains duplicate split identifiers. |
| `unstable_walk_forward_performance` | Any split expectancy is at or below the policy floor. |
| `manual_override_violation` | Paper evidence includes a manual override violation. |
| `max_loss_budget_breached` | Maximum observed paper loss exceeds the policy budget. |

## Why Live Is Separate

`eligible_for_tiny_live=true` means the paper evidence passed rollout gates. It
is not an execution command and must not trigger adapters or wallet actions.
Actual live behavior remains a separate, gated workflow with explicit approvals,
permission scoping, kill switch controls, rollback procedures, and risk checks
documented in `docs/tiny-live-readiness.md`.

## Evidence Package Preservation

The `rollout-review` command must preserve the evidence package used for the
decision. The package should retain:

- the strategy family
- the observation count, including the 30 observations threshold
- `max_observed_loss_usd`
- walk-forward split count
- paper failures and blocked reasons
- the generated tiny-live readiness artifact path
- the generated evidence package path

This preservation is required for later review and for tiny-live readiness
auditing. A reviewer should always be able to reconstruct why the command
returned pass or block without rerunning live logic.
