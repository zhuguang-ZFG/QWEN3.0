/* Handwriting preview page logic. */

(function () {
  "use strict";

  const token = LiMaAuth.getToken();
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  const OPTIONS_API = "/device/v1/app/handwriting/options";
  const HANDWRITING_API = "/device/v1/app/handwriting";
  const DEVICES_API = "/device/v1/app/devices";

  const els = {
    form: document.getElementById("handwritingForm"),
    text: document.getElementById("textInput"),
    charCount: document.getElementById("charCount"),
    font: document.getElementById("fontSelect"),
    paper: document.getElementById("paperSelect"),
    mistakeRate: document.getElementById("mistakeRate"),
    mistakeValue: document.getElementById("mistakeValue"),
    messyRatio: document.getElementById("messyRatio"),
    messyValue: document.getElementById("messyValue"),
    charRandom: document.getElementById("charRandom"),
    charRandomValue: document.getElementById("charRandomValue"),
    modePreview: document.getElementById("modePreview"),
    modeTask: document.getElementById("modeTask"),
    deviceSelect: document.getElementById("deviceSelect"),
    deviceWrap: document.getElementById("deviceWrap"),
    submit: document.getElementById("generateBtn"),
    result: document.getElementById("resultArea"),
    loading: document.getElementById("loading"),
    toast: document.getElementById("toast"),
  };

  let maxTextLength = 3500;
  let currentMode = "preview";
  let devices = [];

  function showToast(message, duration = 3000) {
    els.toast.textContent = message;
    els.toast.classList.add("show");
    setTimeout(() => els.toast.classList.remove("show"), duration);
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setLoading(on) {
    els.submit.disabled = on;
    els.loading.hidden = !on;
  }

  function fillSelect(select, options) {
    select.innerHTML = "";
    Object.entries(options).forEach(([value, label]) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = `${label} (${value})`;
      select.appendChild(opt);
    });
  }

  async function loadOptions() {
    try {
      const data = await LiMaAPI.get(OPTIONS_API, token);
      maxTextLength = data.max_text_length || maxTextLength;
      fillSelect(els.font, data.fonts || {});
      fillSelect(els.paper, data.papers || {});
      if (data.defaults) {
        els.font.value = data.defaults.font_type || els.font.value;
        els.paper.value = data.defaults.paper_bg_type || els.paper.value;
        els.mistakeRate.value = data.defaults.mistake_rate ?? 3;
        els.messyRatio.value = data.defaults.messy_ratio ?? 0;
        els.charRandom.value = data.defaults.char_random ?? 0;
      }
      syncSliderLabels();
    } catch (err) {
      showToast("加载选项失败：" + (err.message || "未知错误"));
    }
  }

  async function loadDevices() {
    try {
      const data = await LiMaAPI.get(DEVICES_API, token);
      devices = data.devices || [];
      els.deviceSelect.innerHTML = "";
      if (devices.length === 0) {
        els.deviceSelect.innerHTML = `<option value="">暂无设备</option>`;
        els.deviceSelect.disabled = true;
      } else {
        els.deviceSelect.disabled = false;
        devices.forEach((device) => {
          const opt = document.createElement("option");
          opt.value = device.deviceId;
          const name = device.metadata?.name || device.model || device.deviceId;
          opt.textContent = `${name} (${device.deviceSn || device.deviceId})`;
          els.deviceSelect.appendChild(opt);
        });
      }
    } catch (err) {
      showToast("加载设备失败：" + (err.message || "未知错误"));
    }
  }

  function syncSliderLabels() {
    els.mistakeValue.textContent = els.mistakeRate.value;
    els.messyValue.textContent = els.messyRatio.value;
    els.charRandomValue.textContent = els.charRandom.value;
  }

  function updateCharCount() {
    const len = els.text.value.length;
    els.charCount.textContent = `${len} / ${maxTextLength}`;
    els.charCount.classList.toggle("over", len > maxTextLength);
  }

  function setMode(mode) {
    currentMode = mode;
    els.modePreview.classList.toggle("active", mode === "preview");
    els.modeTask.classList.toggle("active", mode === "task");
    els.deviceWrap.hidden = mode !== "task";
    els.submit.textContent = mode === "preview" ? "生成 SVG 预览" : "下发到设备";
  }

  function collectPayload() {
    return {
      text: els.text.value.trim(),
      font_type: els.font.value,
      paper_bg_type: els.paper.value,
      mistake_rate: parseInt(els.mistakeRate.value, 10) || 0,
      messy_ratio: parseInt(els.messyRatio.value, 10) || 0,
      char_random: parseInt(els.charRandom.value, 10) || 0,
    };
  }

  function renderSvgPreview(item) {
    const width = parseInt(item.width, 10) || 100;
    const height = parseInt(item.height, 10) || 100;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" style="max-width:100%;height:auto;background:#fff">
      <rect width="100%" height="100%" fill="#fff"/>
      <path d="${escapeHtml(item.svg_path || "")}" fill="none" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
    els.result.innerHTML = `
      <div class="result-title">SVG 预览 · ${width}×${height}</div>
      <div class="svg-preview">${svg}</div>
      <div class="result-meta">后端：${escapeHtml(item.backend || "autohanding")}</div>
    `;
  }

  function renderTaskResult(task, deviceId) {
    const params = task.task?.params || {};
    els.result.innerHTML = `
      <div class="result-title">任务已下发</div>
      <div class="result-meta">设备：${escapeHtml(deviceId)}</div>
      <div class="result-meta">任务 ID：${escapeHtml(task.taskId || task.task?.task_id || "—")}</div>
      <div class="result-meta">状态：${escapeHtml(task.status || "—")}</div>
      <div class="result-meta">点数：${params.point_count ?? "—"}</div>
      <details class="result-details">
        <summary>查看任务详情</summary>
        <pre>${escapeHtml(JSON.stringify(task, null, 2))}</pre>
      </details>
    `;
  }

  async function handlePreview(payload) {
    const data = await LiMaAPI.post(HANDWRITING_API, payload, token);
    const item = (data.data || [])[0];
    if (!item || !item.svg_path) {
      throw new Error("返回结果不含 SVG path");
    }
    renderSvgPreview(item);
  }

  async function handleTask(payload) {
    const deviceId = els.deviceSelect.value;
    if (!deviceId) {
      throw new Error("请先选择设备");
    }
    const body = { capability: "handwriting", params: payload, source: "app" };
    const task = await LiMaAPI.post(`/device/v1/app/devices/${encodeURIComponent(deviceId)}/tasks`, body, token);
    renderTaskResult(task, deviceId);
  }

  async function onSubmit(event) {
    event.preventDefault();
    const payload = collectPayload();
    if (!payload.text) {
      showToast("请输入要转换的文字");
      return;
    }
    if (payload.text.length > maxTextLength) {
      showToast(`文字过长，最多 ${maxTextLength} 字`);
      return;
    }
    setLoading(true);
    try {
      if (currentMode === "preview") {
        await handlePreview(payload);
      } else {
        await handleTask(payload);
      }
    } catch (err) {
      els.result.innerHTML = `<div class="result-error">失败：${escapeHtml(err.message || "未知错误")}</div>`;
    } finally {
      setLoading(false);
    }
  }

  els.text.addEventListener("input", updateCharCount);
  [els.mistakeRate, els.messyRatio, els.charRandom].forEach((input) => {
    input.addEventListener("input", syncSliderLabels);
  });
  els.modePreview.addEventListener("click", () => setMode("preview"));
  els.modeTask.addEventListener("click", () => setMode("task"));
  els.form.addEventListener("submit", onSubmit);

  loadOptions();
  loadDevices();
  updateCharCount();
  setMode("preview");
})();
