# Rollout gates

Live execution is not a default mode. A strategy earns tiny-live eligibility only
after deterministic, local evaluation of paper results and walk-forward evidence.
The rollout gate produces an eligibility decision and machine-readable reason
codes; it does not place orders, call exchanges, open wallets, or bypass the
risk guardian.

## Default policy

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

## Evidence requirements

Paper evidence is represented as `PaperTradeObservation` records:

- stable trade identifier
- gross PnL in USD
- total costs in USD
- failure flag
- manual override violation flag

Walk-forward evidence is represented as `WalkForwardSplit` records:

- stable split identifier
- cost-adjusted expectancy in USD

The evaluator also requires the maximum observed loss in USD from the paper
period. This must come from offline evidence and is compared to the rollout loss
budget.

## Blocking reason codes

The evaluator returns stable reason codes for automation and review:

| Reason code | Meaning |
| --- | --- |
| `insufficient_sample_size` | Fewer paper observations than the policy minimum. |
| `insufficient_walk_forward_splits` | Fewer walk-forward splits than the policy minimum. |
| `non_positive_cost_adjusted_expectancy` | Average paper PnL after costs is not positive. |
| `failure_rate_above_limit` | Paper failure rate exceeds the policy maximum. |
| `unstable_walk_forward_performance` | Any split expectancy is at or below the policy floor. |
| `manual_override_violation` | Paper evidence includes a manual override violation. |
| `max_loss_budget_breached` | Maximum observed paper loss exceeds the policy budget. |

## Why live is separate

`eligible_for_tiny_live=True` means the paper evidence passed rollout gates. It
is not an execution command and must not trigger adapters or wallet actions.
Actual live behavior remains a separate, gated workflow with explicit approvals,
permission scoping, and risk checks.
