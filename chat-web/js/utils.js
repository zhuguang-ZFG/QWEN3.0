/* Shared Chat Web utilities — canonical escaping + URL allow-listing.
 *
 * P3.2: escapeHtml / escapeAttr / isAllowedImageUrl were previously copy-pasted
 * across 8 files with subtly different bodies (some escaped `'` and backtick,
 * some did not). That inconsistency is an XSS foot-gun. This module is the
 * single source of truth; all consumers read from window.LiMaUtils.
 *
 * Loaded as a classic script (IIFE global) to match the rest of chat-web —
 * no module system. Must load before any consumer script in each HTML page.
 */
(function (global) {
  "use strict";

  // Escape for HTML text context. Covers &, <, >, ", ', and backtick — the
  // superset of every prior local copy, so no consumer loses coverage.
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/`/g, "&#96;");
  }

  // Escape for HTML attribute context (URL values etc.).
  function escapeAttr(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Allow-list image URLs: only http(s) on known LiMa image hosts.
  const ALLOWED_IMAGE_DOMAINS = [
    "image.pollinations.ai",
    "chat.donglicao.com",
    "api.donglicao.com",
  ];
  function isAllowedImageUrl(url) {
    try {
      const u = new URL(url);
      if (u.protocol !== "http:" && u.protocol !== "https:") return false;
      return ALLOWED_IMAGE_DOMAINS.some((domain) => u.hostname === domain);
    } catch {
      return false;
    }
  }

  global.LiMaUtils = {
    escapeHtml,
    escapeAttr,
    isAllowedImageUrl,
    ALLOWED_IMAGE_DOMAINS,
  };
})(window);
