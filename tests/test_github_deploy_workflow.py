from pathlib import Path


def test_github_deploy_uses_unified_deploy_script():
    text = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")

    assert "scripts/deploy_unified.py" in text
    assert "scripts/deploy_jdcloud_probe.py" in text
    assert "Deploy JDCloud provider probe" in text
    assert "appleboy/scp-action" not in text
