/* API Key management page logic — card layout with mask/reveal & copy feedback. */

(function () {
  "use strict";

  const token = LiMaAuth.getToken();
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  const API_PATH = "/device/v1/app/keys";
  const createBtn = document.getElementById("createBtn");
  const keyList = document.getElementById("keyList");
  const empty = document.getElementById("empty");
  const modal = document.getElementById("newKeyModal");
  const newKeyInput = document.getElementById("newKeyInput");
  const copyKeyBtn = document.getElementById("copyKeyBtn");
  const closeModalBtn = document.getElementById("closeModalBtn");
  const logoutBtn = document.getElementById("logoutBtn");

  /* SVG icon helpers */
  var EYE_OPEN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EYE_CLOSED = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.91-1.28a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
  var COPY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
  var CHECK_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
  var TRASH_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDate(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString("zh-CN");
  }

  function maskPrefix(prefix) {
    if (!prefix) return "••••••••";
    return prefix + "••••••••••••";
  }

  function showToast(message, type) {
    if (window.LiMaToast) {
      window.LiMaToast(message, { type: type === "error" ? "error" : "success" });
    }
  }

  function buildKeyCard(key) {
    var card = document.createElement("div");
    card.className = "key-card";
    card.dataset.id = key.id;

    var statusClass = (key.status || "").toLowerCase() === "active" ? "active" : "revoked";
    var statusLabel = key.status || "—";

    card.innerHTML =
      '<div class="key-card-info">' +
        '<div class="key-card-name">' + escapeHtml(key.name) + '</div>' +
        '<div class="key-card-meta">' +
          '<span class="key-card-prefix" data-masked="true">' + escapeHtml(maskPrefix(key.prefix)) + '</span>' +
          '<span class="key-card-status ' + statusClass + '">' + escapeHtml(statusLabel) + '</span>' +
          '<span>' + formatDate(key.createdAt) + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="key-card-actions">' +
        '<button class="key-toggle-vis" data-action="toggle" title="显示/隐藏前缀" aria-label="显示或隐藏 Key 前缀">' + EYE_CLOSED + '</button>' +
        '<button class="key-copy-btn" data-action="copy" title="复制前缀">' + COPY_ICON + ' 复制</button>' +
        '<button class="key-del-btn" data-action="delete" title="删除" aria-label="删除 Key">' + TRASH_ICON + '</button>' +
      '</div>';

    return card;
  }

  async function loadKeys() {
    try {
      var data = await LiMaAPI.get(API_PATH, token);
      var keys = data.keys || [];
      keyList.innerHTML = "";
      if (keys.length === 0) {
        keyList.classList.add("hidden");
        empty.classList.remove("hidden");
      } else {
        empty.classList.add("hidden");
        keyList.classList.remove("hidden");
        keys.forEach(function (key) {
          keyList.appendChild(buildKeyCard(key));
        });
      }
    } catch (err) {
      showToast(err.message || "加载失败", "error");
    }
  }

  /* Event delegation for key card actions */
  keyList.addEventListener("click", async function (e) {
    var btn = e.target.closest("[data-action]");
    if (!btn) return;
    var card = btn.closest(".key-card");
    var id = card && card.dataset.id;
    if (!id) return;

    var action = btn.dataset.action;

    if (action === "toggle") {
      var prefixEl = card.querySelector(".key-card-prefix");
      if (!prefixEl) return;
      var isMasked = prefixEl.dataset.masked === "true";
      if (isMasked) {
        /* Fetch full prefix from stored data or just show the raw prefix */
        prefixEl.textContent = prefixEl.dataset.raw || prefixEl.textContent.replace(/••••••••••••$/, "");
        prefixEl.dataset.masked = "false";
        btn.innerHTML = EYE_OPEN;
        btn.title = "隐藏前缀";
      } else {
        prefixEl.textContent = maskPrefix(prefixEl.textContent.replace(/•+$/, ""));
        prefixEl.dataset.masked = "true";
        btn.innerHTML = EYE_CLOSED;
        btn.title = "显示前缀";
      }
    }

    if (action === "copy") {
      var prefixEl2 = card.querySelector(".key-card-prefix");
      var text = prefixEl2 ? prefixEl2.textContent : "";
      try {
        await navigator.clipboard.writeText(text);
        btn.innerHTML = CHECK_ICON + " 已复制";
        btn.classList.add("copied");
        showToast("已复制到剪贴板", "success");
        setTimeout(function () {
          btn.innerHTML = COPY_ICON + " 复制";
          btn.classList.remove("copied");
        }, 2000);
      } catch {
        showToast("复制失败，请手动复制", "error");
      }
    }

    if (action === "delete") {
      if (!confirm("确定删除该 API Key？删除后无法恢复。")) return;
      try {
        await LiMaAPI.del(API_PATH + "/" + encodeURIComponent(id), token);
        card.style.opacity = "0";
        card.style.transform = "translateX(20px)";
        card.style.transition = "all 0.3s var(--ease-out)";
        setTimeout(function () {
          card.remove();
          if (keyList.children.length === 0) {
            keyList.classList.add("hidden");
            empty.classList.remove("hidden");
          }
        }, 300);
        showToast("已删除", "success");
      } catch (err) {
        showToast(err.message || "删除失败", "error");
      }
    }
  });

  createBtn.addEventListener("click", async function () {
    var name = prompt("为新 Key 命名：");
    if (!name || !name.trim()) return;
    createBtn.disabled = true;
    try {
      var data = await LiMaAPI.post(API_PATH, { name: name.trim() }, token);
      newKeyInput.value = data.key || "";
      modal.classList.remove("hidden");
      modal.classList.add("open");
      await loadKeys();
    } catch (err) {
      showToast(err.message || "创建失败", "error");
    } finally {
      createBtn.disabled = false;
    }
  });

  copyKeyBtn.addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(newKeyInput.value);
      copyKeyBtn.innerHTML = CHECK_ICON + " 已复制";
      copyKeyBtn.classList.add("copied");
      showToast("Key 已复制到剪贴板", "success");
      setTimeout(function () {
        copyKeyBtn.innerHTML = COPY_ICON + " 复制";
        copyKeyBtn.classList.remove("copied");
      }, 2000);
    } catch {
      showToast("复制失败，请手动复制", "error");
    }
  });

  closeModalBtn.addEventListener("click", function () {
    modal.classList.add("hidden");
    modal.classList.remove("open");
    newKeyInput.value = "";
  });

  logoutBtn.addEventListener("click", function () {
    LiMaAuth.logout();
    window.location.href = "login.html";
  });

  loadKeys();
})();
