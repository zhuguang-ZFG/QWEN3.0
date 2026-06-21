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
    settings_logic_text = (ROOT / "src/composables/settings/useSettingsPage.ts").read_text(encoding="utf-8")
    utils_text = (ROOT / "src/utils/index.ts").read_text(encoding="utf-8")
    utils_env_text = (ROOT / "src/utils/env.ts").read_text(encoding="utf-8")

    assert "VITE_LOGIN_URL = '/pages-sub/v2/login/index'" in env_text
    assert "VITE_SERVER_BASEURL = 'https://chat.donglicao.com'" in env_text
    assert "VITE_APP_PROXY=false" in env_text
    assert '"pagePath": "pages/v2/device-list/index"' in pages_text
    assert "pagePath: 'pages/v2/device-list/index'" in tabbar_text
    assert "'/pages/login/index'" not in request_text
    assert "'/pages-sub/v2/login/index'" in request_text
    assert "isValidServerBaseUrl" in utils_env_text
    assert "export * from './env'" in utils_text
    assert "/api/ping" not in settings_logic_text
    assert "/health" in settings_logic_text
    assert "/xiaozhi$" not in settings_text


def test_manager_mobile_wechat_env_points_to_lima():
    """WeChat mini-program develop/trial/release must default to LiMa, not xiaozhi laf.run."""
    utils_env_text = (ROOT / "src/utils/env.ts").read_text(encoding="utf-8")

    assert "VITE_SERVER_BASEURL__WEIXIN_DEVELOP = 'https://chat.donglicao.com'" in utils_env_text
    assert "VITE_SERVER_BASEURL__WEIXIN_TRIAL = 'https://chat.donglicao.com'" in utils_env_text
    assert "VITE_SERVER_BASEURL__WEIXIN_RELEASE = 'https://chat.donglicao.com'" in utils_env_text
    assert "VITE_UPLOAD_BASEURL__WEIXIN_DEVELOP = 'https://chat.donglicao.com/upload'" in utils_env_text
    assert "VITE_UPLOAD_BASEURL__WEIXIN_TRIAL = 'https://chat.donglicao.com/upload'" in utils_env_text
    assert "VITE_UPLOAD_BASEURL__WEIXIN_RELEASE = 'https://chat.donglicao.com/upload'" in utils_env_text
    assert "ukw0y1.laf.run" not in utils_env_text


def test_manager_mobile_default_avatar_does_not_use_xiaozhi_cdn():
    """Default avatar must be a local asset, not the retired xiaozhi laf.run CDN."""
    user_store_text = (ROOT / "src/store/user.ts").read_text(encoding="utf-8")

    assert "ukw0y1.laf.run" not in user_store_text
    assert "oss.laf.run" not in user_store_text
    assert "'/static/images/default-avatar.png'" in user_store_text


def test_manager_mobile_package_json_has_no_xiaozhi_branding():
    """Package metadata must reflect LiMa branding, not the upstream xiaozhi repo."""
    import json

    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    searchable = [
        pkg.get("name", ""),
        pkg.get("description", ""),
        pkg.get("homepage", ""),
        pkg.get("repository", ""),
        pkg.get("bugs", {}).get("url", ""),
        pkg.get("author", {}).get("email", ""),
    ]
    combined = "\n".join(searchable)

    assert "xiaozhi" not in combined
    assert "xinnan-tech" not in combined
    assert "laf.run" not in combined
    assert pkg.get("name") == "lima-manager-mobile"


def test_manager_mobile_upload_hook_points_to_lima_and_has_no_console_noise():
    """Upload hook must target LiMa /upload and avoid production console noise."""
    upload_hook_text = (ROOT / "src/hooks/useUpload.ts").read_text(encoding="utf-8")

    assert "getEnvBaseUploadUrl()" in upload_hook_text
    assert "console.log(" not in upload_hook_text
    assert "console.error(" not in upload_hook_text


def test_manager_mobile_legacy_auth_module_is_removed():
    """Legacy username/password/SMS auth pages and API must be deleted after v2 migration."""
    assert not (ROOT / "src/api/auth.ts").exists()
    assert not (ROOT / "src/pages/login/index.vue").exists()
    assert not (ROOT / "src/pages/register/index.vue").exists()
    assert not (ROOT / "src/pages/forgot-password/index.vue").exists()

    pages_text = (ROOT / "src/pages.json").read_text(encoding="utf-8")
    assert '"path": "pages/login/index"' not in pages_text
    assert '"path": "pages/register/index"' not in pages_text
    assert '"path": "pages/forgot-password/index"' not in pages_text

    user_store_text = (ROOT / "src/store/user.ts").read_text(encoding="utf-8")
    config_store_text = (ROOT / "src/store/config.ts").read_text(encoding="utf-8")
    assert "@/api/auth" not in user_store_text
    assert "@/api/auth" not in config_store_text

    interceptor_text = (ROOT / "src/router/interceptor.ts").read_text(encoding="utf-8")
    page_auth_text = (ROOT / "src/hooks/usePageAuth.ts").read_text(encoding="utf-8")
    assert "userStore.userInfo.accountId" in interceptor_text
    assert "userStore.userInfo.accountId" in page_auth_text
    assert "userStore.userInfo.username" not in interceptor_text
    assert "userStore.userInfo.username" not in page_auth_text


def test_manager_mobile_chat_history_and_voiceprint_use_lima_native_api():
    """Chat history, messages and voiceprint APIs must target /device/v1/app, not legacy /agent paths."""
    chat_history_api_text = (ROOT / "src/api/chat-history/chat-history.ts").read_text(encoding="utf-8")
    voiceprint_api_text = (ROOT / "src/api/voiceprint/voiceprint.ts").read_text(encoding="utf-8")

    assert "/device/v1/app" in chat_history_api_text
    assert "/device/v1/app" in voiceprint_api_text
    assert "/agent/" not in chat_history_api_text
    assert "/agent/" not in voiceprint_api_text

    chat_detail_text = (ROOT / "src/pages-sub/chat-history/detail.vue").read_text(encoding="utf-8")
    assert "/agent/play/" not in chat_detail_text
    assert "getAudioPlayUrl" in chat_detail_text


def test_manager_mobile_legacy_device_agent_modules_are_removed():
    """Legacy agent/device pages and APIs must be deleted after v2 migration."""
    removed_paths = [
        ROOT / "src/api/agent",
        ROOT / "src/api/device",
        ROOT / "src/pages/agent",
        ROOT / "src/pages/device/index.vue",
        ROOT / "src/store/plugin.ts",
        ROOT / "src/store/provider.ts",
        ROOT / "src/store/speedPitch.ts",
    ]
    for path in removed_paths:
        assert not path.exists(), f"{path} should have been removed"

    pages_text = (ROOT / "src/pages.json").read_text(encoding="utf-8")
    removed_pages = [
        "pages/agent/edit",
        "pages/agent/index",
        "pages/agent/provider",
        "pages/agent/speedPitch",
        "pages/agent/tools",
        "pages/device/index",
    ]
    for page in removed_pages:
        assert f'"path": "{page}"' not in pages_text

    store_index_text = (ROOT / "src/store/index.ts").read_text(encoding="utf-8")
    assert "from './plugin'" not in store_index_text
    assert "from './provider'" not in store_index_text
    assert "from './speedPitch'" not in store_index_text


def test_manager_mobile_subpackage_and_webview_layout():
    """Non-tab pages live under pages-sub; webview is a first-class subpackage page."""
    assert (ROOT / "src/pages-sub/webview/index.vue").exists()
    assert (ROOT / "src/pages-sub/chat/chat.vue").exists()
    assert (ROOT / "src/composables/chat/useChatStream.ts").exists()

    pages_text = (ROOT / "src/pages.json").read_text(encoding="utf-8")
    assert '"subPackages"' in pages_text
    assert '"root": "pages-sub"' in pages_text
    assert '"path": "pages/chat/chat"' not in pages_text
    assert '"path": "chat/chat"' in pages_text

    app_text = (ROOT / "src/App.vue").read_text(encoding="utf-8")
    assert "console.log(" not in app_text
    assert "console.error(" not in app_text
    assert "updateTabBarText" in app_text

    utils_url_text = (ROOT / "src/utils/url.ts").read_text(encoding="utf-8")
    assert "import { pages, subPackages }" in utils_url_text
    assert "export const safeSubPackages = subPackages" in utils_url_text


def test_manager_mobile_voiceprint_page_uses_composable():
    """Voiceprint page logic lives in composable; playback must not use legacy /agent/play/."""
    page_text = (ROOT / "src/pages-sub/voiceprint/index.vue").read_text(encoding="utf-8")
    composable_text = (ROOT / "src/composables/voiceprint/useVoicePrintPage.ts").read_text(encoding="utf-8")

    assert "useVoicePrintPage" in page_text
    assert "getVoicePrintList" not in page_text
    assert "/agent/play/" not in composable_text
    assert "getAudioDownloadId(currentAgentId.value, audioId)" in composable_text


def test_manager_mobile_static_assets_size_budget():
    """Mini-program static/ must not bundle duplicate app icons or oversized PNGs."""
    static_root = ROOT / "src/static"
    assert not (static_root / "app").exists(), "src/static/app duplicates unpackage/res/icons"

    max_png_kb = 50
    oversized = []
    for png in static_root.rglob("*.png"):
        size_kb = png.stat().st_size / 1024
        if size_kb > max_png_kb:
            oversized.append(f"{png.relative_to(static_root)} ({size_kb:.1f} KB)")
    assert not oversized, f"PNG exceeds {max_png_kb} KB budget: {', '.join(oversized)}"

    tabbar_dir = static_root / "tabbar"
    allowed_tabbar = {
        "home.png",
        "homeHL.png",
        "robot.png",
        "robot_activate.png",
        "network.png",
        "network_activate.png",
        "system.png",
        "system_activate.png",
    }
    actual_tabbar = {p.name for p in tabbar_dir.glob("*.png")}
    assert actual_tabbar == allowed_tabbar


def test_manager_mobile_device_config_components_use_composables():
    """Large device-config components delegate logic to composables."""
    wifi_text = (ROOT / "src/pages/device-config/components/wifi-selector.vue").read_text(encoding="utf-8")
    ultrasonic_text = (ROOT / "src/pages/device-config/components/ultrasonic-config.vue").read_text(encoding="utf-8")

    assert "useWifiSelector" in wifi_text
    assert "parseWifiScanResponse" not in wifi_text
    assert "useUltrasonicConfig" in ultrasonic_text
    assert "generateUltrasonicWavDataUri" not in ultrasonic_text
    assert (ROOT / "src/composables/device-config/ultrasonicAfsk.ts").exists()
    assert (ROOT / "src/composables/device-config/parseWifiScanResponse.ts").exists()


def test_manager_mobile_mp_weixin_build_size_budget():
    """Production mp-weixin output should stay within the post-optimization budget."""
    dist_root = ROOT / "dist/build/mp-weixin"
    assert dist_root.is_dir(), "run pnpm build:mp-weixin before this test"

    total_bytes = sum(p.stat().st_size for p in dist_root.rglob("*") if p.is_file())
    max_total_kb = 900
    assert total_bytes / 1024 <= max_total_kb, f"mp-weixin build {total_bytes / 1024:.1f} KB exceeds {max_total_kb} KB"
