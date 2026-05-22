from ops_entrypoint.dns_check import EndpointRecord, validate_endpoint_records


def test_validate_endpoint_records_requires_owned_domain_and_health_path():
    records = [
        EndpointRecord(
            name="primary",
            base_url="https://chat.donglicao.com",
            owner="lima",
            health_path="/health",
            public=True,
        )
    ]

    problems = validate_endpoint_records(records)

    assert problems == []


def test_validate_endpoint_records_rejects_missing_health_path():
    records = [
        EndpointRecord(
            name="broken",
            base_url="https://example.com",
            owner="unknown",
            health_path="",
            public=True,
        )
    ]

    problems = validate_endpoint_records(records)

    assert "broken: missing health_path" in problems
    assert "broken: owner must be lima" in problems
