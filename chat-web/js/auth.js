/* Authentication helpers for LiMa chat-web login/register pages. */

(function () {
  "use strict";

  const TOKEN_KEY = "lima_token";
  const LOGIN_PATH = "/device/v1/app/auth/login-email";
  const REGISTER_PATH = "/device/v1/app/auth/register-email";
  const SENSITIVE_KEYS = [
    TOKEN_KEY,
    "lima-api-key",
    "lima_api_key",
    "lima_sessions",
    "lima_playground_history",
  ];

  function getToken() {
    try {
      return sessionStorage.getItem(TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  function setToken(token) {
    try {
      sessionStorage.setItem(TOKEN_KEY, token);
    } catch {}
  }

  function removeToken() {
    try {
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {}
  }

  function clearSensitiveStorage() {
    for (const key of SENSITIVE_KEYS) {
      try {
        sessionStorage.removeItem(key);
        localStorage.removeItem(key);
      } catch {}
    }
  }

  function logout() {
    clearSensitiveStorage();
  }

  function isLoggedIn() {
    return !!getToken();
  }

  function redirectIfLoggedIn() {
    if (isLoggedIn()) {
      window.location.href = "index.html";
    }
  }

  function showError(el, message) {
    if (!el) return;
    el.textContent = message || "";
    el.hidden = !message;
  }

  async function login(email, password) {
    return window.LiMaAPI.post(LOGIN_PATH, { email, password });
  }

  async function register(email, password, nickname) {
    return window.LiMaAPI.post(REGISTER_PATH, { email, password, nickname });
  }

  window.LiMaAuth = {
    getToken,
    setToken,
    removeToken,
    clearSensitiveStorage,
    logout,
    isLoggedIn,
    redirectIfLoggedIn,
    showError,
    login,
    register,
  };
})();
