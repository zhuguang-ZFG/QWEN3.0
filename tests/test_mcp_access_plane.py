from lima_mcp.access_plane import (
    ConnectorPolicy,
    ConnectorStatus,
    enabled_connectors,
    validate_connector_policy,
)


def test_foundation_connectors_are_enabled_read_only_and_valid():
    names = {policy.name for policy in enabled_connectors()}
    assert {"filesystem_read", "git_read", "docs_lookup", "memory_query"} <= names

    for name in names:
        policy = validate_connector_policy(name)
        assert policy is not None
        assert policy.is_read_only()
        assert policy.owner
        assert policy.allowlist
        assert policy.audit_events


def test_gated_connectors_are_default_off_and_not_valid_until_owned():
    for name in ("filesystem_write", "git_write", "database_read", "cloud_api"):
        assert validate_connector_policy(name) is None


def test_enabled_connector_without_allowlist_is_invalid(monkeypatch):
    from lima_mcp import access_plane

    monkeypatch.setitem(
        access_plane.FOUNDATION_CONNECTORS,
        "broken_read",
        ConnectorPolicy(
            name="broken_read",
            status=ConnectorStatus.READ_ONLY,
            owner="lima-server",
            allowlist=[],
        ),
    )

    assert validate_connector_policy("broken_read") is None


def test_unknown_connector_policy_is_invalid():
    assert validate_connector_policy("missing") is None
