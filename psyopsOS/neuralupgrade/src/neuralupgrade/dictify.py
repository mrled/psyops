from dataclasses import asdict, is_dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class Dictifiable(Protocol):
    """Protocol for objects that can be converted to a dictionary."""

    def dictify(self) -> dict:
        """Convert the object to a dictionary."""
        pass


def dictify(obj):
    """Convert an object to a dictionary, recursively.

    This function understands:
    - dataclasses
    - Dictify protocol
    """

    allowed_atomics = (str, int, float, bool, type(None))

    if is_dataclass(obj):
        return {k: dictify(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, Dictifiable):
        return {k: dictify(v) for k, v in obj.dictify().items()}
    elif isinstance(obj, dict):
        return {k: dictify(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [dictify(v) for v in obj]
    elif isinstance(obj, allowed_atomics):
        return obj
    else:
        raise TypeError(
            f"Unsupported type {type(obj)} for dictification. Must be one of {allowed_atomics}, dict, list, dataclass, or implement Dictifiable."
        )
