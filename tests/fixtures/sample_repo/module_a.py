"""Sample module A - imports from module_b and defines a class."""

from sample_repo.module_b import helper_function


class Calculator:
    """A simple calculator class for testing AST extraction."""

    def __init__(self, initial: int = 0):
        self.value = initial

    def add(self, amount: int) -> int:
        """Add amount to current value."""
        self.value += amount
        return self.value

    def subtract(self, amount: int) -> int:
        self.value -= amount
        return self.value

    def get_value(self) -> int:
        return self.value


def calculate_sum(items: list[int]) -> int:
    """Sum a list of integers using helper_function."""
    return helper_function(items)
