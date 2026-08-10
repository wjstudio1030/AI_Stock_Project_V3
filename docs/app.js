// docs/app.js

const DATA_BASE_URL = "./data";

const MA_COLORS = {
  MA5: "#f2b705",
  MA10: "#4d8dff",
  MA20: "#a259ff",
  MA60: "#ff6fa5",
};

const priceChartEl = document.getElementById("price-chart");
const kdChartEl = document.getElementById("kd-chart"); // 新增: KD圖表容器
const rsiChartEl = document.getElementById("rsi-chart");
const instChartEl = document.getElementById("institutional-chart");
const marginChartEl = document.getElementById("margin-chart");
const valuationChartEl = document.getElementById("valuation-chart");
const selectEl = document.getElementById("stock-select");
const pageSelectEl = document.getElementById("page-select");
const pageGroupEls = document.querySelectorAll(".page-group");
const updatedAtEl = document.getElementById("updated-at");
const downloadCsvBtn = document.getElementById("download-csv"); // 新增: CSV下載按鈕
const themeToggleBtn = document.getElementById("theme-toggle");
let isDarkMode = localStorage.getItem("ai-stock-theme") === "dark" ||
  (!localStorage.getItem("ai-stock-theme") && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
document.documentElement.setAttribute("data-theme", isDarkMode ? "dark" : "light");
const maLegendEl = document.getElementById("ma-legend");
const fundHeadEl = document.getElementById("fund-table-head");
const fundBodyEl = document.getElementById("fund-table-body");
const stockLabelEl = document.getElementById("stock-label");
const trendNarrativeEl = document.getElementById("trend-narrative");
const probStateLabelEl = document.getElementById("prob-state-label");
const probBarUpEl = document.getElementById("prob-bar-up");
const probBarDownEl = document.getElementById("prob-bar-down");
const probUpPctEl = document.getElementById("prob-up-pct");
const probDownPctEl = document.getElementById("prob-down-pct");
const probSampleSizeEl = document.getElementById("prob-sample-size");
const newsTotalEl = document.getElementById("news-total");
const newsBarPosEl = document.getElementById("news-bar-pos");
const newsBarNeuEl = document.getElementById("news-bar-neu");
const newsBarNegEl = document.getElementById("news-bar-neg");
const newsPosCountEl = document.getElementById("news-pos-count");
const newsNeuCountEl = document.getElementById("news-neu-count");
const newsNegCountEl = document.getElementById("news-neg-count");
const newsListEl = document.getElementById("news-list");
const sentimentChartEl = document.getElementById("sentiment-chart");
const sentimentHistoryTotalEl = document.getElementById("sentiment-history-total");
let sentimentChart, sentimentSeries;
const trackSummaryTotalEl = document.getElementById("track-summary-total");
const trackSummaryCorrectEl = document.getElementById("track-summary-correct");
const trackSummaryRateEl = document.getElementById("track-summary-rate");
const trackCalDetailsEl = document.getElementById("track-calendar-details");
const trackCalSummaryEl = document.getElementById("track-calendar-summary");
const trackCalPrevEl = document.getElementById("track-cal-prev");
const trackCalNextEl = document.getElementById("track-cal-next");
const trackCalMonthLabelEl = document.getElementById("track-cal-month-label");
const trackCalGridEl = document.getElementById("track-cal-grid");
const trackDateResultEl = document.getElementById("track-date-result");
const mlStateLabelEl = document.getElementById("ml-state-label");
const mlBarUpEl = document.getElementById("ml-bar-up");
const mlBarDownEl = document.getElementById("ml-bar-down");
const mlUpPctEl = document.getElementById("ml-up-pct");
const mlDownPctEl = document.getElementById("ml-down-pct");
const mlTrackSummaryTotalEl = document.getElementById("ml-track-summary-total");
const mlTrackSummaryCorrectEl = document.getElementById("ml-track-summary-correct");
const mlTrackSummaryRateEl = document.getElementById("ml-track-summary-rate");
const mlTrackCalDetailsEl = document.getElementById("ml-track-calendar-details");
const mlTrackCalSummaryEl = document.getElementById("ml-track-calendar-summary");
const mlTrackCalPrevEl = document.getElementById("ml-track-cal-prev");
const mlTrackCalNextEl = document.getElementById("ml-track-cal-next");
const mlTrackCalMonthLabelEl = document.getElementById("ml-track-cal-month-label");
const mlTrackCalGridEl = document.getElementById("ml-track-cal-grid");
const mlTrackDateResultEl = document.getElementById("ml-track-date-result");
const instAnomalyBadgesEl = document.getElementById("inst-anomaly-badges");
const overviewStockTitleEl = document.getElementById("overview-stock-title");
const overviewUpdatedEl = document.getElementById("overview-updated");
const overviewCloseEl = document.getElementById("overview-close");
const overviewChangeEl = document.getElementById("overview-change");
const overviewPerEl = document.getElementById("overview-per");
const overviewPbrEl = document.getElementById("overview-pbr");
const overviewRsiEl = document.getElementById("overview-rsi");
const overviewRsiStateEl = document.getElementById("overview-rsi-state");
const overviewMaStateEl = document.getElementById("overview-ma-state");
const overviewInstitutionalEl = document.getElementById("overview-institutional");
const overviewNextDayEl = document.getElementById("overview-next-day");
const overviewNewsEl = document.getElementById("overview-news");
const overviewAnomalyBannerEl = document.getElementById("overview-anomaly-banner");
const staleWarningEl = document.getElementById("stale-warning");
const compareCountEl = document.getElementById("compare-count");
const compareTableBodyEl = document.getElementById("compare-table-body");
const checklistContainerEl = document.getElementById("checklist-container");
const STALE_WARNING_DAYS = 4;

const marketSelectEl = document.getElementById("market-select");

let manifestStockIds = [];
let compareDataLoaded = false;
let compareRows = [];
let compareSort = { key: "stock_id", direction: "asc" };

let manifestStockNames = {};
let currentPage = "price";

let priceChart, kdChart, rsiChart, instChart, marginChart, valuationChart; // 新增: kdChart
let candleSeries, kSeries, dSeries, rsiSeries14, rsiSeries6; // 新增: kSeries, dSeries
let foreignSeries, trustSeries, dealerSeries, marginBalanceSeries, shortBalanceSeries;
let perSeries, pbrSeries;
let maSeriesMap = {};
let isSyncingRange = false;

let currentMarket = "TW"; 
let globalStockIds = [];
let globalStockNames = {};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTaiwanTime(dateStr) {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" });
}

function chartBaseOptions() {
  return {
    layout: {
      background: { color: "transparent" },
      textColor: isDarkMode ? "#c7cad1" : "#64748b",
    },
    grid: {
      vertLines: { color: isDarkMode ? "#22252f" : "#f1f5f9" },
      horzLines: { color: isDarkMode ? "#22252f" : "#f1f5f9" },
    },
    rightPriceScale: { borderColor: isDarkMode ? "#262a36" : "#e2e8f0" },
    leftPriceScale: { borderColor: isDarkMode ? "#262a36" : "#e2e8f0" },
    timeScale: { borderColor: isDarkMode ? "#262a36" : "#e2e8f0" },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  };
}

function initCharts() {
  priceChart = LightweightCharts.createChart(priceChartEl, {
    ...chartBaseOptions(),
    width: priceChartEl.clientWidth,
    height: priceChartEl.clientHeight,
  });

  candleSeries = priceChart.addCandlestickSeries({
    upColor: "#d6382e",
    downColor: "#1e9e5a",
    borderUpColor: "#d6382e",
    borderDownColor: "#1e9e5a",
    wickUpColor: "#d6382e",
    wickDownColor: "#1e9e5a",
  });

  // ---------- KD 圖表 ----------
  kdChart = LightweightCharts.createChart(kdChartEl, {
    ...chartBaseOptions(),
    width: kdChartEl.clientWidth,
    height: kdChartEl.clientHeight,
    rightPriceScale: { borderColor: isDarkMode ? "#262a36" : "#e2e8f0", scaleMargins: { top: 0.1, bottom: 0.1 } },
  });

  kSeries = kdChart.addLineSeries({
    color: "#4d8dff", lineWidth: 1.5,
    autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
  });
  dSeries = kdChart.addLineSeries({ color: "#f2b705", lineWidth: 1.5 });

  // ---------- RSI 圖表 ----------
  rsiChart = LightweightCharts.createChart(rsiChartEl, {
    ...chartBaseOptions(),
    width: rsiChartEl.clientWidth,
    height: rsiChartEl.clientHeight,
    rightPriceScale: { borderColor: isDarkMode ? "#262a36" : "#e2e8f0", scaleMargins: { top: 0.1, bottom: 0.1 } },
  });

  rsiSeries14 = rsiChart.addLineSeries({
    color: "#4d8dff", lineWidth: 2,
    autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
  });
  rsiSeries6 = rsiChart.addLineSeries({ color: "#f2b705", lineWidth: 1 });

  // ---------- 三大法人買賣超圖 ----------
  instChart = LightweightCharts.createChart(instChartEl, {
    ...chartBaseOptions(),
    width: instChartEl.clientWidth,
    height: instChartEl.clientHeight,
  });
  foreignSeries = instChart.addLineSeries({ color: "#d6382e", lineWidth: 1.5 });
  trustSeries = instChart.addLineSeries({ color: "#f2b705", lineWidth: 1.5 });
  dealerSeries = instChart.addLineSeries({ color: "#4d8dff", lineWidth: 1.5 });

  // ---------- 融資融券圖 ----------
  marginChart = LightweightCharts.createChart(marginChartEl, {
    ...chartBaseOptions(),
    width: marginChartEl.clientWidth,
    height: marginChartEl.clientHeight,
    leftPriceScale: { visible: true, borderColor: isDarkMode ? "#262a36" : "#e2e8f0" },
  });
  marginBalanceSeries = marginChart.addLineSeries({
    color: "#4d8dff", lineWidth: 1.5, priceScaleId: "left",
  });
  shortBalanceSeries = marginChart.addLineSeries({
    color: "#ff6fa5", lineWidth: 1.5, priceScaleId: "right",
  });

  // ---------- 本益比 / 淨值比 ----------
  valuationChart = LightweightCharts.createChart(valuationChartEl, {
    ...chartBaseOptions(),
    width: valuationChartEl.clientWidth,
    height: valuationChartEl.clientHeight,
    leftPriceScale: { visible: true, borderColor: isDarkMode ? "#262a36" : "#e2e8f0" },
  });
  perSeries = valuationChart.addLineSeries({
    color: "#4d8dff", lineWidth: 1.5, priceScaleId: "left",
  });
  pbrSeries = valuationChart.addLineSeries({
    color: "#ff6fa5", lineWidth: 1.5, priceScaleId: "right",
  });

  // ---------- 新聞情緒趨勢圖 ----------
  sentimentChart = LightweightCharts.createChart(sentimentChartEl, {
    ...chartBaseOptions(),
    width: sentimentChartEl.clientWidth,
    height: sentimentChartEl.clientHeight,
  });
  sentimentSeries = sentimentChart.addLineSeries({
    color: "#4d8dff", lineWidth: 1.5,
    autoscaleInfoProvider: () => ({ priceRange: { minValue: -1, maxValue: 1 } }),
  });

  // 把 kdChart 也加進同步群組
  const syncGroup = [priceChart, kdChart, rsiChart, instChart, marginChart, valuationChart];
  syncGroup.forEach((source) => {
    syncGroup.forEach((target) => {
      if (source !== target) syncTimeScales(source, target);
    });
  });

  window.addEventListener("resize", () => resizeChartsForPage(currentPage));
}

function resizeChartsForPage(page) {
  if (page === "price") {
    priceChart.resize(priceChartEl.clientWidth, priceChartEl.clientHeight);
  } else if (page === "indicators") {
    kdChart.resize(kdChartEl.clientWidth, kdChartEl.clientHeight); // 新增: KD圖表resize
    rsiChart.resize(rsiChartEl.clientWidth, rsiChartEl.clientHeight);
    instChart.resize(instChartEl.clientWidth, instChartEl.clientHeight);
    marginChart.resize(marginChartEl.clientWidth, marginChartEl.clientHeight);
  } else if (page === "fundamentals") {
    valuationChart.resize(valuationChartEl.clientWidth, valuationChartEl.clientHeight);
  } else if (page === "news") {
    sentimentChart.resize(sentimentChartEl.clientWidth, sentimentChartEl.clientHeight);
  }
}

function setActivePage(page) {
  currentPage = page;
  pageGroupEls.forEach((el) => {
    el.style.display = el.dataset.page === page ? "" : "none";
  });
  requestAnimationFrame(() => resizeChartsForPage(page));

  if (page === "compare") {
    loadCompareTable();
  }
}

function syncTimeScales(source, target) {
  source.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (isSyncingRange || !range) return;
    isSyncingRange = true;
    target.timeScale().setVisibleLogicalRange(range);
    isSyncingRange = false;
  });
}

function clearMaSeries() {
  Object.values(maSeriesMap).forEach((s) => priceChart.removeSeries(s));
  maSeriesMap = {};
  maLegendEl.innerHTML = "";
}

function renderMaSeries(maData) {
  clearMaSeries();
  Object.entries(maData).forEach(([key, points]) => {
    if (!points || points.length === 0) return;
    const color = MA_COLORS[key] || "#888";
    const series = priceChart.addLineSeries({ color, lineWidth: 1.5 });
    series.setData(points);
    maSeriesMap[key] = series;

    const tag = document.createElement("span");
    tag.style.color = color;
    tag.textContent = key;
    maLegendEl.appendChild(tag);
  });
}

const FUND_ROWS = [
  { key: "eps", label: "EPS(元)", digits: 2 },
  { key: "revenue_yi", label: "營收(億)", digits: 1 },
  { key: "gross_margin", label: "毛利率(%)", digits: 1 },
  { key: "operating_margin", label: "營益率(%)", digits: 1 },
  { key: "roe", label: "ROE(%)", digits: 1 },
  { key: "roa", label: "ROA(%)", digits: 1 },
  { key: "debt_ratio", label: "負債比(%)", digits: 1 },
  { key: "operating_cash_flow_yi", label: "營業現金流(億)", digits: 1 },
];

function formatQuarterLabel(dateStr) {
  const d = new Date(dateStr);
  const year = d.getFullYear() % 100;
  const month = d.getMonth() + 1;
  const quarter = Math.floor((month - 1) / 3) + 1;
  return `${year}Q${quarter}`;
}

function renderFundamentalsTable(fundamentals) {
  fundHeadEl.innerHTML = "";
  fundBodyEl.innerHTML = "";

  const quarters = fundamentals?.quarters || [];
  if (quarters.length === 0) {
    fundHeadEl.innerHTML = `<th>季度</th><th>無資料</th>`;
    return;
  }

  let headHtml = `<th>季度</th>`;
  quarters.forEach((q) => {
    headHtml += `<th>${formatQuarterLabel(q.date)}</th>`;
  });
  fundHeadEl.innerHTML = headHtml;

  FUND_ROWS.forEach((rowDef) => {
    let rowHtml = `<td>${rowDef.label}</td>`;
    quarters.forEach((q) => {
      const v = q[rowDef.key];
      rowHtml += `<td>${v === null || v === undefined ? "-" : v.toFixed(rowDef.digits)}</td>`;
    });
    const tr = document.createElement("tr");
    tr.innerHTML = rowHtml;
    fundBodyEl.appendChild(tr);
  });
}

function renderAnalysis(analysis) {
  const narrative = analysis?.narrative || "目前沒有足夠資料可以產生分析。";
  trendNarrativeEl.textContent = narrative;

  const nextDay = analysis?.next_day || {};
  if (nextDay.up_pct === null || nextDay.up_pct === undefined) {
    probStateLabelEl.textContent = nextDay.state_label || "資料不足";
    probBarUpEl.style.width = "50%";
    probBarDownEl.style.width = "50%";
    probUpPctEl.textContent = "-";
    probDownPctEl.textContent = "-";
    probSampleSizeEl.textContent = "";
    return;
  }

  probStateLabelEl.textContent = nextDay.state_label || "";
  probBarUpEl.style.width = `${nextDay.up_pct}%`;
  probBarDownEl.style.width = `${nextDay.down_pct}%`;
  probUpPctEl.textContent = nextDay.up_pct;
  probDownPctEl.textContent = nextDay.down_pct;
  probSampleSizeEl.textContent = `樣本數: ${nextDay.sample_size} 天`;
}

const SENTIMENT_TAG_CLASS = { "利多": "pos", "利空": "neg", "中性": "neu" };

function renderSentimentHistory(news) {
  const history = news?.sentiment_history || [];
  const total = news?.sentiment_history_total || 0;

  sentimentHistoryTotalEl.textContent = `已累積 ${total} 個交易日`;

  const points = history
    .filter((h) => h.total > 0)
    .map((h) => ({ time: h.date, value: h.score }));

  sentimentSeries.setData(points);
  sentimentChart.timeScale().fitContent();
}

function renderNews(news) {
  // 先清空原本的新聞列表
  newsListEl.innerHTML = "";

  // 根據當前市場決定渲染邏輯
  if (currentMarket === "TW") {
    // ==========================================
    // 台股模式：保留原本的所有邏輯 (含情緒統計圖)
    // ==========================================
    const total = news?.total || 0;
    const pos = news?.positive_count || 0;
    const neu = news?.neutral_count || 0;
    const neg = news?.negative_count || 0;

    // 更新情緒統計長條圖
    if (newsTotalEl) newsTotalEl.textContent = `近 ${total} 則相關新聞`;
    if (total === 0) {
      if (newsBarPosEl) newsBarPosEl.style.width = "0%";
      if (newsBarNeuEl) newsBarNeuEl.style.width = "100%";
      if (newsBarNegEl) newsBarNegEl.style.width = "0%";
    } else {
      if (newsBarPosEl) newsBarPosEl.style.width = `${(pos / total) * 100}%`;
      if (newsBarNeuEl) newsBarNeuEl.style.width = `${(neu / total) * 100}%`;
      if (newsBarNegEl) newsBarNegEl.style.width = `${(neg / total) * 100}%`;
    }
    if (newsPosCountEl) newsPosCountEl.textContent = pos;
    if (newsNeuCountEl) newsNeuCountEl.textContent = neu;
    if (newsNegCountEl) newsNegCountEl.textContent = neg;

    // 渲染台股新聞列表
    const articles = news?.articles || [];
    if (articles.length === 0) {
      const li = document.createElement("li");
      li.textContent = "目前沒有相關新聞資料。";
      newsListEl.appendChild(li);
      return;
    }

    articles.forEach((a) => {
      const li = document.createElement("li");
      const tagClass = SENTIMENT_TAG_CLASS ? (SENTIMENT_TAG_CLASS[a.sentiment] || "neu") : "neu";

      const tag = document.createElement("span");
      tag.className = `news-tag ${tagClass}`;
      tag.textContent = a.sentiment;

      const titleLink = document.createElement("a");
      titleLink.className = "news-item-title";
      titleLink.href = a.link || "#";
      titleLink.target = "_blank";
      titleLink.rel = "noopener noreferrer";
      titleLink.textContent = a.title;

      const meta = document.createElement("span");
      meta.className = "news-item-meta";
      meta.textContent = `${a.source || ""} · ${a.date || ""}`;

      li.appendChild(tag);
      li.appendChild(titleLink);
      li.appendChild(meta);
      newsListEl.appendChild(li);
    });

  } else {
    // ==========================================
    // 全球股模式：雙語國際新聞渲染
    const articles = Array.isArray(news) ? news : [];

    if (articles.length === 0) {
      const li = document.createElement("li");
      li.textContent = "目前沒有國際新聞資料。";
      newsListEl.appendChild(li);
      return;
    }

    articles.forEach((a) => {
      const li = document.createElement("li");
      // 加上一些簡單的排版讓雙語新聞更好看
      li.style.listStyle = "none"; // 隱藏預設的黑圓點
      li.style.display = "flex";
      li.style.flexDirection = "column";
      li.style.alignItems = "flex-start";
      li.style.gap = "6px";
      li.style.padding = "10px 0";
      li.style.borderBottom = "1px solid var(--border-color)";

      // 1. 中文大標題 (超連結)
      const titleLink = document.createElement("a");
      titleLink.className = "news-item-title";
      titleLink.href = a.link || "#";
      titleLink.target = "_blank";
      titleLink.rel = "noopener noreferrer";
      titleLink.textContent = a.title_zh || a.title_en; 
      titleLink.style.fontSize = "1.05rem";
      titleLink.style.fontWeight = "600";
      titleLink.style.lineHeight = "1.4";

      // 2. 英文原標題 (灰色斜體小字)
      const titleEn = document.createElement("div");
      titleEn.textContent = a.title_en;
      titleEn.style.fontSize = "0.85rem";
      titleEn.style.color = "var(--text-color)";
      titleEn.style.opacity = "0.7";
      titleEn.style.fontStyle = "italic";

      // 3. 來源與時間
      const meta = document.createElement("span");
      meta.className = "news-item-meta";
      meta.textContent = `${a.source || "Yahoo Finance"} · ${a.time || "無時間"}`;
      meta.style.fontSize = "0.8rem";

      li.appendChild(titleLink);
      // 如果翻譯成功，中英不同才顯示英文原標
      if (a.title_zh && a.title_zh !== a.title_en) {
         li.appendChild(titleEn); 
      }
      li.appendChild(meta);
      newsListEl.appendChild(li);
    });
  }
}

const TRACK_DIRECTION_TEXT = { up: "漲", down: "跌" };

function renderTrackDateDetail(record, resultEl) {
  resultEl.innerHTML = "";
  if (!record) {
    resultEl.innerHTML = `<div class="track-date-empty">請選擇上方的日期查看該次預測結果</div>`;
    return;
  }
  const guessTag = record.correct
    ? `<span class="track-tag hit">✓ 猜中</span>`
    : `<span class="track-tag miss">✕ 猜錯</span>`;
  resultEl.innerHTML = `
    <div class="track-date-row">
      <span>預測日: <b>${escapeHtml(record.predict_date)}</b></span>
      <span>當時猜: <b>${TRACK_DIRECTION_TEXT[record.predicted_direction] || "-"}</b></span>
      <span>驗證日: <b>${escapeHtml(record.target_date || "-")}</b></span>
      <span>實際結果: <b>${TRACK_DIRECTION_TEXT[record.actual_direction] || "-"}</b></span>
      <span>${guessTag}</span>
    </div>
  `;
}

function renderBreakdownList(breakdown, listEl) {
  listEl.innerHTML = "";
  if (!breakdown || breakdown.length === 0) {
    listEl.innerHTML = `<div class="error-breakdown-empty">目前樣本數不足,還無法分組統計</div>`;
    return;
  }
  breakdown.forEach((item) => {
    const row = document.createElement("div");
    row.className = "error-breakdown-row";
    const pct = item.accuracy_pct != null ? item.accuracy_pct : 0;
    row.innerHTML = `
      <span class="error-breakdown-label">${escapeHtml(item.label)}</span>
      <div class="error-breakdown-bar-wrap"><div class="error-breakdown-bar" style="width:${pct}%"></div></div>
      <span class="error-breakdown-value">${item.accuracy_pct != null ? item.accuracy_pct + "%" : "-"}(${item.correct}/${item.total})</span>
    `;
    listEl.appendChild(row);
  });
}

function renderErrorAnalysis(errorAnalysis, els) {
  const analysis = errorAnalysis || {};
  renderBreakdownList(analysis.confidence_breakdown, els.confidenceEl);
  renderBreakdownList(analysis.news_breakdown, els.newsEl);

  if (els.matchEl) {
    renderBreakdownList(analysis.match_level_breakdown, els.matchEl);
  }
  if (els.matchGroupEl) {
    const hasMatchData = analysis.match_level_breakdown && analysis.match_level_breakdown.length > 0;
    els.matchGroupEl.style.display = hasMatchData ? "" : "none";
  }
}

function setupCalendarLookup(recent, calEls, resultEl) {
  const { detailsEl, summaryEl, prevEl, nextEl, monthLabelEl, gridEl } = calEls;
  const dateMap = {};
  const recordByDate = {};
  recent.forEach((r) => {
    const ym = r.predict_date.slice(0, 7);
    if (!dateMap[ym]) dateMap[ym] = new Set();
    dateMap[ym].add(r.predict_date.slice(8, 10));
    recordByDate[r.predict_date] = r;
  });

  if (recent.length === 0) {
    summaryEl.textContent = "請選擇日期";
    monthLabelEl.textContent = "";
    gridEl.innerHTML = "";
    prevEl.disabled = true;
    nextEl.disabled = true;
    resultEl.innerHTML = `<div class="track-date-empty">目前還沒有累積到任何已驗證的預測記錄,持續運作一段時間後才會開始有資料可以查詢。</div>`;
    return;
  }

  const allYm = Object.keys(dateMap).sort();
  const earliestYm = allYm[0];

  let viewYear = parseInt(recent[0].predict_date.slice(0, 4), 10);
  let viewMonth = parseInt(recent[0].predict_date.slice(5, 7), 10);
  let selectedDate = recent[0].predict_date;

  function ymKey(y, m) {
    return `${y}-${String(m).padStart(2, "0")}`;
  }

  function renderGrid() {
    const ym = ymKey(viewYear, viewMonth);
    monthLabelEl.textContent = `${viewYear}年${viewMonth}月`;
    prevEl.disabled = ym <= earliestYm;

    // Allow navigation through the current calendar month.
    // Future dates stay disabled until prediction records exist.
    const now = new Date();
    const currentYm = ymKey(now.getFullYear(), now.getMonth() + 1);
    nextEl.disabled = ym >= currentYm;

    gridEl.innerHTML = "";
    const firstDay = new Date(viewYear, viewMonth - 1, 1);
    const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
    const startWeekday = firstDay.getDay();

    for (let i = 0; i < startWeekday; i++) {
      const empty = document.createElement("div");
      empty.className = "track-cal-cell empty";
      gridEl.appendChild(empty);
    }

    const daysWithData = dateMap[ym] || new Set();
    for (let day = 1; day <= daysInMonth; day++) {
      const dayStr = String(day).padStart(2, "0");
      const fullDate = `${ym}-${dayStr}`;
      const cell = document.createElement("div");
      cell.textContent = day;

      if (daysWithData.has(dayStr)) {
        cell.className = "track-cal-cell has-data" + (fullDate === selectedDate ? " selected" : "");
        cell.addEventListener("click", () => {
          selectedDate = fullDate;
          summaryEl.textContent = fullDate;
          renderTrackDateDetail(recordByDate[fullDate], resultEl);
          renderGrid();
          detailsEl.open = false;
        });
      } else {
        cell.className = "track-cal-cell disabled";
      }
      gridEl.appendChild(cell);
    }
  }

  prevEl.onclick = () => {
    viewMonth -= 1;
    if (viewMonth < 1) { viewMonth = 12; viewYear -= 1; }
    renderGrid();
  };
  nextEl.onclick = () => {
    viewMonth += 1;
    if (viewMonth > 12) { viewMonth = 1; viewYear += 1; }
    renderGrid();
  };

  summaryEl.textContent = selectedDate;
  renderGrid();
  renderTrackDateDetail(recordByDate[selectedDate], resultEl);
}

function renderTrackRecordGeneric(trackRecord, summaryEls, calEls, resultEl, errorAnalysisEls) {
  const { totalEl, correctEl, rateEl } = summaryEls;
  const resolvedCount = trackRecord?.resolved_count || 0;
  const correctCount = trackRecord?.correct_count || 0;
  const accuracyPct = trackRecord?.accuracy_pct;

  totalEl.textContent = resolvedCount;
  correctEl.textContent = correctCount;
  rateEl.textContent = accuracyPct != null ? `${accuracyPct}%` : "-";

  const recent = trackRecord?.recent || [];
  setupCalendarLookup(recent, calEls, resultEl);

  if (errorAnalysisEls) {
    renderErrorAnalysis(trackRecord?.error_analysis, errorAnalysisEls);
  }
}

function renderTrackRecord(trackRecord) {
  renderTrackRecordGeneric(
    trackRecord,
    { totalEl: trackSummaryTotalEl, correctEl: trackSummaryCorrectEl, rateEl: trackSummaryRateEl },
    {
      detailsEl: trackCalDetailsEl, summaryEl: trackCalSummaryEl,
      prevEl: trackCalPrevEl, nextEl: trackCalNextEl,
      monthLabelEl: trackCalMonthLabelEl, gridEl: trackCalGridEl,
    },
    trackDateResultEl,
    {
      confidenceEl: document.getElementById("track-confidence-breakdown"),
      matchEl: document.getElementById("track-match-breakdown"),
      newsEl: document.getElementById("track-news-breakdown"),
    },
  );
}

const ANOMALY_LABEL_MAP = { foreign: "外資", trust: "投信", dealer: "自營商" };

function renderInstAnomalyBadges(anomalies) {
  instAnomalyBadgesEl.innerHTML = "";
  if (!anomalies) return;

  Object.entries(anomalies).forEach(([key, info]) => {
    const badge = document.createElement("span");
    const dirClass = info.direction === "buy" ? "buy" : "sell";
    const dirText = info.direction === "buy" ? "買超" : "賣超";
    badge.className = `anomaly-badge ${dirClass}`;
    badge.textContent = `⚠ ${ANOMALY_LABEL_MAP[key] || key}連續${info.streak}天${dirText}`;
    instAnomalyBadgesEl.appendChild(badge);
  });
}

function renderOverview(data) {
  const overview = data.overview || {};
  const stockName = data.stock_name || manifestStockNames[data.stock_id] || "";
  overviewStockTitleEl.textContent = stockName ? `${stockName} ${data.stock_id} 總覽` : `${data.stock_id} 總覽`;
  overviewUpdatedEl.textContent = data.updated_at
    ? `資料更新: ${formatTaiwanTime(data.updated_at)}`
    : "";

  overviewCloseEl.textContent = overview.close != null ? overview.close.toFixed(2) : "-";

  if (overview.change != null) {
    const sign = overview.change > 0 ? "+" : "";
    const cls = overview.change > 0 ? "up" : overview.change < 0 ? "down" : "flat";
    overviewChangeEl.className = `overview-change ${cls}`;
    overviewChangeEl.textContent = `${sign}${overview.change.toFixed(2)} (${sign}${overview.change_pct}%)`;
  } else {
    overviewChangeEl.textContent = "";
  }

  overviewPerEl.textContent = overview.per != null ? overview.per.toFixed(2) : "-";
  overviewPbrEl.textContent = overview.pbr != null ? overview.pbr.toFixed(2) : "-";
  overviewRsiEl.textContent = overview.rsi14 != null ? overview.rsi14 : "-";
  overviewRsiStateEl.textContent = overview.rsi_state || "";
  overviewMaStateEl.textContent = overview.ma_state || "-";

  overviewInstitutionalEl.innerHTML = "";
  [
    { label: "外資", value: overview.foreign_net_today },
    { label: "投信", value: overview.trust_net_today },
    { label: "自營商", value: overview.dealer_net_today },
  ].forEach((item) => {
    const div = document.createElement("div");
    if (item.value == null) {
      div.textContent = `${item.label}: -`;
    } else {
      const cls = item.value > 0 ? "up" : item.value < 0 ? "down" : "";
      const sign = item.value > 0 ? "+" : "";
      div.innerHTML = `${item.label}: <span class="${cls}">${sign}${item.value}</span>`;
    }
    overviewInstitutionalEl.appendChild(div);
  });

  overviewNextDayEl.innerHTML =
    overview.next_day_up_pct != null
      ? `<span class="txt-up">上漲${overview.next_day_up_pct}%</span> / ` +
        `<span class="txt-down">下跌${overview.next_day_down_pct}%</span>`
      : "資料不足";

  const newsTotal = (overview.news_positive || 0) + (overview.news_negative || 0) + (overview.news_neutral || 0);
  overviewNewsEl.innerHTML =
    newsTotal > 0
      ? `<span class="txt-up">利多${overview.news_positive}</span> / ` +
        `<span class="txt-neutral">中性${overview.news_neutral}</span> / ` +
        `<span class="txt-down">利空${overview.news_negative}</span>`
      : "無相關新聞";

  overviewAnomalyBannerEl.innerHTML = "";
  const anomalies = data.institutional?.anomalies || {};
  Object.entries(anomalies).forEach(([key, info]) => {
    const dirText = info.direction === "buy" ? "買超" : "賣超";
    const line = document.createElement("div");
    line.className = "anomaly-line";
    line.textContent = `⚠ ${ANOMALY_LABEL_MAP[key] || key} 連續 ${info.streak} 天${dirText}`;
    overviewAnomalyBannerEl.appendChild(line);
  });
}

function renderStaleWarning(updatedAtStr) {
  if (!updatedAtStr) {
    staleWarningEl.style.display = "none";
    return;
  }
  const updated = new Date(updatedAtStr);
  const daysSince = (Date.now() - updated.getTime()) / (1000 * 60 * 60 * 24);

  if (daysSince > STALE_WARNING_DAYS) {
    staleWarningEl.style.display = "";
    staleWarningEl.textContent =
      `⚠ 資料已經 ${Math.floor(daysSince)} 天沒有更新了(最後更新: ${formatTaiwanTime(updatedAtStr)}),` +
      `可能是排程沒有正常執行,建議去 GitHub Actions 檢查一下。`;
  } else {
    staleWarningEl.style.display = "none";
  }
}

function formatCompareValue(value, digits, suffix = "") {
  return value != null ? `${value.toFixed(digits)}${suffix}` : "-";
}

function renderCompareTable(rows) {
  compareTableBodyEl.innerHTML = "";
  compareCountEl.textContent = `共 ${rows.length} 檔`;

  if (rows.length === 0) {
    compareTableBodyEl.innerHTML = `<tr><td colspan="11">目前沒有可比較的股票資料</td></tr>`;
    return;
  }

  rows.forEach((data) => {
    const overview = data.overview || {};
    const anomalies = data.institutional?.anomalies || {};
    const hasAnomaly = Object.keys(anomalies).length > 0;

    const changeCls = overview.change > 0 ? "txt-up" : overview.change < 0 ? "txt-down" : "";
    const changeSign = overview.change > 0 ? "+" : "";
    const changeText =
      overview.change_pct != null ? `<span class="${changeCls}">${changeSign}${overview.change_pct}%</span>` : "-";

    const nextDayText =
      overview.next_day_up_pct != null
        ? `<span class="txt-up">${overview.next_day_up_pct}%</span> / <span class="txt-down">${overview.next_day_down_pct}%</span>`
        : "-";

    const newsTotal = (overview.news_positive || 0) + (overview.news_negative || 0) + (overview.news_neutral || 0);
    const newsText =
      newsTotal > 0
        ? `<span class="txt-up">${overview.news_positive}</span>/<span class="txt-neutral">${overview.news_neutral}</span>/<span class="txt-down">${overview.news_negative}</span>`
        : "-";

    const anomalyText = hasAnomaly
      ? Object.entries(anomalies)
          .map(([key, info]) => {
            const cls = info.direction === "buy" ? "txt-up" : "txt-down";
            const dirText = info.direction === "buy" ? "買超" : "賣超";
            return `<span class="${cls}">⚠${ANOMALY_LABEL_MAP[key] || key}${info.streak}天${dirText}</span>`;
          })
          .join(" ")
      : "-";

    const tr = document.createElement("tr");
    if (hasAnomaly) tr.classList.add("has-anomaly");
    tr.innerHTML = `
      <td>${escapeHtml(data.stock_id)}${data.stock_name ? " " + escapeHtml(data.stock_name) : ""}</td>
      <td>${formatCompareValue(overview.close, 2)}</td>
      <td>${changeText}</td>
      <td>${formatCompareValue(overview.per, 1)}</td>
      <td>${formatCompareValue(overview.pbr, 1)}</td>
      <td>${overview.rsi14 != null ? overview.rsi14 : "-"}</td>
      <td>${escapeHtml(overview.ma_state || "-")}</td>
      <td>${nextDayText}</td>
      <td>${newsText}</td>
      <td>${anomalyText}</td>
    `;
    tr.addEventListener("click", () => {
      selectEl.value = data.stock_id;
      loadStock(data.stock_id);
      pageSelectEl.value = "overview";
      setActivePage("overview");
    });
    compareTableBodyEl.appendChild(tr);
  });
}

const COMPARE_SORT_GETTERS = {
  stock_id: (data) => data.stock_id || "",
  price: (data) => data.overview?.close,
  change: (data) => data.overview?.change_pct,
  per: (data) => data.overview?.per,
  pbr: (data) => data.overview?.pbr,
  rsi: (data) => data.overview?.rsi14,
};

function renderSortedCompareTable() {
  // 先定義表頭 (依照市場切換)
  const isGlobal = currentMarket === "GLOBAL";
  
  const theadHTML = isGlobal 
    ? `<tr>
        <th>股票</th><th>現價</th><th>漲跌%</th><th>RSI14</th><th>均線排列</th>
       </tr>`
    : `<tr>
        <th>股票</th><th>現價</th><th>漲跌%</th><th>外資買賣</th><th>PER</th><th>PBR</th><th>RSI14</th><th>均線</th><th>隔日漲跌機率</th>
       </tr>`;
       
  // 建立表格內容
  let tbodyHTML = "";
  compareRows.forEach(data => {
    const ov = data.overview || {};
    const priceStr = ov.close !== undefined ? ov.close : "-";
    const changePctStr = ov.change_pct !== undefined ? `${ov.change_pct}%` : "-";
    const rsiStr = ov.rsi14 !== undefined ? ov.rsi14 : "-";
    const maStateStr = ov.ma_state || "盤整";
    
    // 判斷漲跌顏色
    const changeClass = ov.change_pct > 0 ? 'up' : (ov.change_pct < 0 ? 'down' : '');
    
    if (isGlobal) {
      // 全球股專用的表格列
      tbodyHTML += `<tr>
        <td>${data.stock_id} ${data.stock_name}</td>
        <td>${priceStr}</td>
        <td class="${changeClass}">${changePctStr}</td>
        <td>${rsiStr}</td>
        <td>${maStateStr}</td>
      </tr>`;
    } else {
      // 台股專用的表格列
      const perStr = ov.per || "-";
      const pbrStr = ov.pbr || "-";
      const probStr = ov.next_day_up_pct ? `${ov.next_day_up_pct}%` : "資料不足";
      const foreignStr = ov.foreign_net_today || "-";
      
      tbodyHTML += `<tr>
        <td>${data.stock_id} ${data.stock_name}</td>
        <td>${priceStr}</td>
        <td class="${changeClass}">${changePctStr}</td>
        <td>${foreignStr}</td>
        <td>${perStr}</td>
        <td>${pbrStr}</td>
        <td>${rsiStr}</td>
        <td>${maStateStr}</td>
        <td>${probStr}</td>
      </tr>`;
    }
  });

  // 安全寫入：直接對現有的 tbody 的「父元素 (也就是 table)」進行整併覆蓋
  if (compareTableBodyEl && compareTableBodyEl.parentElement) {
      compareTableBodyEl.parentElement.innerHTML = `<thead>${theadHTML}</thead><tbody id="compare-table-body">${tbodyHTML}</tbody>`;
  }
}

let compareSortCol = "stock_id";
let compareSortAsc = true;

function setupCompareSorting() {
  const ths = document.querySelectorAll(".compare-table th");
  ths.forEach((th) => {
    th.addEventListener("click", () => {
      // 取得點擊的欄位名稱
      const colText = th.textContent.replace("↕", "").trim();
      let colKey = "stock_id";
      
      if (colText.includes("現價")) colKey = "close";
      else if (colText.includes("漲跌%")) colKey = "change_pct";
      else if (colText.includes("RSI")) colKey = "rsi14";
      else if (colText.includes("PER")) colKey = "per";
      else if (colText.includes("PBR")) colKey = "pbr";
      else if (colText.includes("外資")) colKey = "foreign_net_today";
      
      // 切換排序方向
      if (compareSortCol === colKey) {
        compareSortAsc = !compareSortAsc;
      } else {
        compareSortCol = colKey;
        compareSortAsc = true; // 預設新欄位為升冪
      }
      
      // 執行排序
      compareRows.sort((a, b) => {
        const valA = a.overview[colKey] || 0;
        const valB = b.overview[colKey] || 0;
        return compareSortAsc ? (valA > valB ? 1 : -1) : (valA < valB ? 1 : -1);
      });
      
      // 重新渲染表格
      renderSortedCompareTable();
    });
  });
}

async function loadCompareTable(force = false) {
  if (compareDataLoaded && !force) return;

  compareTableBodyEl.innerHTML = `<tr><td colspan="11">載入中...</td></tr>`;
  const rows = [];

  // 👇 1. 新增這行：動態判斷要跑台股還是全球股清單
  const compareList = currentMarket === "TW" ? manifestStockIds : globalStockIds;

  // 👇 2. 把原本的 manifestStockIds 換成 compareList
  for (const id of compareList) {
    try {
      const res = await fetch(`${DATA_BASE_URL}/${id}.json?t=${Date.now()}`);
      if (!res.ok) continue;
      const data = await res.json();
      rows.push(data);
    } catch (e) {}
  }

  compareRows = rows;
  renderSortedCompareTable();
  compareDataLoaded = true;
}

function renderMlPrediction(mlNextDay) {
  const mlSummaryEls = { totalEl: mlTrackSummaryTotalEl, correctEl: mlTrackSummaryCorrectEl, rateEl: mlTrackSummaryRateEl };
  const mlDateEls = {
    detailsEl: mlTrackCalDetailsEl, summaryEl: mlTrackCalSummaryEl,
    prevEl: mlTrackCalPrevEl, nextEl: mlTrackCalNextEl,
    monthLabelEl: mlTrackCalMonthLabelEl, gridEl: mlTrackCalGridEl,
  };
  const mlErrorAnalysisEls = {
    confidenceEl: document.getElementById("ml-confidence-breakdown"),
    matchEl: document.getElementById("ml-match-breakdown"),
    matchGroupEl: document.getElementById("ml-match-group"),
    newsEl: document.getElementById("ml-news-breakdown"),
  };

  if (!mlNextDay || mlNextDay.up_pct === null || mlNextDay.up_pct === undefined) {
    mlStateLabelEl.textContent = mlNextDay?.state_label || "資料不足";
    mlBarUpEl.style.width = "50%";
    mlBarDownEl.style.width = "50%";
    mlUpPctEl.textContent = "-";
    mlDownPctEl.textContent = "-";
    renderTrackRecordGeneric(mlNextDay?.track_record, mlSummaryEls, mlDateEls, mlTrackDateResultEl, mlErrorAnalysisEls);
    return;
  }

  mlStateLabelEl.textContent = mlNextDay.state_label || "";
  mlBarUpEl.style.width = `${mlNextDay.up_pct}%`;
  mlBarDownEl.style.width = `${mlNextDay.down_pct}%`;
  mlUpPctEl.textContent = mlNextDay.up_pct;
  mlDownPctEl.textContent = mlNextDay.down_pct;

  renderTrackRecordGeneric(mlNextDay.track_record, mlSummaryEls, mlDateEls, mlTrackDateResultEl, mlErrorAnalysisEls);
}

async function loadStock(stockId) {
  const res = await fetch(`${DATA_BASE_URL}/${stockId}.json?t=${Date.now()}`);
  if (!res.ok) {
    alert(`找不到 ${stockId} 的資料`);
    return;
  }
  const data = await res.json();

  const stockName = data.stock_name || manifestStockNames[stockId] || "";
  stockLabelEl.replaceChildren();
  if (stockName) {
    stockLabelEl.appendChild(document.createTextNode(stockName));
  }
  const stockIdSpan = document.createElement("span");
  stockIdSpan.className = "stock-id";
  stockIdSpan.textContent = stockId;
  stockLabelEl.appendChild(stockIdSpan);

  // 新增: 更新下載CSV連結
  downloadCsvBtn.href = `${DATA_BASE_URL}/${stockId}_unified.csv`;
  downloadCsvBtn.style.display = "inline-flex";

  candleSeries.setData(data.price);
  renderMaSeries(data.ma || {});
  
  // 新增: KD圖表資料渲染
  const kdData = data.kd || {};
  kSeries.setData(kdData.K || []);
  dSeries.setData(kdData.D || []);
  
  rsiSeries14.setData(data.rsi?.RSI14 || []);
  rsiSeries6.setData(data.rsi?.RSI6 || []);

  const inst = data.institutional || {};
  foreignSeries.setData(inst.foreign_net || []);
  trustSeries.setData(inst.trust_net || []);
  dealerSeries.setData(inst.dealer_net || []);
  renderInstAnomalyBadges(inst.anomalies);

  const margin = data.margin || {};
  marginBalanceSeries.setData(margin.margin_balance || []);
  shortBalanceSeries.setData(margin.short_balance || []);

  const valuation = data.valuation || {};
  perSeries.setData(valuation.PER || []);
  pbrSeries.setData(valuation.PBR || []);

  renderFundamentalsTable(data.fundamentals);
  renderAnalysis(data.analysis);
  renderTrackRecord(data.analysis?.next_day?.track_record);
  renderMlPrediction(data.analysis?.next_day_ml);
  renderNews(data.news);
  renderSentimentHistory(data.news);
  renderOverview(data);
  renderChecklist(data);
  renderV3Features(data);
  renderUltimateJudge(data);


  priceChart.timeScale().fitContent();
  kdChart.timeScale().fitContent(); // 新增: KD圖表自適應
  rsiChart.timeScale().fitContent();
  instChart.timeScale().fitContent();
  marginChart.timeScale().fitContent();
  valuationChart.timeScale().fitContent();

  updatedAtEl.textContent = `資料更新: ${formatTaiwanTime(data.updated_at)}`;
  renderStaleWarning(data.updated_at);
}

// --- 初始化與讀取 manifest 檔案的函式 (完全替換原本的) ---
async function loadManifestAndInit() {
  const res = await fetch(`${DATA_BASE_URL}/manifest.json?t=${Date.now()}`);
  const manifest = await res.json();
  
  // 讀取台股清單
  manifestStockNames = manifest.stock_names || {};
  manifestStockIds = manifest.stocks || [];
  
  // 讀取全球股清單
  globalStockIds = manifest.global_stocks || [];
  globalStockNames = manifest.global_stock_names || {};

  // 綁定「市場切換」下拉選單的事件
  marketSelectEl.addEventListener("change", (e) => {
    currentMarket = e.target.value;
    
    // 👇 補上這行：讓系統知道切換市場後，多股比較表需要重新抓資料
    compareDataLoaded = false; 
    
    updateDropdownsByMarket();
  });

  // 綁定「股票切換」下拉選單的事件
  selectEl.addEventListener("change", () => loadStock(selectEl.value));
  
  // 網頁剛開起來時，執行第一次的選單生成與載入
  updateDropdownsByMarket();
}

pageSelectEl.addEventListener("change", () => setActivePage(pageSelectEl.value));

// 新增：主題切換互動邏輯
themeToggleBtn.textContent = isDarkMode ? "☀️ 淺色模式" : "🌙 深色模式";

themeToggleBtn.addEventListener("click", () => {
  isDarkMode = !isDarkMode;
  document.documentElement.setAttribute("data-theme", isDarkMode ? "dark" : "light");
  localStorage.setItem("ai-stock-theme", isDarkMode ? "dark" : "light");
  themeToggleBtn.textContent = isDarkMode ? "☀️ 淺色模式" : "🌙 深色模式";

  // 即時更新圖表的格線與文字顏色
  const chartOptions = {
    layout: { textColor: isDarkMode ? "#c7cad1" : "#64748b" },
    grid: {
      vertLines: { color: isDarkMode ? "#22252f" : "#f1f5f9" },
      horzLines: { color: isDarkMode ? "#22252f" : "#f1f5f9" },
    },
    rightPriceScale: { borderColor: isDarkMode ? "#262a36" : "#e2e8f0" },
    leftPriceScale: { borderColor: isDarkMode ? "#262a36" : "#e2e8f0" },
    timeScale: { borderColor: isDarkMode ? "#262a36" : "#e2e8f0" },
  };

  [priceChart, kdChart, rsiChart, instChart, marginChart, valuationChart, sentimentChart].forEach(chart => {
    if (chart) chart.applyOptions(chartOptions);
  });
});

initCharts();
setActivePage("overview");
// 👇 V3 新增：渲染 AI 早報與網格策略
function appendInfoRow(container, label, value, highlight = false) {
  const row = document.createElement("div");
  row.className = "v3-ai-text";
  const strong = document.createElement("strong");
  strong.textContent = `${label}：`;
  const span = document.createElement("span");
  span.textContent = value ?? "-";
  if (highlight) span.className = "v3-ai-highlight";
  row.append(strong, span);
  container.appendChild(row);
}

function setCardTitle(card, title) {
  const heading = document.createElement("div");
  heading.className = "v3-ai-title";
  heading.textContent = title;
  card.appendChild(heading);
}

function renderV3Features(data) {
  const v3 = data.v3_features || {};
  const alertBanner = document.getElementById("v3-alert-banner");
  const aiReportCard = document.getElementById("v3-ai-report-card");
  const gridCard = document.getElementById("v3-grid-strategy-card");
  const xgbCard = document.getElementById("v3-xgb-prediction-card");

  const risk = v3.risk_alert;
  if (risk?.triggered) {
    alertBanner.style.display = "flex";
    alertBanner.className = "v3-alert-banner";
    alertBanner.textContent = `🚨 風險警報：${(risk.alerts || []).join("；")}`;
  } else {
    alertBanner.style.display = "none";
    alertBanner.textContent = "";
  }

  aiReportCard.replaceChildren();
  if (v3.ai_report) {
    aiReportCard.style.display = "block";
    setCardTitle(aiReportCard, "🤖 結構化量化早報");
    appendInfoRow(aiReportCard, "評級", v3.ai_report.trend_rating, true);
    appendInfoRow(aiReportCard, "量化摘要", v3.ai_report.quant_summary);
    appendInfoRow(aiReportCard, "操作觀察", v3.ai_report.action_advice);
    appendInfoRow(aiReportCard, "風險提示", v3.ai_report.risk_warning);
    appendInfoRow(aiReportCard, "產生方式", v3.ai_report.analysis_method || "-");
  } else {
    aiReportCard.style.display = "none";
  }

  gridCard.replaceChildren();
  if (v3.grid_strategy) {
    const grid = v3.grid_strategy;
    const lines = grid.grid_defense_lines || {};
    gridCard.style.display = "block";
    setCardTitle(gridCard, "📐 波段回吐網格策略");
    appendInfoRow(gridCard, "波段結構", grid.wave_summary);
    appendInfoRow(gridCard, "目前狀態", grid.strike_status, true);

    const table = document.createElement("table");
    table.className = "v3-grid-table";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["防線等級", "價位"].forEach((text) => {
      const th = document.createElement("th");
      th.textContent = text;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    const tbody = document.createElement("tbody");
    [
      ["強勢防線 (38.2%)", lines.level_382],
      ["中期防線 (50.0%)", lines.level_500],
      ["最後防線 (61.8%)", lines.level_618],
    ].forEach(([label, value]) => {
      const tr = document.createElement("tr");
      [label, value || "-"].forEach((text) => {
        const td = document.createElement("td");
        td.textContent = text;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.append(thead, tbody);
    gridCard.appendChild(table);
    appendInfoRow(gridCard, "紀律提示", grid.ai_execution_order);
  } else {
    gridCard.style.display = "none";
  }

  xgbCard.replaceChildren();
  if (v3.xgb_prediction) {
    const prediction = v3.xgb_prediction;
    const metrics = prediction.model_validation || {};
    xgbCard.style.display = "block";
    setCardTitle(xgbCard, "🌲 XGBoost 盤後原始模型");
    appendInfoRow(xgbCard, "觀測日", prediction.observation_date);
    appendInfoRow(xgbCard, "上漲 / 下跌", `${prediction.up_probability}% / ${prediction.down_probability}%`, true);
    appendInfoRow(xgbCard, "時間序列驗證準確率", metrics.accuracy_pct != null ? `${metrics.accuracy_pct}%` : "-");
    appendInfoRow(xgbCard, "驗證區間", metrics.holdout_start && metrics.holdout_end ? `${metrics.holdout_start} ～ ${metrics.holdout_end}` : "-");
  } else {
    xgbCard.style.display = "none";
  }
}

// V4：只渲染獨立綜合機率卡片，不覆寫其他模型 UI
function renderUltimateJudge(data) {
  const judgeData = data.v3_features?.ultimate_judge;
  const judgeCard = document.getElementById("v4-ultimate-judge-card");
  if (!judgeData) {
    if (judgeCard) judgeCard.style.display = "none";
    return;
  }

  judgeCard.style.display = "block";
  const upProb = Number(judgeData.ultimate_up_probability);
  const downProb = Number(judgeData.ultimate_down_probability);
  const valid = Number.isFinite(upProb) && Number.isFinite(downProb) &&
    upProb >= 0 && downProb >= 0 && Math.abs(upProb + downProb - 100) < 0.11;
  if (!valid) {
    judgeCard.style.display = "none";
    console.error("Invalid ultimate probability payload", judgeData);
    return;
  }

  document.getElementById("v4-ultimate-up-text").textContent = `上漲 ${upProb.toFixed(1)}%`;
  document.getElementById("v4-ultimate-down-text").textContent = `下跌 ${downProb.toFixed(1)}%`;
  document.getElementById("v4-ultimate-bar-up").style.width = `${upProb}%`;
  document.getElementById("v4-ultimate-logic").textContent = judgeData.adjustment_logic || "-";
}

function renderChecklist(data) {
  const conditions = data.overview?.conditions || {};
  const details = conditions.details || {};
  checklistContainerEl.innerHTML = "";

  // 格式化數字的安全小工具
  const safeNum = (val, digits = 2) => val != null ? Number(val).toFixed(digits) : "無資料";

  // 計算季線乖離率 (判斷短線是否過熱或跌深)
  let ma60BiasText = "";
  if (details.close && details.ma60_today) {
    const bias = ((details.close - details.ma60_today) / details.ma60_today) * 100;
    ma60BiasText = `目前與季線乖離率為 <b>${bias > 0 ? '+' : ''}${bias.toFixed(2)}%</b>`;
    if (bias > 15) ma60BiasText += " (乖離偏高，短線有拉回修正風險)";
    else if (bias < -15) ma60BiasText += " (乖離偏低，可能有跌深反彈契機)";
  }

  // 定義條件清單與豐富的說明
  const items = [
    {
      label: "1. KD 落入 20 以下 (尋找超賣區)",
      passed: conditions.kd_under_20,
      desc: `
        <div class="chk-logic"><b>判斷邏輯：</b>昨日 K 值 ≤ 20。</div>
        <div class="chk-data"><b>當前數據：</b>昨日 K=${safeNum(details.k_yest)}。今日 K=${safeNum(details.k_today)}、D=${safeNum(details.d_today)}。</div>
        <div class="chk-warning">💡 <b>實戰補充：</b>若 K 值連續多日在 20 以下徘徊稱為「低檔鈍化」，代表空頭極強，此時不宜盲目接刀，需等待明確止跌訊號出現。</div>
      `
    },
    {
      label: "2. KD 出現黃金交叉 (短線轉強訊號)",
      passed: conditions.kd_golden_cross,
      desc: `
        <div class="chk-logic"><b>判斷邏輯：</b>昨日 K < D 且 今日 K > D。</div>
        <div class="chk-data"><b>當前數據：</b>昨日 K(${safeNum(details.k_yest)}) ${details.k_yest < details.d_yest ? '<' : '≮'} D(${safeNum(details.d_yest)}) ➡️ 今日 K(${safeNum(details.k_today)}) ${details.k_today > details.d_today ? '>' : '≯'} D(${safeNum(details.d_today)})。</div>
        <div class="chk-warning">💡 <b>實戰補充：</b>黃金交叉若發生在 20 以下（低檔）的勝率較高；反之，若在 80 以上發生「死亡交叉」則為獲利了結的警戒訊號。</div>
      `
    },
    {
      label: "3. 股價在季線之上且季線上揚 (中期多頭)",
      passed: conditions.ma60_uptrend,
      desc: `
        <div class="chk-logic"><b>判斷邏輯：</b>今日收盤價 > 今日季線(MA60)，且今日季線數值大於昨日。</div>
        <div class="chk-data"><b>當前數據：</b>收盤價=${safeNum(details.close)}。今日季線=${safeNum(details.ma60_today)}，較昨日(${safeNum(details.ma60_yest)}) <span class="${details.ma60_today > details.ma60_yest ? 'txt-up' : 'txt-down'}">${details.ma60_today > details.ma60_yest ? '上升 📈' : '下降 📉'}</span>。</div>
        <div class="chk-warning">💡 <b>實戰補充：</b>季線(60日均線)是判斷中期多空的分水嶺。${ma60BiasText}。</div>
      `
    },
    {
      label: "4. 區間抄底：跌破布林通道下軌",
      passed: conditions.bb_lower_breakout,
      desc: `
        <div class="chk-logic"><b>進場條件：</b>今日收盤價 &lt; 布林通道下軌。</div>
        <div class="chk-data"><b>當前數據：</b>收盤價=${safeNum(details.close)}。布林下軌=${safeNum(details.bb_lower)}、上軌=${safeNum(details.bb_upper)}。</div>
        <div class="chk-warning">💡 <b>實戰補充：</b>在統計學上，股價有 95% 的時間會在布林通道內。跌破下線代表市場出現恐慌超跌，進場「搶反彈」。此策略在盤整或區間震盪時交易次數多且勝率亮眼。（獲利出場可設定為突破上軌）</div>
      `
    },
    {
      label: "5. 同邏輯對稱組：RSI 落入超賣區",
      passed: conditions.rsi_oversold,
      desc: `
        <div class="chk-logic"><b>進場條件：</b>今日 RSI14 &lt; 30 (超賣區)。</div>
        <div class="chk-data"><b>當前數據：</b>今日 RSI14 = ${safeNum(details.rsi14_today)}。</div>
        <div class="chk-warning">💡 <b>實戰補充：</b>當指標落入超賣買進，等它一路漲到超買 (例如 RSI > 70) 賣出，這樣就是一個完整的交易週期。使用相同指標進出場，能避免時間週期不對稱的問題，出手機會也會有效提升。</div>
      `
    }
  ];

  items.forEach(item => {
    const row = document.createElement("div");
    row.className = `checklist-row ${item.passed ? 'pass' : 'fail'}`;

    const icon = item.passed ? "✅" : "❌";
    // 這裡我們不再用單純的 textContent，而是用 innerHTML 放入有結構的文字
    row.innerHTML = `
      <div class="checklist-icon">${icon}</div>
      <div class="checklist-content">
        <div class="checklist-label">${item.label}</div>
        <div class="checklist-desc">${item.desc}</div>
      </div>
    `;
    checklistContainerEl.appendChild(row);
  });
}

// --- 處理市場切換與選單連動的函式 ---
function updateDropdownsByMarket() {
  // 1. 更新股票下拉選單
  selectEl.innerHTML = "";
  const stocks = currentMarket === "TW" ? manifestStockIds : globalStockIds;
  const names = currentMarket === "TW" ? manifestStockNames : globalStockNames;
  
  stocks.forEach((id) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = names[id] ? `${id} ${names[id]}` : id;
    selectEl.appendChild(opt);
  });

  // 2. 更新頁面分頁選單 (這裡修正了之前的語法錯誤)
  pageSelectEl.innerHTML = `
    <option value="overview">總覽</option>
    <option value="compare">多股比較</option>
    <option value="checklist">多空條件檢核表</option>
    <option value="price">K線</option>
    ${currentMarket === "TW" ? '<option value="trend">走向分析</option>' : ''}
    ${currentMarket === "TW" 
      ? '<option value="indicators">技術籌碼指標</option><option value="fundamentals">基本面統計</option><option value="news">財經新聞</option>' 
      : '<option value="indicators">技術指標(全球)</option><option value="news">國際要聞</option>'} <!-- 👇 全球股補上這項 -->
  `;

  // 3. 隱藏/顯示台股專屬的 UI 卡片 (有加上 tw-only 的區塊)
  document.querySelectorAll(".tw-only").forEach(el => {
    el.style.display = currentMarket === "TW" ? "" : "none";
  });

  // 4. 自動載入該市場的第一檔股票，並切換回總覽頁面
  if (stocks.length > 0) {
    loadStock(stocks[0]);
    pageSelectEl.value = "overview";
    setActivePage("overview");
  }
}

setupCompareSorting();
loadManifestAndInit();
