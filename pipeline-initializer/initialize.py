"""Normalization of the state machine's execution input."""

DEFAULT_REBUILD = False
DEFAULT_NUM_EXECUTORS = 1

FIELDS = ("rebuild", "num_executors")


class InvalidInputError(ValueError):
    """The execution input could not be normalized."""


def normalize(event):
    """Fill in the defaults and reject anything the pipeline cannot use."""
    event = event or {}
    if not isinstance(event, dict):
        raise InvalidInputError(
            f"execution input must be an object, got {type(event).__name__}"
        )

    rebuild = event.get("rebuild", DEFAULT_REBUILD)
    if not isinstance(rebuild, bool):
        raise InvalidInputError(f"rebuild must be a boolean, got {rebuild!r}")

    num_executors = event.get("num_executors", DEFAULT_NUM_EXECUTORS)
    # bool is a subclass of int -- True must not pass as a count.
    if isinstance(num_executors, bool) or not isinstance(num_executors, int):
        raise InvalidInputError(
            f"num_executors must be an integer, got {num_executors!r}"
        )
    if num_executors < 1:
        raise InvalidInputError(
            f"num_executors must be at least 1, got {num_executors}"
        )

    return {"rebuild": rebuild, "num_executors": num_executors}


def unknown_fields(event):
    """Fields the initializer drops -- logged, not an error."""
    if not isinstance(event, dict):
        return []
    return sorted(set(event) - set(FIELDS))
