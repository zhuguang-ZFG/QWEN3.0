// LiMa 星云 API Playground — shared utilities
(function (global) {
  "use strict";

  const DEFAULT_BODY = {
    model: "lima",
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Hello, LiMa!" },
    ],
    stream: true,
    temperature: 0.7,
    max_tokens: 1024,
  };

  const FALLBACK_MODELS = [
    "lima",
    "gpt-3.5-turbo",
    "gpt-4o",
    "claude-3-5-sonnet",
    "deepseek-chat",
  ];

  const LS_KEY_AUTH = "lima_api_key";
  const LS_KEY_AUTH_LEGACY = "lima-api-key";
  const LS_KEY_HISTORY = "lima_playground_history";
  const HISTORY_LIMIT = 20;

  function loadAuth() {
    return (
      sessionStorage.getItem(LS_KEY_AUTH) ||
      sessionStorage.getItem(LS_KEY_AUTH_LEGACY) ||
      localStorage.getItem(LS_KEY_AUTH) ||
      localStorage.getItem(LS_KEY_AUTH_LEGACY) ||
      ""
    );
  }

  function saveAuth(value) {
    if (value) {
      sessionStorage.setItem(LS_KEY_AUTH, value);
    } else {
      sessionStorage.removeItem(LS_KEY_AUTH);
      sessionStorage.removeItem(LS_KEY_AUTH_LEGACY);
      localStorage.removeItem(LS_KEY_AUTH);
      localStorage.removeItem(LS_KEY_AUTH_LEGACY);
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/'/g, "&#39;")
      .replace(/"/g, "&quot;")
      .replace(/`/g, "&#96;");
  }

  function showToast(ctx, message, opts = {}) {
    const { duration = 3500, error = false } = opts;
    const toast = ctx.els.toast;
    toast.textContent = message;
    toast.classList.toggle("error", error);
    toast.classList.add("show");
    if (toast._timer) clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("show"), duration);
  }

  function prettyJson(obj) {
    return JSON.stringify(obj, null, 2);
  }

  function parseJsonBody(ctx) {
    const text = ctx.editor ? ctx.editor.getValue() : "{}";
    try {
      return JSON.parse(text);
    } catch (err) {
      throw new Error("请求体 JSON 格式错误：" + err.message);
    }
  }

  function setJsonBody(ctx, obj) {
    if (!ctx.editor) return;
    ctx.suppressEditorSync = true;
    ctx.editor.setValue(prettyJson(obj));
    ctx.suppressEditorSync = false;
  }

  function syncControlsFromBody(ctx) {
    if (ctx.suppressEditorSync) return;
    try {
      const body = parseJsonBody(ctx);
      if (body.model && ctx.els.model.value !== body.model) {
        const exists = Array.from(ctx.els.model.options).some((o) => o.value === body.model);
        if (exists) ctx.els.model.value = body.model;
      }
      if (typeof body.temperature === "number") {
        ctx.els.temperature.value = body.temperature;
        ctx.els.tempValue.textContent = body.temperature.toFixed(1);
      }
      if (typeof body.max_tokens === "number") ctx.els.maxTokens.value = body.max_tokens;
      if (typeof body.stream === "boolean") ctx.els.stream.checked = body.stream;
    } catch (err) {
      console.warn("playground: failed to sync controls from editor JSON:", err);
    }
  }

  function updateBodyFromControls(ctx) {
    try {
      const body = parseJsonBody(ctx);
      body.model = ctx.els.model.value;
      body.temperature = parseFloat(ctx.els.temperature.value);
      body.max_tokens = parseInt(ctx.els.maxTokens.value, 10);
      body.stream = ctx.els.stream.checked;
      setJsonBody(ctx, body);
    } catch (err) {
      console.warn("playground: failed to update editor JSON from controls:", err);
    }
  }

  async function loadModels(ctx) {
    try {
      const res = await fetch("/v1/models", { method: "GET" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const json = await res.json();
      const models = (json.data || [])
        .map((m) => m.id || m.model || m)
        .filter((id) => typeof id === "string" && id.length > 0);
      populateModels(ctx, models.length ? models : FALLBACK_MODELS);
    } catch (err) {
      console.warn("playground: failed to fetch /v1/models, using fallback list:", err);
      populateModels(ctx, FALLBACK_MODELS);
    }
  }

  function populateModels(ctx, models) {
    const current = ctx.els.model.value;
    ctx.els.model.innerHTML = "";
    for (const id of models) {
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = id;
      ctx.els.model.appendChild(opt);
    }
    const defaultModel = DEFAULT_BODY.model;
    const preferred = current || defaultModel;
    const exists = Array.from(ctx.els.model.options).some((o) => o.value === preferred);
    ctx.els.model.value = exists ? preferred : (ctx.els.model.options[0]?.value || defaultModel);
    updateBodyFromControls(ctx);
  }

  function announce(ctx, message) {
    if (!ctx.els.announcer) return;
    ctx.els.announcer.textContent = "";
    void ctx.els.announcer.offsetWidth;
    ctx.els.announcer.textContent = message;
  }

  function shellQuote(str) {
    // Bash $'...' ANSI-C quoting: escape $, backticks, backslashes, double quotes
    // and single quotes so the argument stays a single shell word.
    return "$'" + String(str)
      .replace(/\\/g, "\\\\")
      .replace(/'/g, "\\'")
      .replace(/"/g, '\\"')
      .replace(/\$/g, "\\$")
      .replace(/`/g, "\\`")
      .replace(/\n/g, "\\n")
      .replace(/\r/g, "\\r")
      .replace(/\t/g, "\\t") + "'";
  }

  function buildCurl(ctx) {
    const body = ctx.editor ? ctx.editor.getValue() : prettyJson(DEFAULT_BODY);
    const url = window.LIMA_CONFIG.apiOrigin + "/v1/chat/completions";
    const auth = ctx.els.auth.value.trim();
    let cmd = "curl -X POST \\\n";
    cmd += "  " + url + " \\\n";
    cmd += "  -H " + shellQuote("Content-Type: application/json") + " \\\n";
    if (auth) cmd += "  -H " + shellQuote("Authorization: Bearer " + auth) + " \\\n";
    cmd += "  -d " + shellQuote(body);
    return cmd;
  }

  function copyViaExecCommand(text) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "0";
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, text.length);
    let success = false;
    try {
      success = document.execCommand("copy");
    } catch (err) {
      console.warn("playground: execCommand copy failed:", err);
      success = false;
    }
    document.body.removeChild(textarea);
    return success;
  }

  async function copyCurl(ctx) {
    const text = buildCurl(ctx);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ok = copyViaExecCommand(text);
        if (!ok) throw new Error("clipboard unavailable");
      }
      showToast(ctx, "cURL 命令已复制到剪贴板");
    } catch (err) {
      console.warn("playground: failed to copy cURL command:", err);
      showToast(ctx, "复制失败，请手动复制", { error: true });
    }
  }

  global.PgUtils = {
    DEFAULT_BODY,
    FALLBACK_MODELS,
    HISTORY_LIMIT,
    LS_KEY_AUTH,
    LS_KEY_AUTH_LEGACY,
    LS_KEY_HISTORY,
    loadAuth,
    saveAuth,
    escapeHtml,
    showToast,
    prettyJson,
    parseJsonBody,
    setJsonBody,
    syncControlsFromBody,
    updateBodyFromControls,
    loadModels,
    populateModels,
    announce,
    buildCurl,
    copyCurl,
    copyViaExecCommand,
    shellQuote,
  };
})(window);
