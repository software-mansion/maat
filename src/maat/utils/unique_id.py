import time
import socket
import os
import threading

_current_id = 0


def unique_id() -> int:
    """
    Generates a process-wide unique integer ID.
    The ID will always be greater than `0`.
    """
    global _current_id
    _current_id += 1
    return _current_id


# Constants for the Snowflake algorithm.
EPOCH = 1609459200000  # Custom epoch (January 1, 2021 in milliseconds).
TIMESTAMP_BITS = 41  # Bits for timestamp.
MACHINE_ID_BITS = 10  # Bits for machine ID.
SEQUENCE_BITS = 12  # Bits for sequence number.
MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1

# Global variables.
_last_timestamp = -1
_sequence = 0
_lock = threading.Lock()


def _get_machine_id():
    """Generate a machine ID based on host and process ID."""
    machine_hash = hash(socket.gethostname() + str(os.getpid()))
    return machine_hash & MAX_MACHINE_ID


# Initialize machine ID.
_machine_id = _get_machine_id()


def snowflake_id() -> int:
    """
    Generates a universe-wide unique integer ID.
    Uses Snowflake ID algorithm: https://en.wikipedia.org/wiki/Snowflake_ID.
    The ID will always be greater than `0`.
    """
    global _last_timestamp, _sequence

    with _lock:
        current_timestamp = int(time.time() * 1000) - EPOCH

        # Handle clock going backwards.
        if current_timestamp < _last_timestamp:
            # Wait until we reach the last timestamp.
            time.sleep((_last_timestamp - current_timestamp) / 1000.0)
            current_timestamp = int(time.time() * 1000) - EPOCH

        # Same millisecond, increment sequence.
        if current_timestamp == _last_timestamp:
            _sequence = (_sequence + 1) & MAX_SEQUENCE
            # Sequence overflow, wait for the next millisecond.
            if _sequence == 0:
                while current_timestamp <= _last_timestamp:
                    current_timestamp = int(time.time() * 1000) - EPOCH
        # Different millisecond, reset sequence.
        else:
            _sequence = 0

        _last_timestamp = current_timestamp

        # Combine all parts into a 64-bit ID.
        return (
            (current_timestamp << (MACHINE_ID_BITS + SEQUENCE_BITS))
            | (_machine_id << SEQUENCE_BITS)
            | _sequence
        )
