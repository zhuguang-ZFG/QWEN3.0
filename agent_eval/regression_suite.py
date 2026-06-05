"""Regression suite for tracking and running test entries."""

from dataclasses import dataclass, field


@dataclass
class RegressionEntry:
    """A single regression test entry."""

    name: str
    test_command: str
    expected_pass: bool


@dataclass
class RegressionSuite:
    """Collection of regression entries with run capability."""

    entries: list[RegressionEntry] = field(default_factory=list)

    def add(self, entry: RegressionEntry) -> None:
        """Add a regression entry to the suite."""
        self.entries.append(entry)

    def run_all(self) -> list[tuple[str, bool]]:
        """Run all entries and return (name, actual_pass) tuples.

        STUB: returns expected_pass as actual result.
        Real execution deferred to LiMa worker.
        Do NOT use all_passed() as a real promotion gate until
        this stub is replaced with actual test execution.
        """
        return [(e.name, e.expected_pass) for e in self.entries]

    def all_passed(self) -> bool:
        """Check if all entries passed. WARNING: stub — always reflects expected_pass."""
        results = self.run_all()
        return all(passed for _, passed in results)
