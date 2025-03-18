import re

import click

type Semver = str

SEMVER_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-(?P<pre>[0-9a-zA-Z.-]+))?(?:\+(?P<build>[0-9a-zA-Z.-]+))?$"
)


class SemverParamType(click.ParamType):
    name = "version"

    def convert(self, value, param, ctx) -> Semver:
        if SEMVER_RE.match(value):
            return value
        else:
            self.fail(f"{value} is not a valid semantic version", param, ctx)
