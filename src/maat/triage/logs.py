"""Log and label helpers shared by the diff modules: error extraction and normalisation."""

import re

from maat.model import LabelCategory, TestReport

EXCERPT_CHARS = 3000

ERROR_RE = re.compile(
    r"^\[(?:out|err)]\s*(error(?:\[E\d+])?:.*|thread '.*' panicked at .*|\[FAIL].*|Error: .*)$",
    re.M,
)
_NOISE_RE = re.compile(r"/mnt/maat-cache/\S+|0x[0-9a-fA-F]{6,}|\d+(?:\.\d+)?(?:s|ms)\b")
# Warning counts drift with every compiler release and say nothing about the failure.
_WARNINGS_RE = re.compile(r" and \d+ warnings?")
# rustc versions differ in whether they print lifetimes (`Foo<'db>` vs `Foo`).
_LIFETIMES_RE = re.compile(r"<'\w+(?:,\s*'\w+)*>|(?<=<)'\w+,\s*")


def normalise(line: str) -> str:
    line = _LIFETIMES_RE.sub("", _WARNINGS_RE.sub("", line))
    return _NOISE_RE.sub("…", line).strip()[:200]


def lint_panicked(t: TestReport) -> bool:
    return any(
        lbl.category == LabelCategory.LINT_FAIL and "panic" in (lbl.comment or "")
        for lbl in t.analyses.labels or []
    )


def failing_steps(t: TestReport):
    """Failing executed steps, with lint last (it fails almost everywhere)."""
    steps = [
        s for s in t.steps if s.was_executed and s.exit_code != 0 and s.log is not None
    ]
    return sorted(steps, key=lambda s: s.name == "lint")


def error_signature(t: TestReport) -> str | None:
    for step in failing_steps(t):
        if m := ERROR_RE.search(step.log_str):
            return f"{step.name}: {normalise(m.group(1))}"
        return f"{step.name}: exit code {step.exit_code}"
    return None


def error_set(t: TestReport) -> frozenset[str]:
    """
    All normalised error lines of the first failing non-lint step.

    Compared as a set because test runners print failures in nondeterministic order.
    """
    for step in failing_steps(t):
        if step.name == "lint":
            break
        return frozenset(normalise(m.group(1)) for m in ERROR_RE.finditer(step.log_str))
    return frozenset()


def excerpt(t: TestReport) -> str | None:
    """First error context plus the tail of the first failing step."""
    for step in failing_steps(t):
        log = step.log_str
        lines = log.splitlines()
        first = next((i for i, line in enumerate(lines) if ERROR_RE.match(line)), None)
        parts = [f"$ {step.run}  (exit {step.exit_code})"]
        if first is not None:
            parts += lines[max(0, first - 3) : first + 25]
            parts.append("…")
        parts += lines[-20:]
        text = "\n".join(_dedupe(parts))
        if len(text) > EXCERPT_CHARS:
            text = text[: EXCERPT_CHARS // 2] + "\n…\n" + text[-EXCERPT_CHARS // 2 :]
        return text
    return None


def _dedupe(lines: list[str]) -> list[str]:
    seen, out = set(), []
    for line in lines:
        if line in seen and line != "…":
            continue
        seen.add(line)
        out.append(line)
    return out
