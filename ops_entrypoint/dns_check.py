from dataclasses import dataclass


@dataclass(frozen=True)
class EndpointRecord:
    name: str
    base_url: str
    owner: str
    health_path: str
    public: bool


def validate_endpoint_records(records: list[EndpointRecord]) -> list[str]:
    problems: list[str] = []
    for record in records:
        if record.owner != "lima":
            problems.append(f"{record.name}: owner must be lima")
        if not record.health_path:
            problems.append(f"{record.name}: missing health_path")
        if record.public and not record.base_url.startswith("https://"):
            problems.append(f"{record.name}: public endpoint must use https")
    return problems
