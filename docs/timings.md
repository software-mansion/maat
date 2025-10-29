# Timings Methodology

This page explains what a “benchmark” means in Ma’at (step timings), exactly what is and isn’t
measured, and what each step in a project run does. The goal is to help you read reports and reason
about timing differences.

## What we measure

Ma’at records execution time for every step that belongs to a project run. A timer starts when the
step begins and stops when the step ends.

Included in a step’s time:

- Container start for that step
- The tool’s own work (build, lint, tests, etc.)
- Streaming logs
- Process shutdown

Not included in any step’s time:

- Work performed outside steps, e.g. the image “bake” that happens between setup and regular steps

Skipped steps (for example, after a failing setup step) have no timing recorded.

Additionally:

- A test’s total time is the sum of the times of its executed steps.
- The whole‑experiment time is measured once for the entire run.

## Setup vs regular steps (why it matters for timings)

Ma’at distinguishes setup steps from regular steps:

- Setup steps are allowed to populate caches and prepare the workspace. They run first. If a setup
  step fails, the remaining steps are marked as skipped.
- After setup succeeds, Ma’at “bakes” the cache and workbench into the image used for subsequent
  steps to make those runs faster and more reproducible. This baking itself is not a step, so it is
  not counted in any step timing.

## Step catalog (what each step does)

Below are the steps Ma’at runs for each project, in order, with notes about what they do and what
their timings include.

1) maat-check-versions (setup, checkout)

  - Command: `maat-check-versions`
  - Purpose: Verify that the Scarb and Starknet Foundry versions in the container match the versions
    selected for this run.
  - Timing includes: running the check and printing versions.

2) maat-patch (setup, checkout)

  - Command: `maat-patch`
  - Purpose: Adjust the project’s configuration so it builds and tests reliably with the selected
    toolchain versions.
  - What it typically changes:
    - Aligns the project’s Cairo version with the selected Scarb version.
    - Pins core Cairo dependencies to the toolchain version used in the run.
    - Ensures the appropriate test runner command is set (snforge, cairo-test, or cargo test).
    - Adds allowances required by some plugins where needed.
    - Optionally borrows safe dev‑dependency versions from a snapshot file, when present.
  - Timing includes: reading and writing manifest files and any quick checks it performs.

3) fetch (setup)

  - Command: `scarb fetch`
  - Purpose: Resolve and download dependencies for the whole workspace.
  - Timing includes: registry requests and dependency resolution.

4) tree (regular)

  - Command: `scarb tree -q --workspace`
  - Purpose: Print the resolved dependency tree to logs for debugging (no effect on later steps).
  - Timing includes: the `scarb tree` run.

5) build (regular)

  - Command: `scarb build --workspace --test`
  - Purpose: Compile the workspace (including test targets).
  - Environment notes: for unstable/nightly Scarb, Ma’at sets `SCARB_IGNORE_CAIRO_VERSION=true` to
    avoid version‑gate issues in dependencies.
  - Timing includes: compilation and any build‑time tooling invoked by Scarb.

6) lint (regular)

  - Command: `scarb lint --workspace --deny-warnings`
  - Purpose: Run Cairo lints across the workspace and fail on warnings.
  - Environment notes: same `SCARB_IGNORE_CAIRO_VERSION` rule may apply as in build.
  - Timing includes: lint analysis duration.

7) test (regular)

  - Command: `scarb test --workspace`
  - Purpose: Execute tests for all workspace packages using the detected runner.
  - Environment notes: Ma’at sets `SNFORGE_FUZZER_SEED=1` for reproducibility and
    `SNFORGE_IGNORE_FORK_TESTS=1` to skip fork tests.
  - Timing includes: test runner startup, execution, and teardown.

8) ls (Cairo Language Server) (regular)

  - Command: `maat-test-ls`
  - Purpose: Check that diagnostics from the Cairo Language Server (CairoLS) are consistent with
    build
    results and capture LS behavior in logs.
  - How it runs (high level):
    - Starts CairoLS inside the container.
    - Opens the project’s source files to trigger analysis.
    - Waits until the server becomes idle (with a short debounce to avoid transient flips) with a
      generous timeout to guard against hangs.
    - Collects diagnostics per file and prints a summary (errors, warnings, infos, hints).
    - Shuts down the server cleanly.
  - How results are interpreted:
    - If the build failed but LS reports no errors, Ma’at marks this as a mismatch.
    - If the build succeeded but LS reports errors, Ma’at marks this as a mismatch.
    - Fatal panics in tools are classified accordingly in labels.
  - Timing includes: LS startup, opening files, analysis, diagnostics collection, and shutdown.

## Notes and caveats

- Network variability (e.g., during `fetch` or tests) directly affects timings.
- Caching can significantly change durations. Setup steps prepare caches; regular steps benefit from
  the baked image that follows setup.
- Because the image bake happens between phases and is not part of any step, wall‑clock time you
  observe from the outside may be slightly larger than the sum of step timings.
