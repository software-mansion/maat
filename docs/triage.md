# Automated Triage

After every experiment, the `analyse` job in `experiment.yml` runs `./maat triage` on the new
report. It compares the report against earlier reports, called *pivots*, produces a
green/amber/red status, findings and action items, and commits them to
`analyses/<report>.json`. The web build renders that file to `analysis/<report>.html`, and the
Slack notification carries the status, a one-line summary, a link to the page, and (only if
there is something to say) a thread reply with the top findings.

A failed analysis never blocks the report: every triage step in CI is non-blocking.

## Running locally (offline replay)

```shell
./maat triage reports/<report>.json --pivots-only

# Deterministic part only, plus the exact prompt Claude would get:
./maat triage reports/<report>.json --no-llm --dry-run /tmp/prompt.txt --html /tmp/a.html -o /tmp/a.json

# Full run (needs ANTHROPIC_API_KEY); pick pivots by hand to compare prompt changes:
./maat triage reports/<report>.json --pivot <pivot-report> --html /tmp/a.html -o /tmp/a.json
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

## Upstream changes

`triage/changelog.py`. Scarb, Cairo, cairo-lint and Starknet Foundry commits between the
primary pivot and the target, via the GitHub compare API. Stable and pre-release versions use
their `v*` tags; nightly and dev source commits come from the `scarb-nightlies` and
`starknet-foundry-nightlies` release notes; the Cairo version comes from Scarb's `Cargo.toml`.
A local run uses your `gh` login for the GitHub API.

## Claude

`triage/llm.py`. One structured-output request, with no tools, that classifies each change
(toolchain regression, intended breaking change, project change, flaky, infra, harness, known
issue, performance) and proposes action items. Logs are passed as untrusted data. The prompt
asks for zero findings when nothing changed. The model and effort can be overridden with
`MAAT_TRIAGE_MODEL` and `MAAT_TRIAGE_EFFORT`; it needs `ANTHROPIC_API_KEY`.

Guardrails (`triage/pipeline.py`):

* Project names, commit SHAs and lint kinds the input doesn't contain are dropped.
* The status is forced to green when the diff shows no new failures, no performance
  regression and no significant lint change.
* The status is raised to amber when regressions are left unexplained.
* The status is raised to amber when a significant lint diagnostic change isn't attributed
  (per kind) to an intended change with a suspected upstream commit.
* Without the LLM, the status is green or amber, never red.

## Analysis page

`triage/render.py`. A static page with only the essentials: status, compared reports (with
side-by-side links into the report viewer), action items (with a rerun command and pre-filled
issue links), findings, change tables, performance, drift and upstream commits.
`./maat export-web-assets` renders every `analyses/*.json` to `analysis/<report>.html`, and
`gc-reports` removes analyses together with their reports.

## CI and Slack

The `analyse` job in `experiment.yml` runs after the report is committed, commits
`analyses/<report>.json`, and triggers the web build. `web.yml` reads the analysis with
`./maat slack-fields` and adds it to the Slack payload.

Configuration:

* Repository secret `ANTHROPIC_API_KEY`.
* Slack workflow (webhook trigger) variables: `url`, `report_name`, `status`, `summary`,
  `analysis_url`, `thread_text`. `thread_text` is empty when there is nothing worth a thread.
