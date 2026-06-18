from pathlib import Path


ROOT = Path("esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile")


def test_manager_mobile_v2_api_uses_lima_native_paths():
    text = (ROOT / "src/api/v2/index.ts").read_text(encoding="utf-8")
    assert "/api/v1/" not in text
    assert "/device/v1/app" in text


def test_manager_mobile_defaults_to_lima_native_v2_entrypoints():
    env_text = (ROOT / "env/.env").read_text(encoding="utf-8")
    pages_text = (ROOT / "src/pages.json").read_text(encoding="utf-8")
    tabbar_text = (ROOT / "src/layouts/fg-tabbar/tabbarList.ts").read_text(encoding="utf-8")
    request_text = (ROOT / "src/http/request/alova.ts").read_text(encoding="utf-8")
    settings_text = (ROOT / "src/pages/settings/index.vue").read_text(encoding="utf-8")
    utils_text = (ROOT / "src/utils/index.ts").read_text(encoding="utf-8")

    assert "VITE_LOGIN_URL = '/pages/v2/login/index'" in env_text
    assert "VITE_SERVER_BASEURL = 'https://chat.donglicao.com'" in env_text
    assert "VITE_APP_PROXY=false" in env_text
    assert '"pagePath": "pages/v2/device-list/index"' in pages_text
    assert "pagePath: 'pages/v2/device-list/index'" in tabbar_text
    assert "'/pages/login/index'" not in request_text
    assert "'/pages/v2/login/index'" in request_text
    assert "isValidServerBaseUrl" in utils_text
    assert "/api/ping" not in settings_text
    assert "/health" in settings_text
    assert "/xiaozhi$" not in settings_text
