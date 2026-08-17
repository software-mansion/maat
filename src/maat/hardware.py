import os
import platform
import re
from typing import Self

from pydantic import BaseModel


class HardwareEnvironment(BaseModel):
    os: str
    arch: str
    cpu_model: str | None
    cpu_count: int | None
    memory_total_mb: int | None
    ci: bool

    @classmethod
    def capture(cls) -> Self:
        try:
            return cls(
                os=f"{platform.system()} {platform.release()}",
                arch=platform.machine(),
                cpu_model=_cpu_model(),
                cpu_count=os.cpu_count(),
                memory_total_mb=_memory_total_mb(),
                ci=os.environ.get("GITHUB_ACTIONS") == "true",
            )
        except Exception:
            return cls(
                os="unknown",
                arch="unknown",
                cpu_model=None,
                cpu_count=None,
                memory_total_mb=None,
                ci=False,
            )


def _cpu_model() -> str | None:
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
        elif platform.system() == "Darwin":
            import subprocess

            return (
                subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"])
                .decode("utf-8")
                .strip()
            )
    except Exception:
        pass
    return None


def _memory_total_mb() -> int | None:
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        match = re.search(r"(\d+)", line)
                        if match is None:
                            return None
                        return int(match.group(1)) // 1024
        elif platform.system() == "Darwin":
            import subprocess

            total_bytes = int(
                subprocess.check_output(["sysctl", "-n", "hw.memsize"])
                .decode("utf-8")
                .strip()
            )
            return total_bytes // (1024 * 1024)
    except Exception:
        pass
    return None
