"""Sample module B - a utility module imported by module_a."""


def helper_function(items: list[int]) -> int:
    """Return sum of all items in the list."""
    return sum(items)


def another_helper(text: str) -> str:
    """Reverse a string."""
    return text[::-1]


class UtilityClass:
    """A utility class used internally."""

    def __init__(self):
        self.calls = 0

    def invoke(self) -> int:
        self.calls += 1
        return self.calls
