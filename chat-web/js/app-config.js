/* Endpoint selection for LiMa chat-web.
 *
 * 所有请求统一走主节点 chat.donglicao.com（由 CF Worker 回源到 JDCloud）。
 * 历史：曾把匿名简单 chat 分流到 Aliyun pilot，该链路 2026-07-05 退役后
 * shouldUsePilot 恒返回 false；接口保留以兼容 chat-api.js 现有调用。
 */
(function () {
  "use strict";

  const PRIMARY_ORIGIN = "https://chat.donglicao.com";
  const PILOT_ORIGIN = "https://aliyun.donglicao.com";
  const DEFAULT_CHAT_MODELS = new Set(["lima", "lima-1.3"]);

  function getApiKey() {
    try {
      return sessionStorage.getItem("lima-api-key") || "";
    } catch {
      return "";
    }
  }

  function isAnonymous() {
    return !getApiKey();
  }

  function hasImageContent(messages) {
    if (!Array.isArray(messages)) return false;
    for (const m of messages) {
      const content = m && m.content;
      if (Array.isArray(content)) {
        for (const block of content) {
          if (block && (block.type === "image" || block.type === "image_url")) {
            return true;
          }
        }
      }
    }
    return false;
  }

  function isDefaultChatModel(model) {
    return DEFAULT_CHAT_MODELS.has(model);
  }

  function shouldUsePilot(_path, _body) {
    // Aliyun pilot 免费 chat 链路已退役（2026-07-05）：匿名 chat 统一走主节点。
    // 保留函数与 window.LiMaConfig 接口以兼容 chat-api.js 现有调用，恒返回 false。
    return false;
  }

  function getApiOrigin(path, body) {
    return shouldUsePilot(path, body) ? PILOT_ORIGIN : PRIMARY_ORIGIN;
  }

  function getApiUrl(path, body) {
    return getApiOrigin(path, body) + path;
  }

  window.LiMaConfig = {
    PRIMARY_ORIGIN,
    PILOT_ORIGIN,
    getApiKey,
    isAnonymous,
    shouldUsePilot,
    getApiOrigin,
    getApiUrl,
  };
})();
