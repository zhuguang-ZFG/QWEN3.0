/* Device management page logic. */

(function () {
  "use strict";

  const token = LiMaAuth.getToken();
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  const DEVICES_API = "/device/v1/app/devices";
  const TASKS_API = "/device/v1/app/tasks";
  const WS_BASE = (location.protocol === "https:" ? "wss://" : "ws://") + location.host;

  const grid = document.getElementById("deviceGrid");
  const emptyState = document.getElementById("emptyState");
  const drawerOverlay = document.getElementById("drawerOverlay");
  const drawer = document.getElementById("detailDrawer");
  const drawerTitle = document.getElementById("drawerTitle");
  const drawerBody = document.getElementById("drawerBody");
  const closeDrawer = document.getElementById("closeDrawer");
  const unbindBtn = document.getElementById("unbindBtn");
  const addDeviceBtn = document.getElementById("addDeviceBtn");
  const bindModal = document.getElementById("bindModal");
  const bindSn = document.getElementById("bindSn");
  const bindCode = document.getElementById("bindCode");
  const confirmBind = document.getElementById("confirmBind");
  const cancelBind = document.getElementById("cancelBind");
  const confirmModal = document.getElementById("confirmModal");
  const confirmUnbind = document.getElementById("confirmUnbind");
  const cancelUnbind = document.getElementById("cancelUnbind");
  const toast = document.getElementById("toast");

  let devices = [];
  let statuses = {};
  let selectedDeviceId = null;
  let ws = null;
  let statusPoller = null;
  let activeTaskPollers = [];

  function escapeHtml(str) {
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function formatTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("zh-CN");
  }

  function deviceName(device) {
    const meta = device.metadata || {};
    return meta.name || device.model || device.deviceId;
  }

  function statusClass(status) {
    if (status.online && status.working) return "busy";
    if (status.online) return "on";
    return "off";
  }

  function statusLabel(status) {
    if (status.online && status.working) return "运行中";
    if (status.online) return "在线";
    return "离线";
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
  }

  async function loadDevices() {
    try {
      const data = await LiMaAPI.get(DEVICES_API, token);
      devices = data.devices || [];
      await loadStatuses();
      renderGrid();
    } catch (err) {
      showToast("加载设备失败：" + (err.message || "未知错误"));
    }
  }

  async function loadStatuses() {
    statuses = {};
    await Promise.all(
      devices.map(async (device) => {
        try {
          const status = await LiMaAPI.get(`${DEVICES_API}/${encodeURIComponent(device.deviceId)}/status`, token);
          statuses[device.deviceId] = status;
        } catch {
          statuses[device.deviceId] = { online: false, working: false };
        }
      })
    );
    Object.entries(statuses).forEach(([deviceId, status]) => updateTileStatus(deviceId, status));
  }

  function renderGrid() {
    grid.innerHTML = "";
    if (devices.length === 0) {
      emptyState.hidden = false;
      return;
    }
    emptyState.hidden = true;
    devices.forEach((device) => {
      const status = statuses[device.deviceId] || { online: false, working: false };
      const tile = document.createElement("div");
      tile.className = "device-tile";
      tile.dataset.id = device.deviceId;
      tile.innerHTML = `
        <div class="device-tile-top">
          <div class="device-tile-info">
            <div class="device-tile-icon"><svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg></div>
            <div>
              <div class="device-tile-name">${escapeHtml(deviceName(device))}</div>
              <div class="device-tile-sn">${escapeHtml(device.deviceSn || device.deviceId)}</div>
            </div>
          </div>
          <span class="status-badge ${statusClass(status)}"><span class="status-dot ${statusClass(status)}"></span>${statusLabel(status)}</span>
        </div>
        <div class="device-tile-meta">
          <span>型号 ${escapeHtml(device.model || "—")}</span>
          <span>固件 ${escapeHtml(device.firmwareVer || "—")}</span>
        </div>
      `;
      tile.addEventListener("click", () => openDrawer(device.deviceId));
      grid.appendChild(tile);
    });
  }

  async function openDrawer(deviceId) {
    selectedDeviceId = deviceId;
    const device = devices.find((d) => d.deviceId === deviceId);
    if (!device) return;
    drawerTitle.textContent = deviceName(device);
    drawerBody.innerHTML = `<div class="empty">加载中…</div>`;
    drawerOverlay.classList.add("open");
    drawer.classList.add("open");

    connectStatusWs(deviceId);
    await renderDrawer(device);
  }

  function closeDetailDrawer() {
    selectedDeviceId = null;
    drawerOverlay.classList.remove("open");
    drawer.classList.remove("open");
    if (ws) {
      try { ws.close(); } catch {}
      ws = null;
    }
    activeTaskPollers.forEach((id) => clearInterval(id));
    activeTaskPollers = [];
  }

  function connectStatusWs(deviceId) {
    if (ws) {
      try { ws.close(); } catch {}
    }
    try {
      ws = new WebSocket(`${WS_BASE}/device/v1/app/devices/${encodeURIComponent(deviceId)}/ws?authorization=Bearer ${encodeURIComponent(token)}`);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          handleWsMessage(deviceId, msg);
        } catch {}
      };
      ws.onerror = () => {};
    } catch {
      ws = null;
    }
  }

  function handleWsMessage(deviceId, msg) {
    if (msg.event === "status_snapshot" && msg.payload) {
      statuses[deviceId] = msg.payload;
      updateTileStatus(deviceId, msg.payload);
      if (selectedDeviceId === deviceId) {
        updateDrawerStatus(msg.payload);
      }
    } else if (msg.event === "device_online" || msg.event === "device_offline") {
      const online = msg.event === "device_online";
      statuses[deviceId] = Object.assign({}, statuses[deviceId] || {}, { online });
      updateTileStatus(deviceId, statuses[deviceId]);
      if (selectedDeviceId === deviceId) updateDrawerStatus(statuses[deviceId]);
    }
  }

  function updateTileStatus(deviceId, status) {
    const tile = grid.querySelector(`.device-tile[data-id="${CSS.escape(deviceId)}"]`);
    if (!tile) return;
    const badge = tile.querySelector(".status-badge");
    const dot = tile.querySelector(".status-dot");
    if (!badge) return;
    badge.className = `status-badge ${statusClass(status)}`;
    if (dot) dot.className = `status-dot ${statusClass(status)}`;
    badge.childNodes[1].textContent = statusLabel(status);
  }

  function updateDrawerStatus(status) {
    const el = document.getElementById("drawerStatus");
    if (!el) return;
    el.className = `status-badge ${statusClass(status)}`;
    el.innerHTML = `<span class="status-dot ${statusClass(status)}"></span>${statusLabel(status)}`;
  }

  function isTaskActive(status) {
    return ["pending", "running", "approved", "paused"].includes((status || "").toLowerCase());
  }

  function taskProgressHtml(task) {
    const pct = task.progress == null ? 0 : Math.max(0, Math.min(100, task.progress));
    return `<div class="task-progress"><div class="task-progress-bar" style="width:${pct}%"></div></div>`;
  }

  function buildTaskItem(task) {
    const active = isTaskActive(task.status);
    return `
      <div class="task-item" data-task-id="${escapeHtml(task.taskId || task.id || "")}" data-task-status="${escapeHtml(task.status || "")}">
        <div class="cap">${escapeHtml(task.capability || "task")} · <span class="task-status-text" style="color:var(--text-muted)">${escapeHtml(task.status || "—")}</span></div>
        <div class="sub task-meta">${formatTime(task.createdAt)}${task.progress != null ? " · 进度 " + task.progress + "%" : ""}</div>
        ${active ? taskProgressHtml(task) : ""}
      </div>
    `;
  }

  async function renderDrawer(device) {
    const status = statuses[device.deviceId] || { online: false, working: false };
    let tasksHtml = "";
    let items = [];
    try {
      const tasksData = await LiMaAPI.get(`${TASKS_API}?device_id=${encodeURIComponent(device.deviceId)}&limit=5`, token);
      items = tasksData.tasks || [];
      if (items.length === 0) {
        tasksHtml = `<div class="empty" style="padding:24px 0;">最近无任务</div>`;
      } else {
        tasksHtml = `<div class="task-list">${items.map(buildTaskItem).join("")}</div>`;
      }
    } catch {
      tasksHtml = `<div class="empty" style="padding:24px 0;">无法加载任务</div>`;
    }

    drawerBody.innerHTML = `
      <div class="drawer-section">
        <div id="drawerStatus" class="status-badge ${statusClass(status)}"><span class="status-dot ${statusClass(status)}"></span>${statusLabel(status)}</div>
      </div>
      <div class="drawer-section">
        <h3>设备信息</h3>
        <div class="drawer-row"><span>设备 ID</span><span>${escapeHtml(device.deviceId)}</span></div>
        <div class="drawer-row"><span>SN</span><span>${escapeHtml(device.deviceSn || "—")}</span></div>
        <div class="drawer-row"><span>型号</span><span>${escapeHtml(device.model || "—")}</span></div>
        <div class="drawer-row"><span>固件版本</span><span>${escapeHtml(device.firmwareVer || status.firmwareVersion || "—")}</span></div>
        <div class="drawer-row"><span>硬件版本</span><span>${escapeHtml(device.hardwareVer || "—")}</span></div>
        <div class="drawer-row"><span>最近心跳</span><span>${formatTime(device.lastHeartbeat || status.lastSeenAt)}</span></div>
      </div>
      <div class="drawer-section">
        <h3>最近 5 条任务</h3>
        ${tasksHtml}
      </div>
    `;

    startTaskPolling(items);
  }

  async function updateTaskItem(taskId) {
    try {
      const data = await LiMaAPI.get(`${TASKS_API}/${encodeURIComponent(taskId)}`, token);
      const task = data.task || data;
      const el = drawerBody.querySelector(`.task-item[data-task-id="${CSS.escape(taskId)}"]`);
      if (!el) return;
      const statusText = el.querySelector(".task-status-text");
      const meta = el.querySelector(".task-meta");
      if (statusText) statusText.textContent = task.status || "—";
      if (meta) meta.textContent = `${formatTime(task.createdAt)}${task.progress != null ? " · 进度 " + task.progress + "%" : ""}`;
      const pct = task.progress == null ? 0 : Math.max(0, Math.min(100, task.progress));
      let bar = el.querySelector(".task-progress-bar");
      if (isTaskActive(task.status)) {
        if (!bar) {
          const wrap = document.createElement("div");
          wrap.className = "task-progress";
          wrap.innerHTML = `<div class="task-progress-bar" style="width:${pct}%"></div>`;
          el.appendChild(wrap);
        } else {
          bar.style.width = pct + "%";
        }
      } else if (bar) {
        bar.parentElement.remove();
      }
      el.dataset.taskStatus = task.status || "";
      return !isTaskActive(task.status);
    } catch {
      return false;
    }
  }

  function startTaskPolling(items) {
    activeTaskPollers.forEach((id) => clearInterval(id));
    activeTaskPollers = [];
    items.forEach((task) => {
      const taskId = task.taskId || task.id;
      if (!taskId || !isTaskActive(task.status)) return;
      updateTaskItem(taskId);
      const id = setInterval(async () => {
        const done = await updateTaskItem(taskId);
        if (done) clearInterval(id);
      }, 2000);
      activeTaskPollers.push(id);
    });
  }

  function openBindModal() {
    bindSn.value = "";
    bindCode.value = "";
    bindModal.classList.add("open");
  }

  function closeBindModal() {
    bindModal.classList.remove("open");
  }

  async function submitBind() {
    const sn = bindSn.value.trim();
    const code = bindCode.value.trim();
    if (!sn || !code) {
      showToast("请输入设备 SN 和激活码");
      return;
    }
    try {
      await LiMaAPI.post(`${DEVICES_API}/bind`, { deviceSn: sn, activationCode: code }, token);
      closeBindModal();
      showToast("设备绑定成功");
      await loadDevices();
    } catch (err) {
      showToast("绑定失败：" + (err.message || "未知错误"));
    }
  }

  function openUnbindModal() {
    if (!selectedDeviceId) return;
    confirmModal.classList.add("open");
  }

  function closeUnbindModal() {
    confirmModal.classList.remove("open");
  }

  async function submitUnbind() {
    if (!selectedDeviceId) return;
    try {
      await LiMaAPI.post(`${DEVICES_API}/${encodeURIComponent(selectedDeviceId)}/unbind`, {}, token);
      closeUnbindModal();
      closeDetailDrawer();
      showToast("设备已解绑");
      await loadDevices();
    } catch (err) {
      showToast("解绑失败：" + (err.message || "未知错误"));
    }
  }

  closeDrawer.addEventListener("click", closeDetailDrawer);
  drawerOverlay.addEventListener("click", closeDetailDrawer);
  unbindBtn.addEventListener("click", openUnbindModal);
  addDeviceBtn.addEventListener("click", openBindModal);
  cancelBind.addEventListener("click", closeBindModal);
  confirmBind.addEventListener("click", submitBind);
  cancelUnbind.addEventListener("click", closeUnbindModal);
  confirmUnbind.addEventListener("click", submitUnbind);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (confirmModal.classList.contains("open")) closeUnbindModal();
      else if (bindModal.classList.contains("open")) closeBindModal();
      else closeDetailDrawer();
    }
  });

  loadDevices();
  statusPoller = setInterval(loadStatuses, 10000);
  window.addEventListener("beforeunload", () => {
    if (statusPoller) clearInterval(statusPoller);
    if (ws) try { ws.close(); } catch {}
  });
})();
