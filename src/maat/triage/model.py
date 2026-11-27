from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from maat.triage.changelog import ToolChangelog
from maat.triage.diff import ReportDiff
from maat.triage.pivot import Pivot

type Status = Literal["green", "amber", "red"]

STATUS_RANK: dict[str, int] = {"green": 0, "amber": 1, "red": 2}


# --- LLM output schema (kept flat and enum-heavy for structured outputs) ---------------------


class Finding(BaseModel):
    title: str = Field(
        description="One line, specific. E.g. 'Scarb 2.21.0 rejects `use` of removed UniversalDeployerABI'."
    )
    projects: list[str] = Field(
        description="Affected project names, exactly as given in the input."
    )
    classification: Literal[
        "toolchain-regression",
        "intended-breaking-change",
        "project-change",
        "flaky",
        "infra",
        "harness",
        "known-issue",
        "performance",
        "unknown",
    ]
    component: Literal[
        "scarb",
        "cairo-compiler",
        "starknet-foundry",
        "cairols",
        "cairo-lint",
        "maat",
        "project",
        "external-service",
        "unknown",
    ]
    confidence: Literal["high", "medium", "low"]
    explanation: str = Field(
        description="2-4 sentences: what changed and why you think so."
    )
    evidence: list[str] = Field(
        description="Short verbatim quotes from the provided logs/changelog supporting the explanation."
    )
    suspected_commits: list[str] = Field(
        description="Commit SHAs copied from the provided upstream changes. Empty if none plausibly relate."
    )
    lint_kinds: list[str] = Field(
        default=[],
        description="IDs (L1, L2, ...) of the lint diagnostic changes this finding explains. Empty if none.",
    )


class Action(BaseModel):
    kind: Literal["rerun", "file-issue", "maat-fix", "known-issue", "needs-human"]
    title: str
    detail: str = Field(
        description="What exactly to do or what question a human must answer."
    )
    projects: list[str]
    issue_repo: Literal[
        "software-mansion/scarb",
        "starkware-libs/cairo",
        "foundry-rs/starknet-foundry",
        "software-mansion/cairols",
        "software-mansion/cairo-lint",
        "software-mansion/maat",
        "none",
    ] = Field(description="Target repository for kind=file-issue, otherwise 'none'.")
    issue_title: str = Field(
        description="Draft issue title for kind=file-issue, otherwise empty."
    )
    issue_body: str = Field(
        description="Draft issue body (markdown) for kind=file-issue, otherwise empty."
    )


class PerformanceVerdict(BaseModel):
    verdict: Literal[
        "no-significant-change", "improved", "regressed", "mixed", "not-comparable"
    ]
    summary: str = Field(
        description="One or two sentences grounded in the provided numbers."
    )


class Triage(BaseModel):
    status: Literal["green", "amber", "red"]
    headline: str = Field(description="Max ~200 characters, plain text, for Slack.")
    performance: PerformanceVerdict
    drift_summary: str = Field(
        description="One sentence on ecosystem/harness drift, or empty if nothing notable."
    )
    findings: list[Finding]
    actions: list[Action]


# --- Persisted analysis ----------------------------------------------------------------------


class LlmMeta(BaseModel):
    model: str
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None
    error: str | None = None


class Analysis(BaseModel):
    report: str
    generated_at: datetime
    target_versions: dict[str, str]
    pivots: list[Pivot]
    diffs: list[ReportDiff]
    changelogs: list[ToolChangelog]
    """Changelog against the primary pivot."""
    triage: Triage | None = None
    status: Status
    status_notes: list[str] = []
    """Why the deterministic guardrails adjusted the LLM status, if they did."""
    headline: str
    rerun_command: str
    llm: LlmMeta | None = None
    run_url: str | None = None

    @property
    def primary(self) -> ReportDiff | None:
        return self.diffs[0] if self.diffs else None
