from device_gateway.protocol_families import (
    GATED_FAMILIES,
    ProtocolFamily,
    family_capabilities,
    family_is_active,
    validate_capability,
)


def test_only_motion_family_is_active():
    assert family_is_active("motion")
    for family in GATED_FAMILIES:
        assert not family_is_active(family)


def test_motion_capabilities_are_allowed():
    assert family_capabilities("motion") == frozenset({
        "run_path",
        "write_text",
        "draw_generated",
    })
    assert validate_capability("motion", "run_path")
    assert not validate_capability("motion", "stream_start")


def test_gated_family_capabilities_exist_but_family_is_inactive():
    assert "voice_clone" in family_capabilities(ProtocolFamily.SPEECH)
    assert validate_capability("speech", "voice_clone")
    assert not family_is_active("speech")


def test_unknown_family_has_no_capabilities():
    assert family_capabilities("unknown") == frozenset()
    assert not validate_capability("unknown", "anything")
