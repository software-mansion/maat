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

## Performance and lint

`triage/perf.py`. Paired per-project ratios (target/pivot), only on matching hardware (CPU
model and count): build, test, lint and CairoLS step times, cold and incremental build, and
CairoLS peak memory. A metric is significant when the median moved by more than 7%, or a test
runner group of at least 10 projects moved by more than 15% (two groups moving in opposite
directions can cancel out in the overall median). Significant metrics list the projects that
contribute most to the shift. Single-project outliers are listed separately; on their own they
are not a regression.

A known issue with `scope = "performance"` excludes its projects from these aggregates; their
own medians are still shown in a separate line. `"all"` covers both failures and performance.

`triage/lint.py`. cairo-lint diagnostics are counted per kind (code and message) on projects
whose rev is unchanged, where cairo-lint output is deterministic. A kind that changed in at
least 2 projects or by at least 5 diagnostics is significant.

Status: a performance regression or a significant lint change also makes it amber.
