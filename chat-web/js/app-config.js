/* Endpoint selection for LiMa chat-web.
 *
 * 所有请求统一走主节点 chat.donglicao.com（由 CF Worker 回源到 JDCloud）。
 * 历史：曾把匿名简单 chat 分流到 Aliyun pilot，该链路 2026-07-05 退役、
 * 死配置于 2026-07-06 清理，分流逻辑已移除，统一走主节点。
 * shouldUsePilot 恒返回 false，保留仅为兼容 chat-api.js 现有调用。
 */
(function () {
  "use strict";

  const PRIMARY_ORIGIN = "https://chat.donglicao.com";

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

  function shouldUsePilot(_path, _body) {
    // pilot 分流已退役：所有请求统一走主节点，恒返回 false。
    return false;
  }

  function getApiUrl(path, _body) {
    return PRIMARY_ORIGIN + path;
  }

  window.LiMaConfig = {
    PRIMARY_ORIGIN,
    getApiKey,
    isAnonymous,
    shouldUsePilot,
    getApiUrl,
  };
})();
