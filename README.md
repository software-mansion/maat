# Ma'at

Ma'at is a tool to run experimental software builds across [Cairo] language ecosystem.
Its purpose is to detect regressions in the Cairo language stack:
the compiler, scarb, test runners, linter and language server.
It does this by building a large number of packages, smoke testing all tools
and building comparison tables between various Cairo versions.
Ma'at is something like [Crater] of [Rust], but for Cairo.

## Documentation

* [Experiments](/docs/experiments.md)
* [Running Ma'at Locally](/docs/local.md)
* [Checkouts](/docs/checkouts.md)

[cairo]: https://www.cairo-lang.org/

[crater]: https://github.com/rust-lang/crater

[rust]: https://rust-lang.org/
