// LiMa 星云 API Playground — UI helpers (history, charts, modal, response)
(function (global) {
  "use strict";

  const U = global.PgUtils;
  const LS_KEY_HISTORY = U.LS_KEY_HISTORY;
  const HISTORY_LIMIT = U.HISTORY_LIMIT;

  function loadHistory() {
    try {
      const raw = localStorage.getItem(LS_KEY_HISTORY);
      return raw ? JSON.parse(raw) : [];
    } catch (err) {
      console.warn("playground: failed to load history:", err);
      return [];
    }
  }

  function saveHistory(history) {
    try {
      localStorage.setItem(LS_KEY_HISTORY, JSON.stringify(history));
    } catch (err) {
      console.warn("playground: failed to save history:", err);
    }
  }

  function addHistoryEntry(ctx, entry) {
    const history = loadHistory();
    history.unshift(entry);
    while (history.length > HISTORY_LIMIT) history.pop();
    saveHistory(history);
    renderHistory(ctx);
  }

  function _createHistoryEmpty() {
    const el = document.createElement("div");
    el.className = "pg-history-empty";
    el.textContent = "暂无历史请求";
    return el;
  }

  function _createHistoryItem(ctx, item) {
    const el = document.createElement("div");
    el.className = "pg-history-item";

    const top = document.createElement("div");
    top.className = "pg-history-top";

    const time = document.createElement("span");
    time.className = "pg-history-time";
    time.textContent = new Date(item.timestamp).toLocaleString("zh-CN", {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
    });

    const status = document.createElement("span");
    status.className = "pg-history-status " + (item.ok ? "ok" : "error");
    status.textContent = item.status || "—";

    top.appendChild(time);
    top.appendChild(status);

    const url = document.createElement("div");
    url.className = "pg-history-url";
    url.textContent = item.url || "/v1/chat/completions";

    const tokens = document.createElement("div");
    tokens.className = "pg-history-tokens";
    tokens.textContent = "Tokens: " + (item.tokens ?? "—") + " · " + (item.model || "—");

    el.appendChild(top);
    el.appendChild(url);
    el.appendChild(tokens);
    el.addEventListener("click", () => loadHistoryItem(ctx, item));
    return el;
  }

  function renderHistory(ctx) {
    const history = loadHistory();
    ctx.els.historyCount.textContent = history.length + " / " + HISTORY_LIMIT;
    ctx.els.historyList.innerHTML = "";

    if (history.length === 0) {
      ctx.els.historyList.appendChild(_createHistoryEmpty());
      return;
    }
    for (const item of history) {
      ctx.els.historyList.appendChild(_createHistoryItem(ctx, item));
    }
  }

  function loadHistoryItem(ctx, item) {
    if (!item || !item.body) return;
    try {
      const body = typeof item.body === "string" ? JSON.parse(item.body) : item.body;
      U.setJsonBody(ctx, body);
      U.syncControlsFromBody(ctx);
      ctx.editor?.focus?.();
      U.announce(ctx, "已加载历史请求");
      U.showToast(ctx, "已加载历史请求");
    } catch (err) {
      console.warn("playground: failed to load history item:", err);
      U.showToast(ctx, "无法加载历史请求：" + err.message, { error: true });
    }
  }

  function resetResponse(ctx) {
    ctx.els.responseBody.textContent = "";
    ctx.els.statusPill.textContent = "Status: —";
    ctx.els.statusPill.className = "pg-meta-pill";
    ctx.els.timePill.textContent = "Time: —";
    ctx.els.tokensPill.textContent = "Tokens: —";
  }

  function setStatus(ctx, status, ok) {
    ctx.els.statusPill.textContent = "Status: " + (status ?? "—");
    ctx.els.statusPill.className = "pg-meta-pill " + (ok ? "ok" : "error");
  }

  function appendResponse(ctx, text, isError = false) {
    const span = document.createElement("span");
    span.textContent = text;
    if (isError) span.className = "pg-chunk-error";
    ctx.els.responseBody.appendChild(span);
    ctx.els.responseBody.scrollTop = ctx.els.responseBody.scrollHeight;
  }

  function initChart(ctx) {
    if (typeof echarts === "undefined") return;
    ctx.tokenChart = echarts.init(document.getElementById("pgTokenChart"));
    updateChart(ctx, []);
  }

  function updateChart(ctx, history) {
    if (!ctx.tokenChart) return;
    const data = history.slice(0, 10).reverse();
    const hasData = data.length > 0;
    const option = {
      backgroundColor: "transparent",
      grid: { top: 24, right: 16, bottom: 24, left: 48, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 17, 26, 0.95)",
        borderColor: "rgba(255,255,255,0.1)",
        textStyle: { color: "#f1f5f9", fontSize: 11 },
      },
      xAxis: {
        type: "category",
        data: hasData ? data.map((_, i) => "Req " + (i + 1)) : ["—"],
        axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
        axisLabel: { color: "#64748b", fontSize: 10 },
      },
      yAxis: {
        type: "value",
        name: "Tokens",
        nameTextStyle: { color: "#64748b", fontSize: 10 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
        axisLabel: { color: "#64748b", fontSize: 10 },
      },
      series: [{
        data: hasData ? data.map((h) => h.tokens ?? 0) : [0],
        type: "bar",
        barWidth: "50%",
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#06b6d4" },
            { offset: 1, color: "rgba(6, 182, 212, 0.2)" },
          ]),
        },
      }],
    };
    ctx.tokenChart.setOption(option);
  }

  function bindKeyModal(ctx) {
    const {
      keyModalOverlay, keyModalInput, keyModalSave,
      keyModalCancel, setKeyBtn, auth,
    } = ctx.els;
    if (!keyModalOverlay) return;

    function open() {
      keyModalInput.value = auth.value;
      keyModalOverlay.classList.add("open");
      keyModalInput.focus();
    }

    function close() {
      keyModalOverlay.classList.remove("open");
      setKeyBtn.focus();
    }

    function save() {
      const value = keyModalInput.value.trim();
      auth.value = value;
      U.saveAuth(value);
      U.showToast(ctx, value ? "API Key 已保存到本地" : "API Key 已清除");
      close();
    }

    setKeyBtn.addEventListener("click", open);
    keyModalSave.addEventListener("click", save);
    keyModalCancel.addEventListener("click", close);
    keyModalOverlay.addEventListener("click", (e) => {
      if (e.target === keyModalOverlay) close();
    });
    keyModalInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") save();
      if (e.key === "Escape") close();
    });
  }

  global.PgUi = {
    loadHistory,
    saveHistory,
    addHistoryEntry,
    renderHistory,
    loadHistoryItem,
    resetResponse,
    setStatus,
    appendResponse,
    initChart,
    updateChart,
    bindKeyModal,
  };
})(window);
