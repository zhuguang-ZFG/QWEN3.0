(function () {
  "use strict";

  window.LIMA_CONFIG = {
    apiOrigin: "https://chat.donglicao.com",
    wsOrigin: "wss://chat.donglicao.com",
  };

  // ponytail: 当 chat-web 托管在 app.donglicao.com 时，把相对 API 路径重定向到
  // 主 API 源站。拦截范围限定为 /v1/、/device/v1/、/api/；若后续增加非 API
  // 的相对路径 fetch，会被误改，需改为显式前缀或扩展白名单。升级路径：所有调用
  // 改为显式 window.LIMA_CONFIG.apiOrigin 前缀后，移除拦截器。
  if (location.host === "chat.donglicao.com") return;

  const API_PREFIXES = ["/v1/", "/device/v1/", "/api/"];

  const originalFetch = window.fetch;
  window.fetch = function (input, init) {
    if (typeof input === "string" && API_PREFIXES.some((p) => input.startsWith(p))) {
      input = window.LIMA_CONFIG.apiOrigin + input;
    }
    return originalFetch(input, init);
  };

  const OriginalWebSocket = window.WebSocket;
  window.WebSocket = function (url, protocols) {
    if (typeof url === "string" && url.startsWith("/device/v1/")) {
      url = window.LIMA_CONFIG.wsOrigin + url;
    }
    return new OriginalWebSocket(url, protocols);
  };
})();
