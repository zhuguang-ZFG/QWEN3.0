/* API Key management page logic. */

(function () {
  "use strict";

  const token = LiMaAuth.getToken();
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  const API_PATH = "/device/v1/app/keys";
  const createBtn = document.getElementById("createBtn");
  const keysBody = document.getElementById("keysBody");
  const keysTable = document.getElementById("keysTable");
  const empty = document.getElementById("empty");
  const toast = document.getElementById("toast");
  const modal = document.getElementById("newKeyModal");
  const newKeyInput = document.getElementById("newKeyInput");
  const copyKeyBtn = document.getElementById("copyKeyBtn");
  const closeModalBtn = document.getElementById("closeModalBtn");
  const logoutBtn = document.getElementById("logoutBtn");

  function showToast(message, type) {
    toast.textContent = message;
    toast.className = "toast " + (type === "error" ? "error" : "success");
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 3000);
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString("zh-CN");
  }

  function renderRow(key) {
    const tr = document.createElement("tr");
    tr.dataset.id = key.id;
    tr.innerHTML =
      '<td>' + escapeHtml(key.name) + '</td>' +
      '<td class="key-prefix">' + escapeHtml(key.prefix) + '</td>' +
      '<td>' + escapeHtml(key.status) + '</td>' +
      '<td>' + formatDate(key.createdAt) + '</td>' +
      '<td><button class="btn-sm btn-danger" data-action="delete">删除</button></td>';
    return tr;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function loadKeys() {
    try {
      const data = await LiMaAPI.get(API_PATH, token);
      const keys = data.keys || [];
      keysBody.innerHTML = "";
      if (keys.length === 0) {
        keysTable.classList.add("hidden");
        empty.classList.remove("hidden");
      } else {
        empty.classList.add("hidden");
        keysTable.classList.remove("hidden");
        keys.forEach((key) => keysBody.appendChild(renderRow(key)));
      }
    } catch (err) {
      showToast(err.message || "加载失败", "error");
    }
  }

  createBtn.addEventListener("click", async function () {
    const name = prompt("为新 Key 命名：");
    if (!name || !name.trim()) return;
    createBtn.disabled = true;
    try {
      const data = await LiMaAPI.post(API_PATH, { name: name.trim() }, token);
      newKeyInput.value = data.key || "";
      modal.classList.remove("hidden");
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
      showToast("已复制到剪贴板", "success");
    } catch {
      showToast("复制失败，请手动复制", "error");
    }
  });

  closeModalBtn.addEventListener("click", function () {
    modal.classList.add("hidden");
    newKeyInput.value = "";
  });

  keysBody.addEventListener("click", async function (e) {
    const btn = e.target.closest('[data-action="delete"]');
    if (!btn) return;
    const tr = btn.closest("tr");
    const id = tr && tr.dataset.id;
    if (!id) return;
    if (!confirm("确定删除该 API Key？删除后无法恢复。")) return;
    try {
      await LiMaAPI.del(API_PATH + "/" + encodeURIComponent(id), token);
      tr.remove();
      if (keysBody.children.length === 0) {
        keysTable.classList.add("hidden");
        empty.classList.remove("hidden");
      }
      showToast("已删除", "success");
    } catch (err) {
      showToast(err.message || "删除失败", "error");
    }
  });

  logoutBtn.addEventListener("click", function () {
    LiMaAuth.logout();
    window.location.href = "login.html";
  });

  loadKeys();
})();
