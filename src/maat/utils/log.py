import time
from contextlib import contextmanager
from datetime import timedelta

from maat.runner.cancellation_token import CancelledException

_start = time.perf_counter()


def elapsed(start: float) -> timedelta:
    return timedelta(seconds=round(time.perf_counter() - start))


def uptime() -> timedelta:
    return elapsed(_start)


def log(*args):
    print(f"[{str(uptime())}]", flush=True, *args)


@contextmanager
def track(name: str):
    start = time.perf_counter()
    log("▶️", name)
    try:
        yield
        log("✅", name, "in", elapsed(start))
    except (CancelledException, KeyboardInterrupt):
        log("🚫", name, "in", elapsed(start))
        raise
    except Exception as e:
        log("❌", name, f"({type(e).__name__})", "in", elapsed(start))
        raise
