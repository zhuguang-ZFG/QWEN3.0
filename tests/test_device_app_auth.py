"""Tests for device_app_auth routes — WeChat login + me + delete (slimdown P2-16).

手机号+短信鉴权（/auth/register、/auth/sms-verification、/auth/captcha、/auth/login 的
phone 分支）已于 2026-07-02 弃用移除。本文件保留并改写为微信一键登录路径的测试。
邮箱鉴权（/auth/login-email、/auth/register-email）的测试在 test_routes_device_app_auth.py
与 device_app_auth_email 相关测试中。
"""

from device_logic.db import connect
from device_app_helpers import client as make_client
from device_app_helpers import seed_account_and_device


def _enable_wechat_dev_login(monkeypatch):
    """Configure dev-mode WeChat login (code -> wx:<code> openid) for tests."""
    monkeypatch.setenv("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", "1")


def test_device_app_auth_rejects_wechat_code_login_without_dev_flag(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.delenv("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", raising=False)

    logged_in = client.post("/device/v1/app/auth/login", json={"code": "wx-code-1"})
    assert logged_in.status_code == 503


def test_device_app_auth_wechat_login_with_real_config(tmp_path, monkeypatch):
    from config import settings
    import device_logic.wechat_gateway as wechat_gateway

    monkeypatch.setattr(settings.WECHAT, "miniapp_appid", "wxappid")
    monkeypatch.setattr(settings.WECHAT, "miniapp_secret", "secret")
    monkeypatch.delenv("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", raising=False)

    original_jscode2session = wechat_gateway.WechatMiniappGateway.jscode2session

    async def fake_jscode2session(self, code):
        if code == "valid-code":
            return {"openid": "o-real", "session_key": "sk", "unionid": ""}
        raise wechat_gateway.WechatLoginError("invalid code")

    monkeypatch.setattr(wechat_gateway.WechatMiniappGateway, "jscode2session", fake_jscode2session)

    try:
        client, _store = make_client(tmp_path, monkeypatch)
        logged_in = client.post("/device/v1/app/auth/login", json={"code": "valid-code"})
        assert logged_in.status_code == 200, logged_in.text
        assert logged_in.json()["accountId"]
        assert logged_in.json()["token"]

        bad = client.post("/device/v1/app/auth/login", json={"code": "bad-code"})
        assert bad.status_code == 401
    finally:
        monkeypatch.setattr(wechat_gateway.WechatMiniappGateway, "jscode2session", original_jscode2session)


def test_device_app_auth_wechat_login_me_and_delete_flow(tmp_path, monkeypatch):
    """WeChat login → /auth/me → bind device → /auth/account/delete 全流程。

    改写自原 register_login_sms_me_and_delete_flow，走微信路径覆盖 me/delete 端点
    （这两个端点对微信和邮箱登录通用）。
    """
    _enable_wechat_dev_login(monkeypatch)
    client, _store = make_client(tmp_path, monkeypatch)

    logged_in = client.post("/device/v1/app/auth/login", json={"code": "wx-flow-1"})
    assert logged_in.status_code == 200, logged_in.text
    login_data = logged_in.json()
    assert login_data["accountId"]
    assert login_data["token"]

    me = client.get("/device/v1/app/auth/me", headers={"Authorization": f"Bearer {login_data['token']}"})
    assert me.status_code == 200, me.text
    assert me.json()["accountId"] == login_data["accountId"]

    seed_account_and_device(device_id="d-auth", device_sn="SN-AUTH-01")
    with connect() as conn:
        conn.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) VALUES ('b-auth', 'd-auth', ?, 'owner', 'active')",
            (login_data["accountId"],),
        )
        conn.commit()

    deleted = client.post(
        "/device/v1/app/auth/account/delete", headers={"Authorization": f"Bearer {login_data['token']}"}
    )
    assert deleted.status_code == 200, deleted.text
    with connect() as conn:
        account = conn.execute("SELECT * FROM v2_account WHERE id=?", (login_data["accountId"],)).fetchone()
        binding = conn.execute("SELECT * FROM v2_device_binding WHERE id='b-auth'").fetchone()
    assert account["status"] == "deleted"
    assert binding["status"] == "unbound"


def test_device_app_auth_login_rate_limited(tmp_path, monkeypatch):
    """登录限流对微信路径同样生效（替代原 register_rate_limited）。"""
    import rate_limiter

    rate_limiter.reset()
    _enable_wechat_dev_login(monkeypatch)
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_DEVICE_AUTH_LOGIN_PER_MIN", "2")

    for idx in range(2):
        response = client.post("/device/v1/app/auth/login", json={"code": f"wx-rl-{idx}"})
        assert response.status_code == 200, response.text

    blocked = client.post("/device/v1/app/auth/login", json={"code": "wx-rl-blocked"})
    assert blocked.status_code == 429


def test_device_app_auth_login_requires_code(tmp_path, monkeypatch):
    """无 code 字段返回 400。"""
    _enable_wechat_dev_login(monkeypatch)
    client, _store = make_client(tmp_path, monkeypatch)

    response = client.post("/device/v1/app/auth/login", json={})
    assert response.status_code == 400
