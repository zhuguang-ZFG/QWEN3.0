/* Endpoint selection for LiMa chat-web.
 *
 * Anonymous simple chat requests can be routed to the Aliyun pilot node
 * (free/low-cost backends only). Everything else stays on the primary
 * JDCloud node served through chat.donglicao.com.
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

  function shouldUsePilot(path, body) {
    if (path !== "/v1/chat/completions") return false;
    if (!isAnonymous()) return false;
    if (!body || typeof body !== "object") return false;
    if (!isDefaultChatModel(body.model)) return false;
    if (body.tools || body.tool_choice) return false;
    if (hasImageContent(body.messages)) return false;
    return true;
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
