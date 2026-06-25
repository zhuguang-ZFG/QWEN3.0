/* Usage statistics page logic (ECharts). */

(function () {
  "use strict";

  const token = LiMaAuth.getToken();
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  const API_PATH = "/device/v1/app/stats/usage";
  const periodSelect = document.getElementById("periodSelect");
  const totalTokens = document.getElementById("totalTokens");
  const totalRequests = document.getElementById("totalRequests");
  const estimatedCost = document.getElementById("estimatedCost");
  const detailsBody = document.getElementById("detailsBody");
  const pager = document.getElementById("pager");

  let currentDays = 30;
  let currentPage = 1;
  let currentPageSize = 20;
  let tokenChart, requestChart, capabilityChart;

  function formatNumber(n) {
    if (n === null || n === undefined) return "—";
    return Number(n).toLocaleString("zh-CN");
  }

  function initCharts() {
    const theme = {
      textStyle: { fontFamily: "Geist, sans-serif" },
      title: { textStyle: { color: "#f1f5f9" } },
      legend: { textStyle: { color: "#94a3b8" } },
      tooltip: { backgroundColor: "rgba(10,10,20,0.9)", borderColor: "rgba(255,255,255,0.1)", textStyle: { color: "#f1f5f9" } },
    };
    tokenChart = echarts.init(document.getElementById("tokenChart"));
    requestChart = echarts.init(document.getElementById("requestChart"));
    capabilityChart = echarts.init(document.getElementById("capabilityChart"));
    window.addEventListener("resize", () => {
      tokenChart.resize();
      requestChart.resize();
      capabilityChart.resize();
    });
  }

  function renderDailyCharts(daily) {
    const dates = daily.map((d) => d.date);
    const tokens = daily.map((d) => d.tokens);
    const requests = daily.map((d) => d.requests);

    const common = {
      grid: { left: 16, right: 16, top: 24, bottom: 24, containLabel: true },
      xAxis: { type: "category", data: dates, axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } }, axisLabel: { color: "#94a3b8" } },
      yAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } }, axisLabel: { color: "#94a3b8" } },
    };

    tokenChart.setOption({
      ...common,
      color: ["#06b6d4"],
      tooltip: { trigger: "axis" },
      series: [{ data: tokens, type: "line", smooth: true, areaStyle: { opacity: 0.2 }, symbol: "none" }],
    });

    requestChart.setOption({
      ...common,
      color: ["#8b5cf6"],
      tooltip: { trigger: "axis" },
      series: [{ data: requests, type: "bar", barWidth: "50%" }],
    });
  }

  function renderCapabilityChart(caps) {
    capabilityChart.setOption({
      color: ["#06b6d4", "#8b5cf6", "#f59e0b"],
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { color: "#94a3b8" } },
      series: [{
        type: "pie",
        radius: ["40%", "70%"],
        avoidLabelOverlap: false,
        label: { color: "#f1f5f9" },
        data: caps.map((c) => ({ value: c.tokens, name: c.capability })),
      }],
    });
  }

  function renderDetails(items, page, pageSize, total) {
    detailsBody.innerHTML = "";
    if (items.length === 0) {
      detailsBody.innerHTML = '<tr><td colspan="4" class="empty">暂无明细</td></tr>';
      pager.innerHTML = "";
      return;
    }
    items.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${escapeHtml(item.date)}</td><td>${escapeHtml(item.type)}</td><td>${formatNumber(item.tokens)}</td><td>¥${Number(item.cost || 0).toFixed(4)}</td>`;
      detailsBody.appendChild(tr);
    });

    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    pager.innerHTML =
      `<button ${page <= 1 ? "disabled" : ""} data-page="${page - 1}">上一页</button>` +
      `<span style="color:var(--text-muted); padding:6px 0;">${page} / ${totalPages}</span>` +
      `<button ${page >= totalPages ? "disabled" : ""} data-page="${page + 1}">下一页</button>`;
  }

  function escapeHtml(str) {
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  async function loadUsage() {
    try {
      const query = `?days=${currentDays}&page=${currentPage}&page_size=${currentPageSize}`;
      const data = await LiMaAPI.get(API_PATH + query, token);
      const summary = data.summary || {};
      totalTokens.textContent = formatNumber(summary.totalTokens);
      totalRequests.textContent = formatNumber(summary.totalRequests);
      estimatedCost.textContent = "¥" + Number(summary.estimatedCost || 0).toFixed(4);

      renderDailyCharts(data.daily || []);
      renderCapabilityChart(data.byCapability || []);
      const details = data.details || {};
      renderDetails(details.items || [], details.page || 1, details.pageSize || currentPageSize, details.total || 0);
    } catch (err) {
      console.error(err);
      detailsBody.innerHTML = `<tr><td colspan="4" class="empty">加载失败：${escapeHtml(err.message || "未知错误")}</td></tr>`;
    }
  }

  periodSelect.addEventListener("change", function () {
    currentDays = parseInt(this.value, 10);
    currentPage = 1;
    loadUsage();
  });

  pager.addEventListener("click", function (e) {
    const btn = e.target.closest("button[data-page]");
    if (!btn || btn.disabled) return;
    currentPage = parseInt(btn.dataset.page, 10);
    loadUsage();
  });

  initCharts();
  loadUsage();
})();
