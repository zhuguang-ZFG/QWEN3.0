import json

from scripts import check_jdcloud_node


def test_parse_remote_report_normalizes_numbers_and_statuses():
    report = check_jdcloud_node.parse_remote_report(
        "\n".join([
            "disk_free_mb=2048",
            "mem_available_mb=512",
            "loadavg=0.10 0.20 0.30",
            "lima_probe_timer=active",
            "lima_probe_service=inactive",
            "prometheus_service=active",
            "chat_health_http_code=200",
            "chat_prometheus_http_code=not_configured",
            "browser_health_http_code=200",
            "browser_ready_http_code=503",
            "browser_render_http_code=500",
        ])
    )

    assert report["disk_free_mb"] == 2048
    assert report["mem_available_mb"] == 512
    assert report["lima_probe_timer"] == "active"
    assert report["chat_health_http_code"] == 200
    assert report["chat_prometheus_http_code"] == "not_configured"
    assert report["browser_health_http_code"] == 200
    assert report["browser_ready_http_code"] == 503
    assert report["browser_render_http_code"] == 500


def test_build_result_is_sanitized_and_role_specific():
    result = check_jdcloud_node.build_result(
        host="117.72.118.95",
        user="root",
        report={
            "disk_free_mb": 2048,
            "mem_available_mb": 512,
            "loadavg": "0.10 0.20 0.30",
            "lima_probe_timer": "active",
            "lima_probe_service": "inactive",
            "prometheus_service": "active",
            "chat_health_http_code": 200,
            "chat_prometheus_http_code": "not_configured",
            "browser_health_http_code": 200,
            "browser_ready_http_code": 200,
            "browser_render_http_code": 200,
        },
    )
    text = json.dumps(result, ensure_ascii=False).lower()

    assert result["host"] == "117.72.118.95"
    assert result["user"] == "root"
    assert result["role"] == "secondary_probe_monitoring"
    assert result["disk_free_mb"] == 2048
    assert "password" not in text
    assert "token" not in text


def test_main_json_uses_read_only_check(monkeypatch, capsys):
    monkeypatch.setattr(
        check_jdcloud_node,
        "run_remote_check",
        lambda host, user, key_path, password, timeout: {
            "disk_free_mb": 2048,
            "mem_available_mb": 512,
            "loadavg": "0.10 0.20 0.30",
            "lima_probe_timer": "active",
            "lima_probe_service": "inactive",
            "prometheus_service": "active",
            "chat_health_http_code": 200,
            "chat_prometheus_http_code": "not_configured",
            "browser_health_http_code": 200,
            "browser_ready_http_code": 200,
            "browser_render_http_code": 200,
        },
    )

    assert check_jdcloud_node.main(["--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["host"] == "117.72.118.95"
    assert data["ok"] is True
    assert data["browser_render_http_code"] == 200


def test_main_json_reports_ssh_failure_without_secret(monkeypatch, capsys):
    def fail_check(host, user, key_path, password, timeout):
        raise RuntimeError("Authentication failed")

    monkeypatch.setattr(check_jdcloud_node, "run_remote_check", fail_check)

    assert check_jdcloud_node.main(["--json"]) == 3

    data = json.loads(capsys.readouterr().out)
    text = json.dumps(data).lower()
    assert data["ok"] is False
    assert data["error_class"] == "RuntimeError"
    assert "authentication failed" in data["error"].lower()
    assert "password" not in text
    assert "token" not in text
