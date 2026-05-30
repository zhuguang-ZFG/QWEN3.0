from scripts.sanitize_vps_service_env import sanitize_unit_text


def test_sanitize_unit_text_removes_secret_environment_lines():
    original = "\n".join([
        "[Service]",
        "EnvironmentFile=/opt/lima-router/.env",
        "Environment=LIMA_API_KEY=secret",
        "Environment=LIMA_API_KEYS=secret",
        "Environment=LIMA_V3=1",
    ])

    sanitized, removed = sanitize_unit_text(original)

    assert removed == 2
    assert "LIMA_API_KEY=secret" not in sanitized
    assert "LIMA_API_KEYS=secret" not in sanitized
    assert "Environment=LIMA_V3=1" in sanitized
