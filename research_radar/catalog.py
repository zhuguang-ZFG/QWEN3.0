"""In-memory research source catalog.

The catalog registers, searches, and filters external reference sources without
network or database dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from research_radar.source import AdoptionState, LicenseClass, SourceRecord


@dataclass
class SourceCatalog:
    sources: dict[str, SourceRecord] = field(default_factory=dict)

    def register(self, source: SourceRecord) -> None:
        if source.source_id in self.sources:
            raise ValueError(f"duplicate source_id: {source.source_id}")
        self.sources[source.source_id] = source

    def get(self, source_id: str) -> SourceRecord | None:
        return self.sources.get(source_id)

    def search(self, query: str, limit: int = 20) -> list[SourceRecord]:
        terms = query.lower().split()
        if not terms or limit <= 0:
            return []
        scored = []
        for source in self.sources.values():
            haystack = " ".join([
                source.name,
                source.description,
                source.subsystem,
                source.notes,
                *source.tags,
                source.license_class.value,
                source.adoption_state.value,
            ]).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, source.source_id, source))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [source for _, _, source in scored[:limit]]

    def filter_by_subsystem(self, subsystem: str) -> list[SourceRecord]:
        return [
            source for source in self.sources.values()
            if source.subsystem == subsystem
        ]

    def filter_by_adoption(self, state: AdoptionState) -> list[SourceRecord]:
        return [
            source for source in self.sources.values()
            if source.adoption_state == state
        ]

    def filter_by_license(self, license_class: LicenseClass) -> list[SourceRecord]:
        return [
            source for source in self.sources.values()
            if source.license_class == license_class
        ]

    def filter_by_tag(self, tag: str) -> list[SourceRecord]:
        tag_lower = tag.lower()
        return [
            source for source in self.sources.values()
            if tag_lower in {item.lower() for item in source.tags}
        ]

    def count_by_subsystem(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for source in self.sources.values():
            counts[source.subsystem] = counts.get(source.subsystem, 0) + 1
        return dict(sorted(counts.items()))

    def count_by_adoption(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for source in self.sources.values():
            key = source.adoption_state.value
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def __len__(self) -> int:
        return len(self.sources)


def build_default_catalog() -> SourceCatalog:
    """Build a catalog seeded with known LiMa research references."""
    from research_radar.seed import SEED_SOURCES

    catalog = SourceCatalog()
    for source in SEED_SOURCES:
        catalog.register(source)
    return catalog
