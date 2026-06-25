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
  };
})();
