# Running Ma'at locally

Ma'at is a Python application ([uv]-powered).
You can clone this repository, set up a local workspace and run it locally.

You need the following things to have up and running on your machine:

- [uv]
- Docker (or compatible stack like Podman or OrbStack)
    - You need `docker` CLI binary to be accessible via `PATH`.
      Shell aliases will not work.
- _Only for development_: Node.js (there is a line for it in `.tool-versions`)

Run the following to learn all available commands:

```shell
./maat --help
```

## Commonly used commands

- `./maat run-local` - runs an experiment on local Docker server.
  This behaves just like [scheduled experiments](./experiments.md#scheduling).
- `./maat web` - builds Ma'at website.
- `./maat checkout` - see [Checkouts](./checkouts.md).

[uv]: https://docs.astral.sh/uv/
