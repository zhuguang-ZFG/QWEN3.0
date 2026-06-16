from scripts.check_vps_environment import build_report


def test_vps_environment_check_redacts_secret_values(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "secret-value")
    (tmp_path / ".env").write_text("LIMA_ADMIN_TOKEN=another-secret\n", encoding="utf-8")

    report = build_report(tmp_path)

    text = str(report)
    assert report["secrets_present"]["LIMA_API_KEY"] is True
    assert report["secrets_present"]["LIMA_ADMIN_TOKEN"] is True
    assert "secret-value" not in text
    assert "another-secret" not in text
