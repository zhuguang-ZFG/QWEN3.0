// LiMa 星云 API Playground — main controller
(function () {
  "use strict";

  const U = window.PgUtils;
  const Ui = window.PgUi;
  const els = {
    auth: document.getElementById("pgAuth"),
    model: document.getElementById("pgModel"),
    temperature: document.getElementById("pgTemperature"),
    tempValue: document.getElementById("pgTempValue"),
    maxTokens: document.getElementById("pgMaxTokens"),
    stream: document.getElementById("pgStream"),
    sendBtn: document.getElementById("pgSendBtn"),
    copyCurlBtn: document.getElementById("pgCopyCurlBtn"),
    responseBody: document.getElementById("pgResponseBody"),
    statusPill: document.getElementById("pgStatusPill"),
    timePill: document.getElementById("pgTimePill"),
    tokensPill: document.getElementById("pgTokensPill"),
    historyList: document.getElementById("pgHistoryList"),
    historyCount: document.getElementById("pgHistoryCount"),
    toast: document.getElementById("pgToast"),
    setKeyBtn: document.getElementById("pgSetKeyBtn"),
    editor: document.getElementById("pgEditor"),
    announcer: document.getElementById("pgAnnouncer"),
    keyModalOverlay: document.getElementById("pgKeyModal"),
    keyModalInput: document.getElementById("pgKeyModalInput"),
    keyModalSave: document.getElementById("pgKeyModalSave"),
    keyModalCancel: document.getElementById("pgKeyModalCancel"),
  };

  const ctx = {
    els,
    editor: null,
    tokenChart: null,
    isSending: false,
    abortController: null,
    suppressEditorSync: false,
  };

  function _iconSvg(useHref, spin) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "svg-icon");
    if (spin) svg.style.animation = "spin 1s linear infinite";
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", useHref);
    svg.appendChild(use);
    return svg;
  }

  function setSendLoading(loading) {
    const btn = els.sendBtn;
    btn.classList.toggle("primary", !loading);
    btn.textContent = "";
    btn.appendChild(_iconSvg(loading ? "icons.svg#i-cpu" : "icons.svg#i-play", loading));
    btn.appendChild(document.createTextNode(loading ? " 取消" : " 发送请求"));
  }

  function _buildRequestOptions(body) {
    const auth = els.auth.value.trim();
    U.saveAuth(auth);
    const headers = { "Content-Type": "application/json" };
    if (auth) headers.Authorization = "Bearer " + auth;
    ctx.abortController = new AbortController();
    return {
      method: "POST",
      signal: ctx.abortController.signal,
      headers,
      body: JSON.stringify(body),
    };
  }

  function _parseSseLine(ctx, line, tokenCountRef) {
    if (!line.startsWith("data: ")) return;
    const data = line.slice(6).trim();
    if (data === "[DONE]" || !data) return;
    try {
      const json = JSON.parse(data);
      const delta = json.choices?.[0]?.delta?.content || "";
      if (delta) Ui.appendResponse(ctx, delta);
      if (json.usage) {
        tokenCountRef.value = json.usage.total_tokens ??
          (json.usage.prompt_tokens + json.usage.completion_tokens) ??
          tokenCountRef.value;
      }
    } catch (err) {
      console.warn("playground: failed to parse SSE data line:", line, err);
    }
  }

  async function _readStreamResponse(ctx, res) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const tokenCountRef = { value: null };
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) _parseSseLine(ctx, line, tokenCountRef);
      }
      const final = decoder.decode();
      if (final) {
        for (const line of final.split("\n")) _parseSseLine(ctx, line, tokenCountRef);
      }
    } catch (err) {
      console.warn("playground: failed to read stream response:", err);
    }
    return tokenCountRef.value;
  }

  async function _displayNonStreamResponse(ctx, res) {
    try {
      const json = await res.json();
      Ui.appendResponse(ctx, U.prettyJson(json));
      if (json.usage) {
        return json.usage.total_tokens ??
          (json.usage.prompt_tokens + json.usage.completion_tokens) ??
          null;
      }
    } catch (err) {
      console.warn("playground: failed to parse non-stream response:", err);
    }
    return null;
  }

  function _recordHistory(ctx, { url, status, ok, tokenCount, model, body }) {
    Ui.addHistoryEntry(ctx, {
      timestamp: Date.now(),
      url,
      status,
      ok,
      tokens: tokenCount,
      model,
      body,
    });
    Ui.updateChart(ctx, Ui.loadHistory());
  }

  function _setPills(ctx, status, ok, start) {
    Ui.setStatus(ctx, status, ok);
    ctx.els.timePill.textContent = "Time: " + ((performance.now() - start) / 1000).toFixed(2) + "s";
  }

  async function _handleNonOkResponse(ctx, res, { url, body }) {
    let errText = "";
    try {
      errText = await res.text();
    } catch (err) {
      console.warn("playground: failed to read error response body:", err);
    }
    Ui.appendResponse(ctx, errText || "HTTP " + res.status, true);
    _recordHistory(ctx, {
      url,
      status: res.status,
      ok: false,
      tokenCount: null,
      model: body.model,
      body,
    });
  }

  function _cancelInFlight() {
    ctx.abortController?.abort();
    ctx.isSending = false;
    setSendLoading(false);
  }

  function _validateBody(ctx, body) {
    if (!body.messages || !Array.isArray(body.messages) || body.messages.length === 0) {
      U.showToast(ctx, "请求体中 messages 不能为空", { error: true });
      return false;
    }
    return true;
  }

  async function sendRequest() {
    if (ctx.isSending) {
      _cancelInFlight();
      return;
    }

    let body;
    try {
      body = U.parseJsonBody(ctx);
    } catch (err) {
      U.showToast(ctx, err.message, { error: true });
      return;
    }
    if (!_validateBody(ctx, body)) return;

    ctx.isSending = true;
    setSendLoading(true);
    Ui.resetResponse(ctx);
    const start = performance.now();
    const url = "/v1/chat/completions";

    try {
      const res = await fetch(url, _buildRequestOptions(body));
      _setPills(ctx, res.status, res.ok, start);
      if (!res.ok) {
        await _handleNonOkResponse(ctx, res, { url, body });
        return;
      }
      const tokenCount = body.stream
        ? await _readStreamResponse(ctx, res)
        : await _displayNonStreamResponse(ctx, res);
      if (tokenCount !== null) els.tokensPill.textContent = "Tokens: " + tokenCount;
      _recordHistory(ctx, { url, status: res.status, ok: res.ok, tokenCount, model: body.model, body });
    } catch (err) {
      if (err.name === "AbortError") {
        Ui.appendResponse(ctx, "\n[请求已取消]", true);
      } else {
        Ui.setStatus(ctx, "ERR", false);
        _setPills(ctx, "ERR", false, start);
        Ui.appendResponse(ctx, "请求出错：" + err.message, true);
        console.warn("playground: request failed:", err);
      }
    } finally {
      ctx.isSending = false;
      ctx.abortController = null;
      setSendLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Escape" && ctx.isSending && ctx.abortController) {
      e.preventDefault();
      ctx.abortController.abort();
      return;
    }
    if (e.ctrlKey && e.key === "Enter" && !ctx.editor?.getDomNode?.()?.contains(document.activeElement)) {
      e.preventDefault();
      sendRequest();
    }
  }

  function handleResize() {
    ctx.tokenChart?.resize();
  }

  function initEditor() {
    require.config({ paths: { vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs" } });
    require(["vs/editor/editor.main"], () => {
      ctx.editor = monaco.editor.create(els.editor, {
        value: U.prettyJson(U.DEFAULT_BODY),
        language: "json",
        theme: "vs-dark",
        automaticLayout: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 13,
        lineNumbers: "on",
        renderLineHighlight: "line",
        folding: true,
        matchBrackets: "always",
        formatOnPaste: true,
        formatOnType: true,
      });

      ctx.editor.onDidChangeModelContent(() => U.syncControlsFromBody(ctx));
      ctx.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, sendRequest);
      U.syncControlsFromBody(ctx);
    });
  }

  function bindEvents() {
    els.auth.value = U.loadAuth();

    els.temperature.addEventListener("input", () => {
      els.tempValue.textContent = parseFloat(els.temperature.value).toFixed(1);
      U.updateBodyFromControls(ctx);
    });
    els.maxTokens.addEventListener("input", () => U.updateBodyFromControls(ctx));
    els.stream.addEventListener("change", () => U.updateBodyFromControls(ctx));
    els.model.addEventListener("change", () => U.updateBodyFromControls(ctx));

    els.sendBtn.addEventListener("click", sendRequest);
    els.copyCurlBtn.addEventListener("click", () => U.copyCurl(ctx));
    Ui.bindKeyModal(ctx);

    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", handleResize);
  }

  async function boot() {
    bindEvents();
    Ui.initChart(ctx);
    Ui.renderHistory(ctx);
    Ui.updateChart(ctx, Ui.loadHistory());
    await U.loadModels(ctx);
    initEditor();
  }

  boot();
})();
