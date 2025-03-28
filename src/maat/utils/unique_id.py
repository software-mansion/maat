_current_id = 0


def unique_id() -> int:
    """
    Generates a globally unique integer ID.
    The ID will always be greater than `0`.
    """
    global _current_id
    _current_id += 1
    return _current_id
