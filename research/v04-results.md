# V0.4 experiment record
100 seeds per regime, 1000 events per seed; synthetic outcomes, not real users.
| Regime | Rule | SAGE | Adaptive |
|---|---:|---:|---:|
| aligned | .02128 | .05330 | .03837 |
| alternate | .04750 | .06828 | .07251 |
Paired adaptive - SAGE approximate 95% CI: aligned [-.01724,-.01263]; alternate [.00016,.00829].
Unwanted interventions (SAGE vs adaptive): aligned 9905 vs 18482; alternate 7890 vs 20271.
Three unit tests passed: permission, expiry, feedback. The pending-task mechanism is partial, simulated reward is immediate and fully observed, and the exploration policy is not production-safe. Do not promote adaptive to default. Full V0.4 source is in the local ZIP artifact; this commit records results only.
