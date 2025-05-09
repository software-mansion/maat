<div align="center">
  <picture>
    <img alt="An artistic depiction of Ma'at, the ancient Egyptian goddess, overseeing a balanced ecosystem as experiments unfold, symbolizing harmony and testing."
         src="src/maat/frontend/templates/_assets/logo.png"
         height="256" width="256">
  </picture>

# Ma'at

Ma'at is a tool to run experimental software builds across [Cairo] language ecosystem.
Something like [Crater] of [Rust], but for Cairo.
</div>

---

## Getting started

Ma'at is a Python application ([uv]-powered).
You can clone this repository, set up a local workspace and run it locally.

You need the following things to have up and running on your machine:

- [uv]
- Docker (or compatible stack like Podman or OrbStack)
    - you need `docker` CLI to be accessible via `PATH`
- _Only for development_: Node.js (there is a line for it in `.tool-versions`)

To get started, run:

```shell
./maat
```

The CLI will guide you through configuring your experiment.

## Flow

Ma'at experiment run roughly performs the following steps:

```mermaid
flowchart TD
    cliRun(./maat #91;--workspace release#93; run-local)

subgraph dockerBuild [Build Container Image]
direction LR
dockerBuildCli(ASDF_SCARB_VERSION=X.Y.Z\nASDF_STARKNET_FOUNDRY_VERSION=X.Y.Z\ndocker build -t IMG ...)

subgraph Dockerfile
direction TB
fromFedora(FROM fedora:latest)
rustInstall(install latest stable rust via rustup)
asdfInstall(install scarb and foundry via asdf)
warmup(create empty foundry project and compile it\nto warmup caches and prebuild snforge plugin)
addTestHarness(add test harness)
fromFedora --> rustInstall --> asdfInstall -->warmup --> addTestHarness
end

dockerBuildCli --> Dockerfile
end

subgraph experimentLoop [For each ecosystem project, in parallel]
direction TB
dockerRun(docker run --rm -t IMG test_harness)

subgraph container [Container]
direction LR
forceBuildEnv(force the project to use experiment's\nScarb and Foundry versions)
build(scarb build)
lint(scarb lint)
test(run snforge or cairo-test)
ls(start cairols and collect diagnostics)
forceBuildEnv --> build --> lint --> test --> ls
end

dockerRun --> container
end

reportJson[(report.json)]

cliRun --> dockerBuild -->experimentLoop
build & lint & test & ls -.-> reportJson
```

You can then compare two reports with the following invocation to detect regressions:

```shell
./maat build-web old_report.json report.json
```

## Debugging reports

With Jupter Notebooks or Python REPL it is fairly easy to inspect reports and look for some traces
of errors.
Check out [`sample_notebook.ipynb`](./sample_notebook.ipynb) file for examples.
The `maat.model.Report` class provides a fully typed representation of report files.
The `maat.repl` module provides some handy utilities.

## Notifications

`./maat run-local` can emit a notification upon finish on macOS (via `osascript`) and Linux (via
`notify-send`).
On macOS, by default scripts have no privileges granted to send notifications,
and this results in no notifications appearing from Ma'at.
To fix this, open `Script Editor.app` and run the following script:

```applescript
display notification "world" with title "hello"
```

This should result in a notification permission request for Script Editor to appear which you need
to accept—after this, Ma'at will successfully notify on experiment completion.

[cairo]: https://www.cairo-lang.org/

[crater]: https://github.com/rust-lang/crater

[rust]: https://rust-lang.org/

[uv]: https://docs.astral.sh/uv/
