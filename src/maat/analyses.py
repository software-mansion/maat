from pydantic import BaseModel

from maat.model import Analysis


class CompiledProcMacrosFromSource(Analysis, BaseModel):
    KEY = "compiled_procmacros_from_source"
    package_ids: list[str]


class ClassifyDiagnostics(Analysis, BaseModel):
    KEY = "classify_diagnostics"
    warnings: int
    errors: int
    total: int
    diagnostics_by_message_and_severity: list[tuple[str, str, int]]
