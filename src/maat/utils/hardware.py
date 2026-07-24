import os
import platform
import time
from dataclasses import dataclass
from pathlib import Path

from maat.model import HardwareInfo


@dataclass(frozen=True)
class _CpuSnapshot:
    """Monotonic Linux CPU counters captured at one point in time."""

    captured_at: float
    total_ticks: int | None
    steal_ticks: int | None
    pressure_some_microseconds: int | None


class HardwareCollector:
    """Collect static hardware data and CPU contention over an experiment."""

    def __init__(self):
        self._hardware = collect_hardware_info()
        self._start = _cpu_snapshot()

    def finish(self) -> HardwareInfo:
        """Return hardware data enriched with CPU metrics for the elapsed run."""
        end = _cpu_snapshot()
        return self._hardware.model_copy(
            update={
                "cpu_steal_percent": _cpu_steal_percent(self._start, end),
                "cpu_pressure_percent": _cpu_pressure_percent(self._start, end),
            }
        )


def collect_hardware_info() -> HardwareInfo:
    """Collect a terse hardware snapshot from Linux procfs with Unix fallbacks."""
    processors = _parse_cpuinfo(_read_text(Path("/proc/cpuinfo")))

    return HardwareInfo(
        cpu_model=_cpu_model(processors),
        physical_cores=_physical_cores(processors),
        logical_cores=len(processors) or os.cpu_count(),
        memory_bytes=_memory_bytes(_read_text(Path("/proc/meminfo"))),
        architecture=platform.machine() or None,
        kernel=platform.release() or None,
        virtualized=_is_virtualized(processors),
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _parse_cpuinfo(cpuinfo: str) -> list[dict[str, str]]:
    processors = []
    for block in cpuinfo.split("\n\n"):
        fields = {}
        for line in block.splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields[key.strip()] = value.strip()
        if fields:
            processors.append(fields)
    return processors


def _cpu_model(processors: list[dict[str, str]]) -> str | None:
    for key in ("model name", "Hardware", "Processor"):
        for processor in processors:
            if value := processor.get(key):
                return " ".join(value.split())
    return None


def _physical_cores(processors: list[dict[str, str]]) -> int | None:
    core_ids = {
        (processor["physical id"], processor["core id"])
        for processor in processors
        if "physical id" in processor and "core id" in processor
    }
    if core_ids:
        return len(core_ids)

    core_counts = {
        int(value)
        for processor in processors
        if (value := processor.get("cpu cores", "")).isdigit()
    }
    if len(core_counts) == 1:
        return core_counts.pop()
    return None


def _memory_bytes(meminfo: str) -> int | None:
    for line in meminfo.splitlines():
        key, separator, value = line.partition(":")
        if key == "MemTotal" and separator:
            parts = value.split()
            if parts and parts[0].isdigit():
                multiplier = 1024 if len(parts) > 1 and parts[1] == "kB" else 1
                return int(parts[0]) * multiplier
    return None


def _is_virtualized(processors: list[dict[str, str]]) -> bool | None:
    feature_sets = [
        set((processor.get("flags") or processor.get("Features") or "").split())
        for processor in processors
    ]
    if not feature_sets:
        return None
    return any("hypervisor" in features for features in feature_sets)


def _cpu_snapshot() -> _CpuSnapshot:
    total_ticks, steal_ticks = _cpu_times(_read_text(Path("/proc/stat")))
    return _CpuSnapshot(
        captured_at=time.perf_counter(),
        total_ticks=total_ticks,
        steal_ticks=steal_ticks,
        pressure_some_microseconds=_cpu_pressure_total(
            _read_text(Path("/proc/pressure/cpu"))
        ),
    )


def _cpu_times(stat: str) -> tuple[int | None, int | None]:
    """Parse aggregate CPU and hypervisor steal ticks from Linux procfs."""
    first_line = stat.partition("\n")[0].split()
    if not first_line or first_line[0] != "cpu" or len(first_line) < 9:
        return None, None

    try:
        # guest and guest_nice are already included in user and nice respectively.
        times = [int(value) for value in first_line[1:9]]
    except ValueError:
        return None, None
    return sum(times), times[7]


def _cpu_pressure_total(pressure: str) -> int | None:
    """Parse cumulative microseconds with runnable tasks waiting for CPU."""
    for line in pressure.splitlines():
        fields = line.split()
        if fields and fields[0] == "some":
            for field in fields[1:]:
                key, separator, value = field.partition("=")
                if key == "total" and separator and value.isdigit():
                    return int(value)
    return None


def _cpu_steal_percent(start: _CpuSnapshot, end: _CpuSnapshot) -> float | None:
    if (
        start.total_ticks is None
        or start.steal_ticks is None
        or end.total_ticks is None
        or end.steal_ticks is None
    ):
        return None

    total_delta = end.total_ticks - start.total_ticks
    steal_delta = end.steal_ticks - start.steal_ticks
    if total_delta <= 0 or steal_delta < 0:
        return None
    return round(100 * steal_delta / total_delta, 3)


def _cpu_pressure_percent(start: _CpuSnapshot, end: _CpuSnapshot) -> float | None:
    if (
        start.pressure_some_microseconds is None
        or end.pressure_some_microseconds is None
    ):
        return None

    elapsed_microseconds = (end.captured_at - start.captured_at) * 1_000_000
    pressure_delta = (
        end.pressure_some_microseconds - start.pressure_some_microseconds
    )
    if elapsed_microseconds <= 0 or pressure_delta < 0:
        return None
    return round(min(100.0, 100 * pressure_delta / elapsed_microseconds), 3)
