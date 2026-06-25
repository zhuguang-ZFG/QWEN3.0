/* Authentication helpers for LiMa chat-web login/register pages. */

(function () {
  "use strict";

  const TOKEN_KEY = "lima_token";
  const LOGIN_PATH = "/device/v1/app/auth/login-email";
  const REGISTER_PATH = "/device/v1/app/auth/register-email";

  function getToken() {
    try {
      return localStorage.getItem(TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  function setToken(token) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {}
  }

  function removeToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {}
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
    isLoggedIn,
    redirectIfLoggedIn,
    showError,
    login,
    register,
  };
})();
