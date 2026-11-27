# Automated Triage

`./maat triage REPORT` analyses a report by comparing it against earlier reports, called
*pivots*. Each section below describes one step; everything except the Claude step is
deterministic.

## Running locally

```shell
./maat triage reports/<report>.json --pivots-only
./maat triage reports/<report>.json -o /tmp/a.json
./maat triage reports/<report>.json --pivot <pivot-report> -o /tmp/a.json   # choose pivots by hand
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

## Comparison

`triage/diff.py`. Per project: regression, fix, changed failure (same outcome, different
errors), still failing, lint pass/fail flip, new or removed project. Error lines are compared
as a set, after stripping paths, hex values, durations, warning counts and lifetimes, so
nondeterministic test order or a rustc formatting change doesn't count as a change. Each change
carries a log excerpt, a link to the logs, and the project's outcome over the last 4 reports of
the same kind (tagged with their tool versions). Lint pass/fail is not a failure on its own,
because cairo-lint fails on almost every project; a cairo-lint panic is.

With several pivots, a failure that is unchanged against one pivot is not news against
another: a project that fails exactly as on the last stable release isn't a "changed failure"
just because the previous RC failed differently.

Drift: added/removed projects, rev changes, and Ma'at harness commits between the two reports.

Status: green when nothing changed, amber otherwise. Regressions against any pivot count.

### Known issues

`known_issues.toml`, glob-matched against project names and labels. Matching failures are
marked as known and stop counting as news.
