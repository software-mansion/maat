# Automated Triage

`./maat triage REPORT` analyses a report by comparing it against earlier reports, called
*pivots*. Each section below describes one step; everything except the Claude step is
deterministic.

## Running locally

```shell
./maat triage reports/<report>.json    # prints the chosen pivots and why
```

## Pivots

`triage/pivot.py`. Up to two reports created before the target:

| Target            | Pivots                                                                                    |
|-------------------|-------------------------------------------------------------------------------------------|
| stable release    | previous stable Scarb (same Foundry if possible) or, if only Foundry changed, the previous Foundry with the same Scarb; then the RC of the same version or an identical earlier run |
| release candidate | previous pre-release of the same version, previous stable release, identical earlier run, latest nightly |
| nightly           | previous nightly, latest stable release                                                   |
| dev build         | previous dev build, latest nightly, latest stable release                                 |
| `custom-*`        | previous run of the same custom experiment, latest nightly (nightly workspace), latest stable release |

Only reports created before the target are candidates, so replaying an old report behaves the
same way it would have in CI. Reports pruned by `gc-reports` are loaded from git history
(`--no-git-history` skips them).
