<div align="center">
  <picture>
    <img alt="An artistic depiction of Ma'at, the ancient Egyptian goddess, overseeing a balanced ecosystem as experiments unfold, symbolizing harmony and testing."
         src="./docs/logo.png"
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
            fromFedora-->rustInstall-->asdfInstall-->warmup-->addTestHarness
        end

        dockerBuildCli-->Dockerfile
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
            forceBuildEnv-->build-->lint-->test-->ls
        end
        
        dockerRun-->container
    end
    
    reportJson[(report.json)]
    
    cliRun-->dockerBuild-->experimentLoop
    build & lint & test & ls -.-> reportJson
```

You can then compare two reports with the following invocation to detect regressions:

```shell
./maat diff old_report.json report.json
```

[cairo]: https://www.cairo-lang.org/
[crater]: https://github.com/rust-lang/crater
[rust]: https://rust-lang.org/
[uv]: https://docs.astral.sh/uv/
