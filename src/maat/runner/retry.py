import time
import random
from functools import wraps
from typing import TypeVar, Callable, ParamSpec

T = TypeVar("T")
P = ParamSpec("P")


def retry(
    max_retries: int = 5,
    initial_backoff: float = 0.1,
    max_backoff: float = 5.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that retries the decorated function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff time in seconds
        max_backoff: Maximum backoff time in seconds
        backoff_factor: Factor by which to increase backoff with each attempt
        jitter: Whether to add random jitter to backoff time

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            backoff = initial_backoff

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt == max_retries:
                        raise last_exception

                    # Calculate backoff time with optional jitter
                    if jitter:
                        sleep_time = backoff * (0.5 + random.random())
                    else:
                        sleep_time = backoff

                    sleep_time = min(sleep_time, max_backoff)

                    time.sleep(sleep_time)

                    # Increase backoff for next iteration
                    backoff = min(backoff * backoff_factor, max_backoff)

            # This should never be reached due to the max_retries check above
            assert False, "Unexpected code path"

        return wrapper

    return decorator
