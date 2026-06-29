/* Minimal API client for LiMa chat-web. */

(function () {
  "use strict";

  const API_BASE = "";

  window.LiMaAPI = {
    base: API_BASE,

    async post(path, body, token) {
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = "Bearer " + token;
      const res = await fetch(API_BASE + path, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = data.message || data.error || res.statusText;
        throw new Error(msg);
      }
      return data;
    },

    async get(path, token) {
      const headers = {};
      if (token) headers["Authorization"] = "Bearer " + token;
      const res = await fetch(API_BASE + path, { headers });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.message || data.error || res.statusText);
      }
      return data;
    },

    async del(path, token) {
      const headers = {};
      if (token) headers["Authorization"] = "Bearer " + token;
      const res = await fetch(API_BASE + path, { method: "DELETE", headers });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.message || data.error || res.statusText);
      }
      return data;
    },

    async put(path, body, token) {
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = "Bearer " + token;
      const res = await fetch(API_BASE + path, {
        method: "PUT",
        headers,
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.message || data.error || res.statusText);
      }
      return data;
    },
  };

  /* ─── Enhanced Toast (P1) ─── */
  var _toastEl = null;
  var _toastTimer = null;
  var _progressRAF = null;

  var ICON_SVG = {
    success: '<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
    error:   '<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    warning: '<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    info:    '<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
  };

  function _ensureToast() {
    if (_toastEl) return _toastEl;
    var el = document.createElement("div");
    el.className = "toast";
    el.setAttribute("role", "alert");
    el.innerHTML =
      '<div class="toast-icon"></div>' +
      '<div class="toast-body"></div>' +
      '<div class="toast-progress"></div>';
    document.body.appendChild(el);
    _toastEl = el;
    return el;
  }

  function _cancelTimers() {
    if (_toastTimer) { clearTimeout(_toastTimer); _toastTimer = null; }
    if (_progressRAF) { cancelAnimationFrame(_progressRAF); _progressRAF = null; }
  }

  /**
   * Show an enhanced toast notification.
   * @param {string} message
   * @param {object} [opts]
   * @param {string} [opts.type] - "success" | "error" | "warning" | "info" (default: "info")
   * @param {number} [opts.duration] - ms before auto-hide (default: 3500)
   */
  window.LiMaToast = function (message, opts) {
    opts = opts || {};
    var type = opts.type || (opts.error ? "error" : "info");
    var duration = opts.duration || 3500;

    _cancelTimers();
    var el = _ensureToast();
    var iconEl = el.querySelector(".toast-icon");
    var bodyEl = el.querySelector(".toast-body");
    var progressEl = el.querySelector(".toast-progress");

    el.className = "toast " + type;
    iconEl.innerHTML = ICON_SVG[type] || ICON_SVG.info;
    bodyEl.textContent = message;
    progressEl.style.width = "100%";

    /* Force reflow then show */
    void el.offsetWidth;
    el.classList.add("show");

    /* Animate progress bar */
    var start = performance.now();
    function tick(now) {
      var elapsed = now - start;
      var pct = Math.max(0, 1 - elapsed / duration) * 100;
      progressEl.style.width = pct + "%";
      if (elapsed < duration) {
        _progressRAF = requestAnimationFrame(tick);
      }
    }
    _progressRAF = requestAnimationFrame(tick);

    /* Auto-hide */
    _toastTimer = setTimeout(function () {
      el.classList.remove("show");
      _progressRAF = null;
    }, duration);
  };
})();
