/* Sidebar real-device status indicator for the chat console. */

(function () {
  "use strict";

  const token = window.LiMaAuth ? LiMaAuth.getToken() : "";
  const list = document.getElementById("myDeviceList");
  if (!token || !list) return;

  const API = "/device/v1/app/devices";
  let devices = [];
  let statuses = {};
  let poller = null;

  function escapeHtml(str) {
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function deviceName(device) {
    const meta = device.metadata || {};
    return meta.name || device.model || device.deviceId;
  }

  function statusClass(status) {
    if (status && status.online && status.working) return "busy";
    if (status && status.online) return "on";
    return "off";
  }

  function statusLabel(status) {
    if (status && status.online && status.working) return "运行中";
    if (status && status.online) return "在线";
    return "离线";
  }

  async function loadDevices() {
    try {
      const data = await LiMaAPI.get(API, token);
      devices = data.devices || [];
      await loadStatuses();
      render();
    } catch (err) {
      list.innerHTML = `<div class="device-card" style="cursor:default;"><div class="device-card-top"><div class="device-meta"><div class="device-sub">无法加载设备</div></div></div></div>`;
    }
  }

  async function loadStatuses() {
    await Promise.all(
      devices.map(async (device) => {
        try {
          const status = await LiMaAPI.get(`${API}/${encodeURIComponent(device.deviceId)}/status`, token);
          statuses[device.deviceId] = status;
        } catch {
          statuses[device.deviceId] = { online: false, working: false };
        }
      })
    );
  }

  function iconForModel(model) {
    if (model && model.includes("draw")) return "draw";
    if (model && model.includes("write")) return "write";
    if (model && model.includes("human")) return "human";
    if (model && model.includes("voice")) return "voice";
    return "ai";
  }

  function render() {
    if (devices.length === 0) {
      list.innerHTML = `<a class="device-card" href="devices.html" style="text-decoration:none;color:inherit;"><div class="device-card-top"><div class="device-icon ai"><svg class="svg-icon"><use href="icons.svg#i-bot"/></svg></div><div class="device-meta"><div class="device-name">暂无设备</div><div class="device-sub">前往设备管理</div></div></div></a>`;
      return;
    }

    list.innerHTML = devices.map((device) => {
      const status = statuses[device.deviceId] || { online: false, working: false };
      const cls = iconForModel(device.model);
      return `
        <a class="device-card" href="devices.html?id=${encodeURIComponent(device.deviceId)}" style="text-decoration:none;color:inherit;">
          <div class="device-card-top">
            <div class="device-icon ${cls}">
              <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            </div>
            <div class="device-meta">
              <div class="device-name">${escapeHtml(deviceName(device))}</div>
              <div class="device-sub">
                <span class="status-dot ${statusClass(status)}"></span>
                ${statusLabel(status)}
              </div>
            </div>
          </div>
        </a>
      `;
    }).join("");
  }

  async function refresh() {
    await loadStatuses();
    render();
  }

  loadDevices();
  poller = setInterval(refresh, 10000);
  window.addEventListener("beforeunload", () => {
    if (poller) clearInterval(poller);
  });
})();
