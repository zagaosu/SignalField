(() => {
  "use strict";

  const PRESET_ORDER = [
    "Agent",
    "推理部署",
    "模型工具",
    "多模态",
    "RAG 与数据",
    "评测与安全",
    "开源模型",
    "AI 编程",
    "生活",
    "运动",
    "新闻",
    "财经",
    "娱乐",
    "科学",
    "健康",
    "汽车",
    "旅行",
    "教育",
    "游戏",
    "时尚",
  ];
  const INTEREST_KEY = "signalfield:interests:v5";
  const DEMO_GROUPS = new Set(["Agent", "推理部署", "模型工具"]);
  const INTEREST_BATCH_SIZE = 8;
  const INITIAL_BROAD_BATCH = [
    "Agent",
    "生活",
    "运动",
    "新闻",
    "推理部署",
    "娱乐",
    "模型工具",
    "财经",
  ];
  const BROAD_INTERESTS = [
    { group: "Agent", label: "Agent", hint: "编排 · 工具 · 记忆" },
    { group: "推理部署", label: "推理部署", hint: "引擎 · 量化 · 端侧" },
    { group: "模型工具", label: "模型工具", hint: "服务 · 开发 · SDK" },
    { group: "多模态", label: "多模态", hint: "视觉 · 语音 · 视频" },
    { group: "RAG 与数据", label: "RAG 与数据", hint: "检索 · 知识库" },
    { group: "评测与安全", label: "评测与安全", hint: "基准 · 对齐 · 护栏" },
    { group: "开源模型", label: "开源模型", hint: "权重 · 微调 · 训练" },
    { group: "AI 编程", label: "AI 编程", hint: "编码 Agent · IDE" },
    { group: "生活", label: "生活", hint: "家居 · 美食 · 日常" },
    { group: "运动", label: "运动", hint: "赛事 · 健身 · 户外" },
    { group: "新闻", label: "新闻", hint: "国际 · 社会 · 深度" },
    { group: "财经", label: "财经", hint: "市场 · 公司 · 政策" },
    { group: "娱乐", label: "娱乐", hint: "影视 · 音乐 · 综艺" },
    { group: "科学", label: "科学", hint: "太空 · 生命 · 环境" },
    { group: "健康", label: "健康", hint: "营养 · 康复 · 心理" },
    { group: "汽车", label: "汽车", hint: "新能源 · 智驾 · 新车" },
    { group: "旅行", label: "旅行", hint: "目的地 · 户外 · 城市" },
    { group: "教育", label: "教育", hint: "学习 · 升学 · 职业" },
    { group: "游戏", label: "游戏", hint: "新游 · 电竞 · 独立" },
    { group: "时尚", label: "时尚", hint: "穿搭 · 美妆 · 设计" },
  ];
  const INTEREST_KEYWORDS = [
    { group: "Agent", label: "Agent 编排", hint: "工作流 / 多智能体" },
    { group: "Agent", label: "工具调用", hint: "权限 / 工具网关" },
    { group: "Agent", label: "记忆与评测", hint: "长期记忆 / 基准" },
    { group: "推理部署", label: "推理引擎", hint: "吞吐 / 延迟" },
    { group: "推理部署", label: "量化", hint: "INT4 / KV Cache" },
    { group: "推理部署", label: "端侧部署", hint: "Jetson / 边缘" },
    { group: "模型工具", label: "模型服务", hint: "API / Serving" },
    { group: "模型工具", label: "开发工具", hint: "调试 / 可观测" },
    { group: "模型工具", label: "SDK", hint: "接口 / 版本" },
    { group: "多模态", label: "视觉理解", hint: "VLM / 图像推理" },
    { group: "多模态", label: "语音交互", hint: "ASR / 实时语音" },
    { group: "多模态", label: "视频生成", hint: "生成 / 编辑" },
    { group: "RAG 与数据", label: "向量检索", hint: "Embedding / 索引" },
    { group: "RAG 与数据", label: "知识库", hint: "文档 / 图谱" },
    { group: "RAG 与数据", label: "数据管线", hint: "清洗 / 标注" },
    { group: "评测与安全", label: "Agent 评测", hint: "任务 / 轨迹" },
    { group: "评测与安全", label: "对齐", hint: "偏好 / 红队" },
    { group: "评测与安全", label: "安全护栏", hint: "注入 / 权限" },
    { group: "开源模型", label: "模型权重", hint: "开源发布 / 许可证" },
    { group: "开源模型", label: "微调", hint: "LoRA / 后训练" },
    { group: "开源模型", label: "训练工具", hint: "分布式 / 加速" },
    { group: "AI 编程", label: "编码 Agent", hint: "仓库 / 工具链" },
    { group: "AI 编程", label: "IDE 集成", hint: "补全 / 重构" },
    { group: "AI 编程", label: "代码评测", hint: "基准 / 安全" },
    { group: "生活", label: "家居改善", hint: "空间 / 收纳" },
    { group: "生活", label: "美食趋势", hint: "餐厅 / 食谱" },
    { group: "生活", label: "城市生活", hint: "社区 / 消费" },
    { group: "运动", label: "足球", hint: "联赛 / 转会" },
    { group: "运动", label: "篮球", hint: "赛事 / 球员" },
    { group: "运动", label: "跑步健身", hint: "训练 / 装备" },
    { group: "新闻", label: "国际时事", hint: "地缘 / 政策" },
    { group: "新闻", label: "国内社会", hint: "公共议题" },
    { group: "新闻", label: "深度报道", hint: "调查 / 解释" },
    { group: "财经", label: "市场行情", hint: "股票 / 大宗" },
    { group: "财经", label: "公司动态", hint: "财报 / 融资" },
    { group: "财经", label: "宏观政策", hint: "利率 / 监管" },
    { group: "娱乐", label: "影视", hint: "电影 / 剧集" },
    { group: "娱乐", label: "音乐", hint: "专辑 / 现场" },
    { group: "娱乐", label: "综艺", hint: "节目 / 行业" },
    { group: "科学", label: "太空探索", hint: "航天 / 天文" },
    { group: "科学", label: "生命科学", hint: "基因 / 医疗" },
    { group: "科学", label: "气候环境", hint: "气候 / 能源" },
    { group: "健康", label: "营养饮食", hint: "营养 / 膳食" },
    { group: "健康", label: "运动康复", hint: "损伤 / 恢复" },
    { group: "健康", label: "心理健康", hint: "压力 / 睡眠" },
    { group: "汽车", label: "新能源车", hint: "电池 / 补能" },
    { group: "汽车", label: "智能驾驶", hint: "辅助驾驶 / 法规" },
    { group: "汽车", label: "新车发布", hint: "车型 / 配置" },
    { group: "旅行", label: "目的地", hint: "攻略 / 签证" },
    { group: "旅行", label: "户外徒步", hint: "路线 / 装备" },
    { group: "旅行", label: "城市漫游", hint: "街区 / 文化" },
    { group: "教育", label: "学习方法", hint: "效率 / 工具" },
    { group: "教育", label: "考试升学", hint: "政策 / 备考" },
    { group: "教育", label: "职业成长", hint: "技能 / 转型" },
    { group: "游戏", label: "新游发布", hint: "主机 / 手游" },
    { group: "游戏", label: "电竞", hint: "赛事 / 战队" },
    { group: "游戏", label: "独立游戏", hint: "开发 / 发行" },
    { group: "时尚", label: "穿搭", hint: "趋势 / 品牌" },
    { group: "时尚", label: "美妆", hint: "产品 / 成分" },
    { group: "时尚", label: "设计", hint: "视觉 / 产品" },
  ];
  const ACTIVE_STATUSES = new Set(["queued", "running", "cancelling"]);
  const STATUS_LABELS = {
    queued: "排队中",
    running: "检索中",
    cancelling: "取消中",
    completed: "已完成",
    partial: "部分完成",
    failed: "失败",
    cancelled: "已取消",
  };
  const STAGE_LABELS = {
    created: "准备任务",
    planning: "规划检索策略",
    searching: "搜索候选资料",
    reading: "读取正文",
    extracting: "聚合事件与证据",
    checking_gaps: "检查证据缺口",
    gap_searching: "定向补搜",
    gap_reading: "读取补充资料",
    verifying: "核验引用",
    ranking: "排序与生成卡片",
    done: "完成",
  };
  const STOP_LABELS = {
    coverage_sufficient: "覆盖充分",
    low_value_gaps: "低价值缺口",
    no_results: "无结果",
    no_verifiable_events: "无可核验事件",
    read_failed: "正文读取失败",
    gap_rounds_exhausted: "补搜轮次用尽",
    evidence_gaps_remaining: "证据仍有缺口",
    topic_uncovered: "话题未覆盖",
    daily_budget_exhausted: "本地每日预算",
    run_budget_exhausted: "单任务额度耗尽",
    budget_exhausted: "额度耗尽",
    user_cancel: "用户取消",
    timeout: "时间上限",
    server_restart: "服务重启中断",
    service_unavailable: "服务不可用",
    internal_error: "内部异常",
    config_missing: "配置缺失",
  };
  const QUERY_STATUS = {
    planned: "待执行",
    running: "执行中",
    ok: "成功",
    error: "失败",
    skipped: "跳过",
  };
  const ACTION_OUTCOME = {
    running: "进行中",
    helpful: "有效补搜",
    no_new_value: "无新增价值",
    failed: "补搜失败",
    budget_stopped: "额度停止",
  };
  const STRATEGY_LABELS = { open: "开放发现", official: "官方来源", specific: "定向核验" };
  const DATE_CONFIDENCE = { confirmed: "日期明确", inferred: "日期推断", unknown: "日期待确认" };

  const app = {
    config: null,
    currentRun: null,
    runs: [],
    updates: [],
    selectedTopics: new Set(),
    customTopics: [],
    window: "week",
    mode: "demo",
    pollTimer: null,
    pollBusy: false,
    pollFailures: 0,
    isStarting: false,
    resultsSig: null,
    progressRunId: null,
    activeEventId: null,
    lastFocused: null,
    lastUpdateFetch: 0,
    interestBroad: new Set(),
    interestFine: new Set(),
    visibleBroad: [],
    interestRound: 1,
    focusKeywords: [],
    orbAnimation: null,
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function pad2(value) {
    return String(value).padStart(2, "0");
  }

  function topicSelected(topic) {
    return app.selectedTopics.has(topic);
  }

  function isActive(status) {
    return ACTIVE_STATUSES.has(status);
  }

  function isDemoRun(run = app.currentRun) {
    return run ? run.mode === "demo" : app.mode === "demo";
  }

  function hasUnread(events) {
    return (events || []).some(
      (event) => !event.read_at && ["new", "updated"].includes(event.change_type)
    );
  }

  function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body) headers["Content-Type"] = "application/json";
    return fetch(path, { ...options, headers }).then(async (response) => {
      let payload = null;
      try {
        payload = await response.json();
      } catch (_) {
        payload = null;
      }
      if (!response.ok) {
        const detail = payload && payload.detail;
        let message = "请求失败，请稍后重试。";
        if (typeof detail === "string") message = detail;
        else if (detail && typeof detail === "object") {
          message = detail.message || JSON.stringify(detail);
        }
        const error = new Error(message);
        error.status = response.status;
        error.detail = detail;
        throw error;
      }
      return payload;
    });
  }

  function formatDateOnly(value) {
    if (!value) return "待确认";
    const parts = String(value).slice(0, 10).split("-");
    if (parts.length !== 3) return value;
    return `${parts[0]}.${parts[1]}.${parts[2]}`;
  }

  function formatMonthDay(value) {
    if (!value) return "待确认";
    const parts = String(value).slice(0, 10).split("-");
    if (parts.length !== 3) return value;
    return `${parts[1]}.${parts[2]}`;
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value).slice(0, 16).replace("T", " ");
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  }

  function formatHistoryTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  }

  function relativeTime(value) {
    if (!value) return "尚未开始";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 60) return "刚刚";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
    if (seconds < 86400 * 7) return `${Math.floor(seconds / 86400)} 天前`;
    return formatDateTime(value);
  }

  function durationText(seconds) {
    if (seconds === null || seconds === undefined) return "—";
    if (seconds < 60) return `${seconds} 秒`;
    return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
  }

  function modeLabel(mode) {
    return mode === "live" ? "真实检索" : "演示样例";
  }

  function statusClass(status) {
    return STATUS_LABELS[status] ? status : "queued";
  }

  function toast(message, type = "info", timeout = 3800) {
    const stack = $("#toast-stack");
    const node = el("div", `toast ${type}`, message);
    stack.appendChild(node);
    window.setTimeout(() => {
      node.classList.add("leaving");
      window.setTimeout(() => node.remove(), 230);
    }, timeout);
  }

  function clearInlineError() {
    $("#inline-error").hidden = true;
  }

  function showInlineError(title, message, missing = []) {
    $("#error-title").textContent = title;
    let text = message;
    if (missing && missing.length) {
      text += ` 缺少服务端配置：${missing.join("、")}。请参考 README 与 .env.example。`;
    }
    $("#error-text").textContent = text;
    $("#inline-error").hidden = false;
  }

  function errorFromRequest(error) {
    const detail = error && error.detail;
    const missing = detail && Array.isArray(detail.missing) ? detail.missing : [];
    const code = detail && typeof detail === "object" ? detail.code : "";
    if (code === "config_missing") {
      return {
        title: "真实检索尚未配置",
        message: "未启动真实检索，也没有静默返回演示内容。",
        missing,
      };
    }
    return { title: "请求失败", message: (error && error.message) || "未知错误", missing };
  }

  function openLayer(id) {
    const layer = $(`#${id}-layer`);
    if (!layer) return;
    app.lastFocused = document.activeElement;
    layer.hidden = false;
    document.body.classList.add("locked");
    window.requestAnimationFrame(() => {
      layer.classList.add("visible");
      const focusTarget =
        id === "interest" ? layer.querySelector(".interest-modal") : layer.querySelector(".drawer-close");
      if (focusTarget) focusTarget.focus({ preventScroll: true });
      if (id === "interest") window.setTimeout(startOrbAnimation, 0);
    });
  }

  function closeLayer(id) {
    const layer = $(`#${id}-layer`);
    if (!layer || layer.hidden) return;
    if (id === "interest") stopOrbAnimation();
    layer.classList.remove("visible");
    window.setTimeout(() => {
      layer.hidden = true;
      if (!$$(".drawer-layer.visible, .modal-layer.visible, .interest-layer.visible").length) {
        document.body.classList.remove("locked");
      }
    }, 280);
    if (app.lastFocused && typeof app.lastFocused.focus === "function") {
      app.lastFocused.focus({ preventScroll: true });
    }
  }

  async function init() {
    bindEvents();
    renderBase();
    try {
      const [config, updateData] = await Promise.all([
        api("/api/config"),
        api("/api/updates"),
      ]);
      app.config = config;
      app.updates = updateData.items || [];
      initializeControls();
      await refreshHistory(false);
      const params = new URLSearchParams(window.location.search);
      const queryRun = params.get("run");
      const storedRun = localStorage.getItem("signalfield:lastRun");
      let runId = queryRun;
      if (!runId && storedRun && app.runs.some((run) => run.id === storedRun)) {
        runId = storedRun;
      }
      if (!runId && app.runs.length) runId = app.runs[0].id;
      const savedPreferences = readInterestPreferences();
      const initialView = savedPreferences && !savedPreferences.skipped ? "radar" : "home";
      if (runId) {
        await loadRun(runId, { initial: true, view: initialView });
      } else {
        renderEmptyLanding();
        setView(initialView, { scroll: false });
      }
      renderUpdateBanner();
      maybeShowInterest();
    } catch (error) {
      const info = errorFromRequest(error);
      showInlineError("无法连接本地服务", info.message);
      $("#loading-skeleton").hidden = true;
      renderEmptyState({
        title: "服务尚未就绪",
        message: "请确认 SignalField 本地服务已经启动，然后刷新页面。",
      });
      $("#results-count").textContent = "00";
    }
  }

  function renderBase() {
    $("#hero-mode").textContent = "DEMO";
    $("#hero-window").textContent = "最近 7 天";
    $("#hero-budget").textContent = "8 搜索 / 15 读取 / 9 模型";
    $("#topic-count").textContent = "已选 0 / 3";
    $("#budget-inline").textContent = "8 / 15 / 9";
    $("#budget-time").textContent = "≤ 120 秒";
  }

  function validBroadGroups() {
    const available = new Set((app.config?.topics || []).map((topic) => topic.label));
    return BROAD_INTERESTS.filter((item) => available.has(item.group));
  }

  function fineGroup(label) {
    const found = INTEREST_KEYWORDS.find((item) => item.label === label);
    return found ? found.group : null;
  }

  function readInterestPreferences() {
    try {
      const raw = localStorage.getItem(INTEREST_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_) {
      return null;
    }
  }

  function restoreInterestPreferences() {
    const saved = readInterestPreferences();
    if (!saved || saved.skipped) return;
    const valid = new Set(validBroadGroups().map((item) => item.group));
    const groups = Array.isArray(saved.groups)
      ? saved.groups.filter((group) => valid.has(group))
      : [];
    if (!groups.length) return;
    const keywords = Array.isArray(saved.keywords) ? saved.keywords : [];
    const allowed = new Set(INTEREST_KEYWORDS.map((item) => item.label));
    const fine = keywords
      .filter((label) => allowed.has(label) && valid.has(fineGroup(label)))
      .filter((label) => groups.includes(fineGroup(label)))
      .slice(0, 3);
    app.interestBroad = new Set(groups);
    app.interestFine = new Set(fine);
    const topicGroups = [...new Set(fine.map((label) => fineGroup(label)))].filter((group) =>
      groups.includes(group)
    );
    app.selectedTopics = new Set(topicGroups.length ? topicGroups : groups);
    app.focusKeywords = [...fine];
  }

  function persistInterestPreferences({ skipped = false } = {}) {
    try {
      const fine = [...app.interestFine];
      const topics = [...new Set(fine.map((label) => fineGroup(label)).filter(Boolean))];
      localStorage.setItem(
        INTEREST_KEY,
        JSON.stringify({
          skipped,
          groups: skipped ? [] : [...app.interestBroad],
          keywords: skipped ? [] : fine,
          topics,
          savedAt: new Date().toISOString(),
        })
      );
    } catch (_) {
      // Private browsing may reject localStorage.
    }
  }

  function maybeShowInterest() {
    if (readInterestPreferences()) return;
    window.setTimeout(() => {
      if (!app.config) return;
      openInterestPicker({ onboarding: true });
    }, 420);
  }

  function shuffled(values) {
    const result = [...values];
    for (let i = result.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [result[i], result[j]] = [result[j], result[i]];
    }
    return result;
  }

  function broadBatch(selectedGroups = [], onboarding = false) {
    const available = validBroadGroups().map((item) => item.group);
    const selected = available.filter((group) => selectedGroups.includes(group));
    const initial = available.filter((group) => INITIAL_BROAD_BATCH.includes(group));
    let candidate = onboarding ? initial : selected;
    const pool = available.filter((group) => !candidate.includes(group));
    candidate = [...candidate, ...shuffled(pool)];
    return [...new Set(candidate)].slice(0, INTEREST_BATCH_SIZE);
  }

  function shuffleBroadInterests() {
    if (app.interestRound !== 1) return;
    app.visibleBroad = broadBatch([...app.interestBroad], false);
    renderOrbItems();
    window.setTimeout(startOrbAnimation, 40);
  }

  function openInterestPicker({ onboarding = false } = {}) {
    if (!app.config) return;
    if (onboarding) {
      app.interestBroad = new Set();
      app.interestFine = new Set();
    } else {
      const current = validBroadGroups()
        .map((item) => item.group)
        .filter((group) => app.selectedTopics.has(group));
      if (current.length) app.interestBroad = new Set(current);
      app.interestFine = new Set(
        [...app.interestFine].filter((label) => app.interestBroad.has(fineGroup(label)))
      );
    }
    app.visibleBroad = broadBatch([...app.interestBroad], onboarding);
    const returnToRadar = !onboarding && Boolean(app.currentRun);
    $("#interest-return-radar").hidden = !returnToRadar;
    $("#interest-skip").hidden = returnToRadar;
    syncInterestModeUI();
    app.interestRound = 1;
    renderInterestStep();
    openLayer("interest");
    window.setTimeout(startOrbAnimation, 120);
  }

  function syncInterestModeUI() {
    const liveAvailable = Boolean(app.config?.modes?.live?.available);
    const note = $("#interest-mode-note");
    $$("#interest-mode-switch button").forEach((button) => {
      const active = button.dataset.interestMode === app.mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
      if (button.dataset.interestMode === "live") {
        button.disabled = !liveAvailable;
        button.title = liveAvailable ? "使用真实搜索并产生少量费用" : "真实检索尚未配置";
      }
    });
    if (note) {
      if (app.mode === "live" && liveAvailable) {
        note.textContent = "DeepSeek Search · 会计费";
      } else if (!liveAvailable) {
        note.textContent = "真实模式未配置";
      } else {
        note.textContent = "演示不耗额度";
      }
    }
  }

  function renderInterestStep() {
    const broadMode = app.interestRound === 1;
    const title = $("#interest-title");
    title.replaceChildren();
    if (broadMode) {
      title.appendChild(document.createTextNode("先圈定"));
      title.appendChild(document.createElement("br"));
      title.appendChild(el("em", "", "你的大方向。"));
      $("#interest-sub").textContent =
        "兴趣球每批展示 8 个方向，最多选 3 个。没兴趣就换一批；已经选中的方向会保留。";
      $("#interest-step-label").textContent = "ROUND 01 / 02 · 广域发现";
      $("#interest-round").textContent = "ROUND 01 / 02";
      $("#interest-note").textContent =
        "第一轮只决定方向，第二轮会在球里换成更细的关键词。默认：最近 7 天 · 演示样例。";
      $("#interest-start").classList.remove("is-final");
      $("#interest-action-label").textContent = "下一步 · 选细一点";
      $("#interest-action-arrow").textContent = "→";
      $("#orb-hint").textContent = "每批 8 个方向 · 点选后换一批也可以保留已选";
      $("#interest-shuffle").hidden = false;
    } else {
      title.appendChild(document.createTextNode("再从大方向里"));
      title.appendChild(document.createElement("br"));
      title.appendChild(el("em", "", "挑细一点。"));
      $("#interest-sub").textContent =
        "球里已经换成你刚选方向下的细分关键词。最多选三个，同方向会合并成一个检索话题。";
      $("#interest-step-label").textContent = "ROUND 02 / 02 · 细分兴趣";
      $("#interest-round").textContent = "ROUND 02 / 02";
      $("#interest-note").textContent =
        "细分兴趣会进入查询规划，让搜索更贴近你在意的性能、兼容性或工具能力。";
      $("#interest-start").classList.add("is-final");
      $("#interest-action-label").textContent = "开始我的扫描";
      $("#interest-action-arrow").textContent = "↗";
      $("#orb-hint").textContent = "第二轮关键词更细 · 最多选三个";
      $("#interest-shuffle").hidden = true;
    }
    $("#interest-back").hidden = broadMode;
    $("#interest-dots").replaceChildren(
      el("span", `interest-dot${broadMode ? " active" : ""}`),
      el("span", `interest-dot${broadMode ? "" : " active"}`)
    );
    renderOrbItems();
    syncInterestSummary();
    window.setTimeout(startOrbAnimation, 60);
  }

  function renderOrbItems() {
    const container = $("#interest-keywords");
    stopOrbAnimation();
    container.replaceChildren();
    const broadMode = app.interestRound === 1;
    const visible = new Set(app.visibleBroad);
    const items = broadMode
      ? validBroadGroups()
          .filter((item) => visible.has(item.group))
          .map((item) => ({
            key: item.group,
            group: item.group,
            label: item.label,
            hint: item.hint,
            kind: "broad",
          }))
      : INTEREST_KEYWORDS.filter((item) => app.interestBroad.has(item.group)).map((item) => ({
          key: item.label,
          group: item.group,
          label: item.label,
          hint: item.hint,
          kind: "fine",
        }));
    items.forEach((item, index) => {
      const selected = broadMode
        ? app.interestBroad.has(item.key)
        : app.interestFine.has(item.key);
      const button = el(
        "button",
        `orb-keyword${item.kind === "broad" ? " is-broad" : ""}${selected ? " selected" : ""}`
      );
      button.type = "button";
      button.dataset.interestKey = item.key;
      button.dataset.interestKind = item.kind;
      button.setAttribute("aria-pressed", String(selected));
      button.title = `${item.group} · ${item.hint}`;
      if (item.kind === "broad") {
        const main = el("span", "orb-main");
        main.appendChild(el("span", "orb-group", `DIRECTION 0${index + 1}`));
        main.appendChild(el("span", "orb-label", item.label));
        button.appendChild(main);
      } else {
        button.appendChild(el("span", "orb-group", item.group));
        button.appendChild(el("span", "orb-label", item.label));
      }
      button.appendChild(el("span", "orb-check", "✓"));
      button.addEventListener("click", () => handleOrbSelect(item));
      container.appendChild(button);
    });
  }

  function handleOrbSelect(item) {
    if (app.interestRound === 1) {
      if (app.interestBroad.has(item.key)) {
        app.interestBroad.delete(item.key);
        [...app.interestFine].forEach((label) => {
          if (fineGroup(label) === item.key) app.interestFine.delete(label);
        });
      } else if (app.interestBroad.size >= 3) {
        toast("最多选择三个大方向。先取消一个，再选新的。", "error");
        return;
      } else {
        app.interestBroad.add(item.key);
      }
    } else if (app.interestFine.has(item.key)) {
      app.interestFine.delete(item.key);
    } else if (app.interestFine.size >= 3) {
      toast("最多选择三个细分兴趣。先取消一个，再选新的。", "error");
      return;
    } else {
      app.interestFine.add(item.key);
    }
    syncOrbSelection();
    syncInterestSummary();
  }

  function syncOrbSelection() {
    const broadMode = app.interestRound === 1;
    $$(".orb-keyword", $("#interest-keywords")).forEach((button) => {
      const selected = broadMode
        ? app.interestBroad.has(button.dataset.interestKey)
        : app.interestFine.has(button.dataset.interestKey);
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  function syncInterestSummary() {
    const summary = $("#interest-summary");
    const chips = $("#interest-chips");
    chips.replaceChildren();
    const broadMode = app.interestRound === 1;
    if (broadMode) {
      const groups = validBroadGroups()
        .map((item) => item.group)
        .filter((group) => app.interestBroad.has(group));
      if (!groups.length) {
        summary.textContent = "还没有选择";
        summary.classList.add("empty");
      } else {
        summary.textContent = groups.join(" / ");
        summary.classList.remove("empty");
        groups.forEach((group) => {
          const chip = el("span", "interest-chip");
          chip.appendChild(el("strong", "", group));
          chip.appendChild(el("em", "", "方向"));
          chips.appendChild(chip);
        });
      }
      $("#interest-start").disabled = groups.length === 0;
      $("#interest-back").hidden = true;
    } else {
      const fine = INTEREST_KEYWORDS.map((item) => item.label).filter((label) =>
        app.interestFine.has(label)
      );
      if (!fine.length) {
        summary.textContent = "还没有选细分兴趣";
        summary.classList.add("empty");
      } else {
        summary.textContent = fine.join("　/　");
        summary.classList.remove("empty");
        fine.forEach((label) => {
          const chip = el("span", "interest-chip");
          chip.appendChild(el("strong", "", label));
          chip.appendChild(el("em", "", fineGroup(label) || ""));
          chips.appendChild(chip);
        });
      }
      $("#interest-start").disabled = fine.length === 0;
      $("#interest-back").hidden = false;
    }
  }

  function goToFineRound() {
    if (!app.interestBroad.size) {
      toast("先在球里选至少一个大方向。", "error");
      return;
    }
    app.interestFine = new Set(
      [...app.interestFine].filter((label) => app.interestBroad.has(fineGroup(label)))
    );
    app.interestRound = 2;
    renderInterestStep();
  }

  function handleInterestAction() {
    if (app.interestRound === 1) {
      goToFineRound();
      return;
    }
    startFromInterest();
  }

  async function startFromInterest() {
    const fine = [...app.interestFine];
    if (!fine.length) {
      toast("至少选择一个细分兴趣。", "error");
      return;
    }
    const groups = (app.config?.topics || [])
      .map((topic) => topic.label)
      .filter((group) => fine.some((label) => fineGroup(label) === group));
    if (!groups.length) {
      toast("这些兴趣没有对应的检索方向，请重新选择。", "error");
      return;
    }
    if (app.mode === "demo") {
      const unsupported = groups.filter((group) => !DEMO_GROUPS.has(group));
      if (unsupported.length) {
        toast(
          `演示语料暂未覆盖「${unsupported.join("、")}」，请在上方切换“真实检索”。`,
          "error",
          5200
        );
        return;
      }
    }
    app.focusKeywords = fine;
    app.selectedTopics = new Set(groups);
    app.customTopics = [];
    persistInterestPreferences();
    renderPresetTopics();
    renderCustomTopics();
    updateSelectionUI();
    stopOrbAnimation();
    closeLayer("interest");
    setView("radar", { scroll: true });
    renderRadarPending();
    toast(`已跳转到你的雷达：${fine.join("、")}`, "success");
    window.setTimeout(() => performScan(), 340);
  }

  function skipInterestPicker() {
    persistInterestPreferences({ skipped: true });
    stopOrbAnimation();
    closeLayer("interest");
    setView(app.currentRun ? "radar" : "home", { scroll: true });
    toast("已打开示例雷达，你可以随时点“调整兴趣”。", "info");
  }

  function stopOrbAnimation() {
    if (app.orbAnimation && app.orbAnimation.raf) {
      window.cancelAnimationFrame(app.orbAnimation.raf);
    }
    app.orbAnimation = null;
    const pause = $("#orb-pause");
    if (pause) pause.textContent = "暂停漂浮";
  }

  function arrangePausedOrb() {
    const state = app.orbAnimation;
    if (!state) return;
    const count = state.items.length;
    const cols = count <= 3 ? 1 : 2;
    const rows = Math.ceil(count / cols);
    const xOffset = state.width * 0.2;
    const ySpacing = Math.min(state.height * 0.155, 74);
    state.items.forEach((item, index) => {
      const col = index % cols;
      const row = Math.floor(index / cols);
      item.x = cols === 1 ? 0 : (col === 0 ? -xOffset : xOffset);
      item.y = (row - (rows - 1) / 2) * ySpacing;
      item.node.style.transform = `translate(-50%, -50%) translate(${item.x}px, ${item.y}px) scale(${item.scale.toFixed(3)})`;
    });
  }

  function toggleOrbPause() {
    if (!app.orbAnimation) return;
    app.orbAnimation.paused = !app.orbAnimation.paused;
    if (app.orbAnimation.paused) arrangePausedOrb();
    $("#orb-pause").textContent = app.orbAnimation.paused ? "继续漂浮" : "暂停漂浮";
  }

  function startOrbAnimation() {
    stopOrbAnimation();
    const layer = $("#interest-layer");
    const orb = $("#interest-orb");
    const container = $("#interest-keywords");
    if (!layer || !orb || !container || layer.hidden) return;
    if (!layer.classList.contains("visible")) {
      window.setTimeout(startOrbAnimation, 70);
      return;
    }
    const nodes = $$(".orb-keyword", container);
    if (!nodes.length) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const rect = orb.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    if (!width || !height) {
      window.setTimeout(startOrbAnimation, 80);
      return;
    }
    const radius = Math.min(width, height) / 2 - 9;
    const items = nodes.map((node, index) => {
      const nodeRect = node.getBoundingClientRect();
      const bound = Math.hypot(nodeRect.width / 2, nodeRect.height / 2) + 2;
      const angle = (index / nodes.length) * Math.PI * 2 + (index % 2 ? 0.22 : 0);
      const speed = 0.42 + ((index * 37) % 21) / 100;
      const orbit = radius * (nodes.length <= 3 ? 0.58 : 0.6);
      return {
        node,
        x: Math.cos(angle) * orbit,
        y: Math.sin(angle) * orbit,
        vx: Math.cos(angle + Math.PI / 2) * speed,
        vy: Math.sin(angle + Math.PI / 2) * speed,
        bound,
        scale: reduceMotion ? 1 : 0.35,
        delay: index * 45,
      };
    });
    if (reduceMotion) {
      $("#orb-pause").hidden = true;
      items.forEach((item, index) => {
        const angle = (index / items.length) * Math.PI * 2;
        const orbit = Math.max(70, radius * 0.58);
        item.x = Math.cos(angle) * orbit;
        item.y = Math.sin(angle) * orbit;
        item.node.style.transform = `translate(-50%, -50%) translate(${item.x}px, ${item.y}px)`;
        item.node.style.opacity = "1";
      });
      return;
    }
    const state = {
      orb,
      width,
      height,
      radius,
      items,
      paused: false,
      started: performance.now(),
      raf: null,
      last: performance.now(),
    };
    app.orbAnimation = state;
    state.paused = false;
    $("#orb-pause").hidden = false;
    $("#orb-pause").textContent = "暂停漂浮";
    orb.onmouseenter = () => {
      if (app.orbAnimation) app.orbAnimation.hoverPaused = true;
    };
    orb.onmouseleave = () => {
      if (app.orbAnimation) app.orbAnimation.hoverPaused = false;
    };

    const frame = (now) => {
      if (app.orbAnimation !== state) return;
      const elapsed = Math.min(34, now - state.last);
      state.last = now;
      const dt = elapsed / 16.67;
      const maxTravel = (item) => Math.max(20, state.radius - item.bound);
      const constrain = (item) => {
        const distance = Math.hypot(item.x, item.y);
        const limit = maxTravel(item);
        if (distance <= limit || distance <= 0) return;
        const nx = item.x / distance;
        const ny = item.y / distance;
        item.x = nx * limit;
        item.y = ny * limit;
        const dot = item.vx * nx + item.vy * ny;
        if (dot > 0) {
          item.vx -= 2 * dot * nx;
          item.vy -= 2 * dot * ny;
        }
      };
      const moving = !state.paused && !state.hoverPaused;
      if (moving) {
        items.forEach((item) => {
          item.x += item.vx * dt;
          item.y += item.vy * dt;
        });
      }
      // Manual pause uses a stable grid layout so tags stay clickable. While
      // floating, resolve overlaps to keep the sphere readable.
      if (!state.paused) {
        for (let pass = 0; pass < 4; pass += 1) {
          items.forEach(constrain);
          for (let i = 0; i < items.length; i += 1) {
            for (let j = i + 1; j < items.length; j += 1) {
              const a = items[i];
              const b = items[j];
              let dx = b.x - a.x;
              let dy = b.y - a.y;
              let distance = Math.hypot(dx, dy);
              const minDistance = a.bound + b.bound + 9;
              if (distance >= minDistance) continue;
              if (distance < 0.001) {
                dx = 1;
                dy = 0;
                distance = 1;
              }
              const nx = dx / distance;
              const ny = dy / distance;
              const overlap = (minDistance - distance) / 2;
              a.x -= nx * overlap;
              a.y -= ny * overlap;
              b.x += nx * overlap;
              b.y += ny * overlap;
              if (moving) {
                const relative = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
                if (relative < 0) {
                  a.vx += relative * nx;
                  a.vy += relative * ny;
                  b.vx -= relative * nx;
                  b.vy -= relative * ny;
                }
              }
            }
          }
        }
        items.forEach(constrain);
      }
      items.forEach((item) => {
        const age = now - state.started;
        if (age > item.delay) item.scale += (1 - item.scale) * 0.1;
        item.node.style.transform = `translate(-50%, -50%) translate(${item.x}px, ${item.y}px) scale(${item.scale.toFixed(3)})`;
        item.node.style.opacity = item.scale < 0.6 ? "0" : "1";
      });
      state.raf = window.requestAnimationFrame(frame);
    };
    state.raf = window.requestAnimationFrame(frame);
  }

  function initializeControls() {
    const config = app.config;
    // Keep the initial manual-selection state valid after the direction list
    // grows: the backend still caps a single task at three topics.
    app.selectedTopics = new Set(config.topics.slice(0, 3).map((topic) => topic.label));
    restoreInterestPreferences();
    renderPresetTopics();
    renderCustomTopics();
    syncModeUI();
    updateSelectionUI();
    updateBudgetSummary();
    app.window = "week";
    app.mode = "demo";
    syncSegmented();
    renderDailyNote();
    $("#results-subtitle").textContent = "只保留有正文逐字证据、值得关注的变化。";
  }

  function renderPresetTopics() {
    const container = $("#topic-presets");
    container.replaceChildren();
    if (!app.config) return;
    app.config.topics.forEach((topic, index) => {
      const button = el("button", "topic-option");
      button.type = "button";
      button.setAttribute("aria-pressed", String(topicSelected(topic.label)));
      button.dataset.topic = topic.label;
      button.classList.toggle("selected", topicSelected(topic.label));
      const top = el("div", "topic-topline");
      const glyph = el("span", "topic-glyph", pad2(index + 1));
      const check = el("span", "topic-check", "✓");
      top.append(glyph, check);
      const label = el("strong", "", topic.label);
      const desc = el("small", "", topic.description);
      button.append(top, label, desc);
      button.addEventListener("click", () => togglePreset(topic.label));
      container.appendChild(button);
    });
  }

  function togglePreset(label) {
    app.focusKeywords = [];
    if (topicSelected(label)) {
      if (app.selectedTopics.size === 1) {
        toast("至少保留一个话题，才能开始检索。", "error");
        return;
      }
      app.selectedTopics.delete(label);
      const index = app.customTopics.indexOf(label);
      if (index >= 0) app.customTopics.splice(index, 1);
    } else {
      if (app.selectedTopics.size >= 3) {
        toast("单任务最多三个话题。先取消一个，再选择新的。", "error");
        return;
      }
      app.selectedTopics.add(label);
    }
    renderPresetTopics();
    renderCustomTopics();
    updateSelectionUI();
  }

  function addCustomTopic(rawValue) {
    const value = String(rawValue || "")
      .normalize("NFKC")
      .replace(/<[^>]+>/g, "")
      .replace(/\s+/g, " ")
      .trim();
    if (!value) {
      toast("请输入一个自定义话题。", "error");
      return;
    }
    if (value.length > 24) {
      toast("单个话题不能超过 24 个字符。", "error");
      return;
    }
    if (value.length < 2) {
      toast("自定义话题至少需要 2 个字符。", "error");
      return;
    }
    const all = new Set([...(app.config?.topics || []).map((t) => t.label), ...app.customTopics]);
    if (Array.from(all).some((topic) => topic.toLowerCase() === value.toLowerCase())) {
      toast("这个话题已经添加过了。", "error");
      return;
    }
    if (app.selectedTopics.size >= 3) {
      toast("单任务最多三个话题。先取消一个，再添加。", "error");
      return;
    }
    app.customTopics.push(value);
    app.selectedTopics.add(value);
    app.focusKeywords = [];
    $("#custom-topic").value = "";
    renderCustomTopics();
    updateSelectionUI();
  }

  function renderCustomTopics() {
    const container = $("#custom-tags");
    container.replaceChildren();
    app.customTopics.forEach((topic) => {
      if (!app.selectedTopics.has(topic)) return;
      const tag = el("span", "custom-tag");
      tag.appendChild(el("span", "", topic));
      const remove = el("button", "", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", `移除话题 ${topic}`);
      remove.addEventListener("click", () => {
        app.selectedTopics.delete(topic);
        app.focusKeywords = [];
        app.customTopics = app.customTopics.filter((item) => item !== topic);
        renderPresetTopics();
        renderCustomTopics();
        updateSelectionUI();
      });
      tag.appendChild(remove);
      container.appendChild(tag);
    });
  }

  function updateSelectionUI() {
    const count = app.selectedTopics.size;
    $("#topic-count").textContent = `已选 ${count} / 3`;
    const hint = $("#selection-hint");
    hint.classList.toggle("warn", count === 0);
    if (count === 0) hint.textContent = "至少选择一个话题。";
    else if (count === 3) hint.textContent = "已选满三个话题。开始扫描后，Agent 会为每个方向保留覆盖机会。";
    else hint.textContent = "选择预设方向，或添加一个你关心的细分话题。";
    updateStartState();
  }

  function syncSegmented() {
    $$("#window-segmented button").forEach((button) => {
      const active = button.dataset.window === app.window;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    $$("#mode-segmented button").forEach((button) => {
      const active = button.dataset.mode === app.mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
      if (button.dataset.mode === "live" && app.config && !app.config.modes.live.available) {
        button.classList.add("unavailable");
      }
    });
  }

  function syncModeUI() {
    const live = app.mode === "live";
    const available = app.config ? app.config.modes.live.available : false;
    const notice = $("#mode-notice");
    const noticeText = $("#mode-notice-text");
    const availability = $("#mode-availability");
    const footnote = $("#scan-footnote");
    notice.classList.remove("live", "warning", "demo");
    if (!live) {
      notice.classList.add("demo");
      $(".notice-mark", notice).textContent = "DEMO";
      noticeText.textContent =
        "演示使用虚构样例；未执行实时搜索，不消耗远程调用额度；演示日期不代表真实事件日期。";
      availability.textContent = "演示不耗额度";
      footnote.textContent = "演示使用虚构语料，未执行实时搜索，也不消耗远程额度。";
    } else if (available) {
      notice.classList.add("live");
      $(".notice-mark", notice).textContent = "LIVE";
      const providerLabel = app.config.modes.live.provider_label || "搜索服务";
      const modelLabel = app.config.modes.live.model || "兼容模型";
      noticeText.textContent = `真实检索会调用 ${providerLabel} 与 ${modelLabel}。搜索摘要只用于发现线索，事实必须回到已读取正文。`;
      availability.textContent = `${providerLabel} + ${modelLabel}`;
      footnote.textContent = "真实模式会消耗服务额度；今日调用实时显示，单次任务仍受搜索/读取/模型上限约束。";
    } else {
      notice.classList.add("warning");
      $(".notice-mark", notice).textContent = "SETUP";
      const missing = (app.config?.modes.live.missing || []).join("、");
      noticeText.textContent = `真实检索尚未配置完整${
        missing ? `（缺少 ${missing}）` : ""
      }。启动时会明确报错，不会静默返回演示内容。`;
      availability.textContent = "服务端未配置";
      footnote.textContent = "真实模式缺配置时会明确失败；不会把演示内容当成真实结果。";
    }
    renderDailyNote();
    updateStartState();
  }

  function compactTokens(value) {
    const number = Number(value || 0);
    if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}m`;
    if (number >= 1_000) return `${(number / 1_000).toFixed(1)}k`;
    return String(number);
  }

  function dailyUsageText(daily) {
    const data = daily || {};
    const searches = data.search_calls ?? 0;
    const reads = data.read_calls ?? 0;
    const models = data.model_calls ?? 0;
    const tokensIn = compactTokens(data.tokens_in);
    const tokensOut = compactTokens(data.tokens_out);
    return `搜索 ${searches} 次 · 正文 ${reads} 次 · 模型 ${models} 次 · tokens ${tokensIn}/${tokensOut}`;
  }

  function renderDailyNote() {
    const node = $("#daily-note");
    if (!node) return;
    const daily = app.config && app.config.daily_usage;
    if (!daily) {
      node.textContent = "";
      return;
    }
    node.classList.remove("warn");
    node.textContent = `今日真实消耗：${dailyUsageText(daily)}`;
  }

  function renderRadarUsage(run) {
    const node = $("#radar-usage-values");
    const live = $("#usage-live");
    const panel = $("#radar-usage");
    if (!node || !live || !panel) return;
    const daily =
      (run && run.daily_usage) || (app.config && app.config.daily_usage) || null;
    if (!daily) {
      node.textContent = "等待用量数据";
      return;
    }
    node.textContent = dailyUsageText(daily);
    const active = Boolean(run && isActive(run.status) && run.mode === "live");
    panel.classList.toggle("is-active", active);
    live.textContent = run && run.mode === "demo" ? "演示不计入" : active ? "实时" : "已同步";
  }

  async function refreshConfig() {
    try {
      app.config = await api("/api/config");
      updateBudgetSummary();
      syncModeUI();
    } catch (_) {
      // Non-critical.
    }
  }

  function updateBudgetSummary() {
    if (!app.config) return;
    const limits = app.config.limits;
    $("#budget-inline").textContent = `${limits.searches} / ${limits.reads} / ${limits.model_calls}`;
    $("#budget-time").textContent = `≤ ${limits.seconds} 秒`;
    $("#hero-budget").textContent = `${limits.searches} 搜索 / ${limits.reads} 读取 / ${limits.model_calls} 模型`;
  }

  function updateStartState() {
    const button = $("#scan-btn");
    const active = app.currentRun && isActive(app.currentRun.status);
    button.disabled = app.isStarting || active || app.selectedTopics.size === 0;
    const label = $(".scan-btn-label", button);
    if (app.isStarting) label.textContent = "正在启动…";
    else if (active) label.textContent = "扫描进行中";
    else label.textContent = app.currentRun ? "开始新的扫描" : "开始扫描";
  }

  function setView(view, { scroll = true } = {}) {
    const next = view === "radar" ? "radar" : "home";
    const changed = document.body.dataset.view !== next;
    document.body.dataset.view = next;
    $("#radar-toolbar").hidden = next !== "radar";
    const backButton = $("#back-to-radar-btn");
    if (backButton) backButton.hidden = next !== "home" || !app.currentRun;
    if (next === "radar") renderRadarToolbar(app.currentRun);
    if (changed && scroll) window.scrollTo({ top: 0, behavior: "auto" });
    if (changed) {
      document.body.classList.remove("view-transition");
      void document.body.offsetWidth;
      document.body.classList.add("view-transition");
      window.setTimeout(() => document.body.classList.remove("view-transition"), 500);
    }
  }

  function renderRadarToolbar(run) {
    renderRadarUsage(run);
    if (!run) {
      $("#radar-run-created").textContent = "等待扫描";
      $("#radar-context").textContent = "正在按你的兴趣准备扫描。";
      $("#radar-focus-chips").replaceChildren(el("span", "radar-focus-chip", "等待兴趣"));
      $("#radar-focus-hint").textContent = "兴趣选择会在扫描时进入查询规划。";
      return;
    }
    const topics = run.topics || [];
    const fine = run.focus_keywords || [];
    const count = (run.events || []).length;
    const when = run.created_at ? `扫描于 ${formatHistoryTime(run.created_at)}` : "刚刚扫描";
    $("#radar-run-created").textContent = when;
    const statusCopy =
      run.status === "running" || run.status === "queued"
        ? "正在读取正文、整理事件并核验证据。"
        : count
        ? `已整理 ${count} 个有正文证据的事件。`
        : run.stop_message || "这次没有形成可展示事件。";
    $("#radar-context").textContent = `${modeLabel(run.mode)} · ${
      run.window === "day" ? "最近 24 小时" : "最近 7 天"
    } · ${statusCopy}`;
    const chips = $("#radar-focus-chips");
    chips.replaceChildren();
    topics.forEach((topic) => {
      const chip = el("span", "radar-focus-chip");
      chip.appendChild(el("span", "", topic));
      chip.appendChild(el("em", "", "方向"));
      chips.appendChild(chip);
    });
    fine.forEach((keyword) => {
      const chip = el("span", "radar-focus-chip fine");
      chip.appendChild(el("span", "", keyword));
      chip.appendChild(el("em", "", fineGroup(keyword) || "细分"));
      chips.appendChild(chip);
    });
    if (!topics.length && !fine.length) {
      chips.appendChild(el("span", "radar-focus-chip", "完整示例"));
    }
    $("#radar-focus-hint").textContent = fine.length
      ? "第二轮细分兴趣已进入本轮查询规划。"
      : "本轮按大方向扫描；可以点“调整兴趣”补充细分关键词。";
  }

  function renderRadarPending() {
    $("#radar-run-created").textContent = "正在启动扫描";
    $("#radar-context").textContent = "正在把你的兴趣转成查询计划，并打开第二页的雷达视图。";
    const chips = $("#radar-focus-chips");
    chips.replaceChildren();
    [...app.interestBroad].forEach((group) => {
      const chip = el("span", "radar-focus-chip");
      chip.appendChild(el("span", "", group));
      chip.appendChild(el("em", "", "方向"));
      chips.appendChild(chip);
    });
    [...app.interestFine].forEach((keyword) => {
      const chip = el("span", "radar-focus-chip fine");
      chip.appendChild(el("span", "", keyword));
      chip.appendChild(el("em", "", fineGroup(keyword) || "细分"));
      chips.appendChild(chip);
    });
    $("#radar-focus-hint").textContent = "扫描完成后，这里会显示本轮实际关注范围。";
  }

  function renderHero() {
    const run = app.currentRun;
    const count = run && run.events ? run.events.length : 0;
    $("#hero-count").textContent = pad2(count);
    $("#hero-mode").textContent = run ? (run.mode === "demo" ? "DEMO" : "LIVE") : "IDLE";
    $("#hero-window").textContent = run
      ? run.window === "day"
        ? "最近 24 小时"
        : "最近 7 天"
      : app.window === "day"
      ? "最近 24 小时"
      : "最近 7 天";
    $("#hero-scanned").textContent = run
      ? isActive(run.status)
        ? "正在扫描"
        : relativeTime(run.created_at)
      : "尚未开始";
    if (run && run.budget && run.budget.limits) {
      const limits = run.budget.limits;
      $("#hero-budget").textContent = `${limits.searches} 搜索 / ${limits.reads} 读取 / ${limits.model_calls} 模型`;
    }
  }

  function renderUpdateBanner() {
    const banner = $("#update-banner");
    const count = app.updates.length;
    if (!count) {
      banner.hidden = true;
      return;
    }
    const updated = app.updates.filter((item) => item.change_type === "updated").length;
    const fresh = count - updated;
    const bits = [];
    if (fresh) bits.push(`${fresh} 条新收录`);
    if (updated) bits.push(`${updated} 条实质更新`);
    $("#update-title").textContent = `有 ${bits.join("、")}，等待查看`;
    const titles = app.updates.slice(0, 2).map((item) => item.title);
    $("#update-text").textContent =
      titles.join(" · ") +
      (count > 2 ? `，另有 ${count - 2} 条` : "") +
      "。重复转载不会产生重复提醒。";
    banner.hidden = false;
  }

  async function refreshUpdates() {
    try {
      const data = await api("/api/updates");
      app.updates = data.items || [];
      app.lastUpdateFetch = Date.now();
      renderUpdateBanner();
    } catch (_) {
      // A transient poll failure should not disrupt the active task.
    }
  }

  async function markAllUpdatesRead() {
    if (!app.updates.length) return;
    const runIds = [...new Set(app.updates.map((item) => item.run_id))];
    try {
      await Promise.all(runIds.map((runId) => api(`/api/runs/${runId}/read`, { method: "POST" })));
      toast("已将更新标记为已读。", "success");
      await refreshUpdates();
      await refreshHistory(false);
      if (app.currentRun) {
        app.resultsSig = null;
        await refreshCurrentRun({ silent: true });
      }
    } catch (error) {
      toast(error.message || "标记失败。", "error");
    }
  }

  function viewLatestUpdate() {
    if (!app.updates.length) return;
    const runId = app.updates[0].run_id;
    const exists = app.runs.find((run) => run.id === runId);
    if (!exists) {
      refreshHistory(false).then(() => loadRun(runId));
    } else {
      loadRun(runId);
    }
    const results = $("#results-section");
    if (results) results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function handleStart(event) {
    event.preventDefault();
    await performScan();
  }

  async function performScan() {
    clearInlineError();
    if (!app.selectedTopics.size) {
      showInlineError("还没有选择话题", "至少选择一个话题后再开始扫描。");
      return;
    }
    if (app.currentRun && isActive(app.currentRun.status)) {
      toast("当前任务尚未结束，请等待完成或先取消。", "error");
      return;
    }
    app.isStarting = true;
    updateStartState();
    try {
      const run = await api("/api/runs", {
        method: "POST",
        body: JSON.stringify({
          topics: [...app.selectedTopics],
          focus_keywords: app.focusKeywords,
          window: app.window,
          mode: app.mode,
        }),
      });
      app.currentRun = run;
      app.resultsSig = null;
      app.progressRunId = null;
      localStorage.setItem("signalfield:lastRun", run.id);
      setRunQuery(run.id);
      setView("radar", { scroll: true });
      renderAll();
      renderProgress(run);
      startPolling();
      await refreshHistory(false);
      toast(run.mode === "demo" ? "演示扫描已启动。" : "真实检索已启动。", "success");
    } catch (error) {
      const info = errorFromRequest(error);
      showInlineError(info.title, info.message, info.missing);
    } finally {
      app.isStarting = false;
      updateStartState();
    }
  }

  async function loadRun(runId, options = {}) {
    stopPolling();
    try {
      const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
      app.currentRun = run;
      app.resultsSig = null;
      app.progressRunId = null;
      localStorage.setItem("signalfield:lastRun", run.id);
      setRunQuery(run.id);
      if (options.view !== false) {
        setView(options.view || "radar", { scroll: false });
      }
      renderAll();
      await refreshHistory(false);
      if (isActive(run.status)) startPolling();
      if (options.scroll) {
        window.scrollTo({ top: 0, behavior: "auto" });
      }
      updateStartState();
    } catch (error) {
      if (error.status === 404) {
        toast("该任务记录不存在。", "error");
        const stored = localStorage.getItem("signalfield:lastRun");
        if (stored === runId) localStorage.removeItem("signalfield:lastRun");
      } else {
        toast(error.message || "加载任务失败。", "error");
      }
    }
  }

  function setRunQuery(runId) {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("run", runId);
      window.history.replaceState({}, "", url);
    } catch (_) {
      // Non-critical.
    }
  }

  function startPolling() {
    stopPolling();
    app.pollFailures = 0;
    app.pollTimer = window.setInterval(pollCurrentRun, 900);
    window.setTimeout(pollCurrentRun, 320);
  }

  function stopPolling() {
    if (app.pollTimer) {
      window.clearInterval(app.pollTimer);
      app.pollTimer = null;
    }
  }

  async function pollCurrentRun() {
    if (app.pollBusy || !app.currentRun) return;
    const runId = app.currentRun.id;
    const previousStatus = app.currentRun.status;
    app.pollBusy = true;
    try {
      const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
      if (!app.currentRun || app.currentRun.id !== runId) return;
      app.pollFailures = 0;
      app.currentRun = run;
      renderAll();
      if (!isActive(run.status)) {
        stopPolling();
        await refreshHistory(false);
        await refreshUpdates();
        await refreshConfig();
        updateStartState();
        if (previousStatus !== run.status) {
          announceCompletion(run);
        }
      }
    } catch (_) {
      app.pollFailures += 1;
      if (app.pollFailures >= 4) {
        stopPolling();
        toast("无法更新任务状态，请刷新页面重试。", "error");
      }
    } finally {
      app.pollBusy = false;
    }
  }

  async function refreshCurrentRun(options = {}) {
    if (!app.currentRun) return;
    try {
      const run = await api(`/api/runs/${encodeURIComponent(app.currentRun.id)}`);
      app.currentRun = run;
      app.resultsSig = null;
      if (!options.silent) renderAll();
      else {
        renderResults(run);
        renderProgress(run);
      }
      updateStartState();
    } catch (_) {
      // Keep the existing view.
    }
  }

  function announceCompletion(run) {
    if (run.status === "cancelled") {
      toast("任务已取消，已完成的结果已保留。", "info");
      return;
    }
    if (run.status === "failed") {
      toast(run.stop_message || "任务失败，请查看检索记录。", "error", 5000);
      return;
    }
    const count = (run.events || []).length;
    if (run.status === "partial") {
      toast(`任务部分完成，保留 ${count} 个事件。${run.stop_message || ""}`, "info", 5200);
    } else if (count) {
      toast(`扫描完成，整理出 ${count} 个有证据支持的事件。`, "success");
    } else {
      toast(run.stop_message || "扫描完成，但本次没有形成可展示事件。", "info", 5000);
    }
  }

  function renderAll() {
    renderHero();
    renderRadarToolbar(app.currentRun);
    if (app.currentRun) {
      renderProgress(app.currentRun);
      renderResults(app.currentRun);
      $("#progress-section").hidden = false;
      $("#results-section").hidden = false;
    } else {
      $("#progress-section").hidden = true;
      renderEmptyLanding();
    }
    renderUpdateBanner();
    updateStartState();
  }

  const STAGES = [
    { label: "规划", keys: ["created", "planning"] },
    { label: "搜索", keys: ["searching"] },
    { label: "读取", keys: ["reading"] },
    { label: "抽取", keys: ["extracting"] },
    { label: "补搜", keys: ["checking_gaps", "gap_searching", "gap_reading"] },
    { label: "核验", keys: ["verifying", "ranking", "done"] },
  ];

  function renderProgress(run) {
    const active = isActive(run.status);
    const status = run.status;
    $("#run-status").className = `run-status ${statusClass(status)}`;
    $("#run-status").replaceChildren(
      el("i", "dot"),
      document.createTextNode(STATUS_LABELS[status] || status)
    );

    const topics = run.topics || [];
    const windowLabel = run.window === "day" ? "最近 24 小时" : "最近 7 天";
    const focus = (run.focus_keywords || []).length
      ? ` · 细分：${run.focus_keywords.join("、")}`
      : "";
    $("#run-meta").textContent = `${modeLabel(run.mode)} · ${topics.join(" / ")} · ${windowLabel}${focus} · ${durationText(
      run.elapsed_seconds
    )}`;

    const progress = run.progress || { percent: 0, stage: "created", message: "准备中" };
    $("#stage-label").textContent = progress.message || STAGE_LABELS[progress.stage] || "检索中";
    $("#progress-percent").textContent = `${Math.round(progress.percent || 0)}%`;
    $("#progress-fill").style.width = `${Math.max(0, Math.min(100, progress.percent || 0))}%`;

    renderStages(progress.stage, status);
    renderStopBanner(run);
    renderRunMetrics(run);
    renderWarnings(run);

    const cancel = $("#cancel-btn");
    cancel.hidden = !active;
    cancel.disabled = status === "cancelling";
    cancel.textContent = status === "cancelling" ? "正在取消…" : "取消任务";

    const details = $("#query-details");
    const previousStatus = app.lastProgressStatus;
    if (app.progressRunId !== run.id) {
      details.open = active;
      app.progressRunId = run.id;
    } else if (isActive(previousStatus) && !active && details.open) {
      details.open = false;
    }
    app.lastProgressStatus = run.status;
    renderQueries(run);
  }

  function renderStages(stage, status) {
    const rail = $("#stage-rail");
    rail.replaceChildren();
    let activeIndex = STAGES.findIndex((item) => item.keys.includes(stage));
    if (activeIndex < 0) activeIndex = 0;
    const complete = !isActive(status) && stage === "done";
    STAGES.forEach((item, index) => {
      const node = el("div", "stage-item");
      if (complete || index < activeIndex) node.classList.add("done");
      if (!complete && index === activeIndex) node.classList.add("active");
      node.append(el("span", "stage-num", complete || index < activeIndex ? "✓" : pad2(index + 1)));
      node.appendChild(el("span", "", item.label));
      rail.appendChild(node);
    });
  }

  function renderStopBanner(run) {
    const banner = $("#stop-banner");
    if (isActive(run.status) || !run.stop_message) {
      banner.hidden = true;
      return;
    }
    banner.hidden = false;
    $("#stop-label").textContent = STOP_LABELS[run.stop_reason] || "停止原因";
    $("#stop-message").textContent = run.stop_message;
  }

  function renderRunMetrics(run) {
    const metrics = $("#run-metrics");
    metrics.replaceChildren();
    const usage = run.usage || {};
    const limits = (run.budget && run.budget.limits) || {};
    const chips = [
      [`搜索 ${usage.search_calls || 0}/${limits.searches || 8}`, ""],
      [`读取 ${usage.read_attempts || 0}/${limits.reads || 15}`, ""],
      [`模型 ${usage.model_calls || 0}/${limits.model_calls || 9}`, ""],
      [`耗时 ${durationText(run.elapsed_seconds)}`, ""],
      [`查询 ${(run.queries || []).length} 条`, ""],
      [`已读正文 ${(run.documents || []).filter((doc) => doc.read_status === "success").length} 篇`, ""],
    ];
    if (run.mode === "demo") chips.push(["演示 · 0 次远程调用", "demo"]);
    else chips.push([`远程调用 ${usage.remote_calls || 0} 次`, ""]);
    if (usage.tokens_in || usage.tokens_out) {
      chips.push([`tokens ${usage.tokens_in || 0} / ${usage.tokens_out || 0}`, ""]);
    }
    if (usage.estimated_cost_usd > 0) {
      chips.push([`估算 $${Number(usage.estimated_cost_usd).toFixed(4)}`, ""]);
    }
    const alertReasons = new Set([
      "daily_budget_exhausted",
      "run_budget_exhausted",
      "budget_exhausted",
      "timeout",
    ]);
    if (alertReasons.has(run.stop_reason)) {
      chips.push(["预算或时间受限", "alert"]);
    }
    chips.forEach(([label, klass]) => metrics.appendChild(el("span", `metric-chip ${klass}`, label)));
  }

  function renderWarnings(run) {
    let container = $(".run-warnings");
    if (!container) {
      container = el("div", "run-warnings");
      const metrics = $("#run-metrics");
      metrics.insertAdjacentElement("afterend", container);
    }
    container.replaceChildren();
    const warnings = (run.warnings || []).filter(Boolean).slice(0, 4);
    if (!warnings.length) {
      container.hidden = true;
      return;
    }
    container.hidden = false;
    container.appendChild(el("span", "run-warnings-label", "注意"));
    warnings.forEach((warning) => container.appendChild(el("p", "", warning)));
  }

  function renderQueries(run) {
    const list = $("#query-list");
    list.replaceChildren();
    const queries = run.queries || [];
    $("#query-summary").textContent = `${queries.length} 条查询 · ${(run.documents || []).length} 个候选网页`;
    queries.forEach((query, index) => {
      const item = el("div", "query-item");
      const badge = el("span", `query-badge round-${query.round || 0}`, `Q${index + 1}`);
      const main = el("div", "query-main");
      main.appendChild(el("div", "query-title", query.text));
      main.appendChild(
        el(
          "div",
          "query-purpose",
          `目的：${query.purpose || "未记录"}`
        )
      );
      const meta = el("div", "query-meta");
      const roundText = query.round ? `第 ${query.round} 轮补搜` : "初始搜索";
      meta.appendChild(el("span", "", roundText));
      meta.appendChild(el("span", "", STRATEGY_LABELS[query.strategy] || query.strategy || "搜索"));
      meta.appendChild(el("span", "", `${query.result_count || 0} 个候选`));
      if (query.new_documents) meta.appendChild(el("span", "", `新增 ${query.new_documents} 个网页`));
      if (query.attempts > 1) meta.appendChild(el("span", "", `尝试 ${query.attempts} 次`));
      if (query.error) meta.appendChild(el("span", "", query.error));
      main.appendChild(meta);
      const status = el(
        "span",
        `query-status ${query.status || "planned"}`,
        QUERY_STATUS[query.status] || query.status || "待执行"
      );
      item.append(badge, main, status);
      list.appendChild(item);
    });
    if (!queries.length) {
      list.appendChild(el("p", "history-empty", run.status === "queued" ? "任务排队中，查询计划尚未生成。" : "暂无查询记录。"));
    }

    const actions = $("#actions-list");
    actions.replaceChildren();
    (run.actions || []).forEach((action) => {
      const node = el("div", "action-item");
      const top = el("div", "action-top");
      top.appendChild(el("span", "", `补搜第 ${action.round} 轮`));
      top.appendChild(
        el("strong", "", ACTION_OUTCOME[action.outcome] || action.outcome || "已记录")
      );
      node.appendChild(top);
      node.appendChild(el("p", "action-title", `原因：${action.reason || "—"}`));
      node.appendChild(
        el(
          "p",
          "action-queries",
          `查询：${(action.query_texts || []).join(" / ") || "—"} · 新事件 ${action.new_events || 0} · 新事实 ${
            action.new_facts || 0
          } · 解决缺口 ${action.resolved_gaps || 0}`
        )
      );
      actions.appendChild(node);
    });
  }

  function resultsSignature(run) {
    return JSON.stringify({
      id: run.id,
      status: run.status,
      stop: run.stop_reason,
      events: (run.events || []).map((event) => [
        event.id,
        event.read_at,
        event.change_type,
        event.event_date,
      ]),
      verification: run.verification,
    });
  }

  function renderResults(run, force = false) {
    const signature = resultsSignature(run);
    const count = (run.events || []).length;
    $("#results-count").textContent = pad2(count);
    $("#result-mode").textContent = modeLabel(run.mode);
    const demo = run.mode === "demo";
    if (isActive(run.status) && !count) {
      $("#results-subtitle").textContent = "正在读取正文、聚合事件并核验证据。";
    } else if (demo) {
      $("#results-subtitle").textContent = "以下为虚构样例，用于体验检索流程与证据结构，不代表真实事件。";
    } else {
      $("#results-subtitle").textContent = "只保留有正文逐字证据、值得关注的变化。";
    }
    const unread = hasUnread(run.events || []);
    $("#mark-run-read-btn").hidden = !unread;

    if (signature === app.resultsSig && !force) return;
    app.resultsSig = signature;

    const body = $("#results-body");
    body.replaceChildren();

    if (isActive(run.status) && !count) {
      const grid = el("div", "skeleton-grid");
      for (let i = 0; i < 2; i += 1) grid.appendChild(el("div", "skeleton-card"));
      body.appendChild(grid);
      return;
    }

    if (!count) {
      renderEmptyRun(run);
      return;
    }

    const grid = el("div", "event-grid");
    run.events.forEach((event, index) => grid.appendChild(buildEventCard(event, index, run)));
    body.appendChild(grid);
    body.appendChild(buildTimeline(run.events));
  }

  function buildEventCard(event, index, run) {
    const unread = !event.read_at && ["new", "updated"].includes(event.change_type);
    const card = el("article", `event-card${unread ? " unread" : ""}`);
    card.style.setProperty("--i", String(index));
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `查看事件：${event.title}`);
    card.dataset.eventId = event.id;
    if (unread) card.appendChild(el("span", "unread-dot", ""));

    const top = el("div", "event-card-top");
    const tags = el("div", "event-tags");
    const topic = el("span", "topic-tag", event.topic);
    topic.dataset.topic = event.topic;
    tags.appendChild(topic);
    if (run.mode === "demo") tags.appendChild(el("span", "demo-tag", "样例"));
    const change = el(
      "span",
      `change-tag ${event.change_type || "new"}`,
      event.change_type === "updated" ? "实质更新" : event.change_type === "unchanged" ? "已收录" : "新收录"
    );
    if (event.change_note) change.title = event.change_note;
    tags.appendChild(change);
    const date = el("div", "event-date");
    if (event.event_date) {
      date.appendChild(el("strong", "", formatMonthDay(event.event_date)));
      date.appendChild(
        el("span", "", `${String(event.event_date).slice(0, 4)} · 事件日期`)
      );
    } else {
      date.appendChild(el("strong", "", "待确认"));
      date.appendChild(el("span", "", "事件日期"));
    }
    top.append(tags, date);
    card.appendChild(top);

    card.appendChild(el("h3", "event-title", event.title));
    card.appendChild(el("p", "event-summary", event.summary || "暂无摘要。"));
    const stats = el("div", "event-stats");
    const group = el("div", "event-stat-group");
    group.appendChild(el("span", "", `${(event.facts || []).length} 条事实`));
    group.appendChild(el("span", "", `${event.independent_source_count || 0} 个来源域名`));
    if (!event.event_date) group.appendChild(el("span", "date-unknown", "日期未确认"));
    stats.appendChild(group);
    const actions = el("div", "event-card-actions");
    const primary = primarySource(event);
    if (run.mode !== "demo" && primary && isHttpUrl(primary.url)) {
      const sourceLink = el("a", "event-source-link", "原文 ↗");
      sourceLink.href = primary.url;
      sourceLink.target = "_blank";
      sourceLink.rel = "noopener noreferrer";
      sourceLink.referrerPolicy = "no-referrer";
      sourceLink.title = `打开原网页：${primary.domain || primary.url}`;
      sourceLink.addEventListener("click", (clickEvent) => clickEvent.stopPropagation());
      actions.appendChild(sourceLink);
    }
    actions.appendChild(el("span", "event-open", "↗"));
    stats.appendChild(actions);
    card.appendChild(stats);

    const open = () => openDetail(event.id);
    card.addEventListener("click", open);
    card.addEventListener("keydown", (keyboardEvent) => {
      if (keyboardEvent.target !== card) return;
      if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
        keyboardEvent.preventDefault();
        open();
      }
    });
    return card;
  }

  function buildTimeline(events) {
    const block = el("section", "timeline-block");
    const head = el("div", "timeline-head");
    head.appendChild(el("h3", "", "事件时间线"));
    head.appendChild(el("span", "", "按事件日期排序 · 未确认日期置后"));
    block.appendChild(head);
    const timeline = el("div", "timeline");
    const ordered = [...events].sort((left, right) => {
      if (!left.event_date && !right.event_date) return 0;
      if (!left.event_date) return 1;
      if (!right.event_date) return -1;
      return String(right.event_date).localeCompare(String(left.event_date));
    });
    ordered.forEach((event) => {
      const button = el("button", "timeline-item");
      button.type = "button";
      const date = el("div", "timeline-date");
      date.appendChild(document.createTextNode(event.event_date ? formatMonthDay(event.event_date) : "待确认"));
      date.appendChild(
        el("small", "", event.event_date ? `${String(event.event_date).slice(0, 4)} · ${event.topic}` : event.topic)
      );
      const axis = el("div", "timeline-axis");
      axis.appendChild(el("span", "timeline-dot"));
      const content = el("div", "timeline-content");
      content.appendChild(el("div", "timeline-topic", event.topic));
      const title = el("h4", "", event.title);
      content.appendChild(title);
      button.append(date, axis, content);
      button.addEventListener("click", () => openDetail(event.id));
      timeline.appendChild(button);
    });
    block.appendChild(timeline);
    return block;
  }

  function renderEmptyLanding() {
    $("#loading-skeleton")?.remove();
    renderEmptyState({
      title: "设定一个关注方向，开始第一次扫描",
      message:
        "SignalField 会先规划查询，再读取正文、聚合事件、核验逐字证据；如果日期或条件仍有缺口，会说明原因并决定是否补搜。",
      actions: [
        {
          label: "选择话题",
          onClick: () => $("#console-title")?.scrollIntoView({ behavior: "smooth", block: "start" }),
        },
      ],
    });
    $("#results-count").textContent = "00";
    $("#results-head")?.classList.add("is-empty");
  }

  function renderEmptyRun(run) {
    const mapping = {
      no_results: {
        title: "所选时间窗内没有找到相关结果",
        message: run.stop_message || "搜索没有返回可读取的候选网页。可以扩大时间范围，或换一个更具体的话题。",
      },
      no_verifiable_events: {
        title: "没有形成满足证据要求的事件",
        message:
          run.stop_message ||
          "读取到了一些网页，但没有事件能通过正文与逐字片段核验。系统没有用搜索摘要冒充证据。",
      },
      read_failed: {
        title: "来源都没能读取成功",
        message: run.stop_message || "候选网页存在，但正文读取失败。失败页面没有作为证据使用。",
      },
      user_cancel: {
        title: "任务已取消",
        message: run.stop_message || "已保留取消前完成的有效结果。",
      },
      daily_budget_exhausted: {
        title: "今日额度已用完",
        message: run.stop_message || "为避免重复试用耗尽额度，任务在预算边界处停止。",
      },
      run_budget_exhausted: {
        title: "达到本次任务预算",
        message: run.stop_message || "任务已停止，未完成的结果没有被包装成确定结论。",
      },
      timeout: {
        title: "达到时间上限",
        message: run.stop_message || "任务在 120 秒边界处停止，已保留可得的部分结果。",
      },
      service_unavailable: {
        title: "搜索服务不可用",
        message: run.stop_message || "工具连续失败，任务停止。没有返回演示内容作为替代。",
      },
      internal_error: {
        title: "任务执行失败",
        message: run.stop_message || "发生了内部异常，请查看检索记录或稍后重试。",
      },
    };
    const info =
      mapping[run.stop_reason] ||
      (run.status === "failed"
        ? { title: "这次扫描没有完成", message: run.stop_message || "请查看检索记录。" }
        : { title: "本次没有可展示事件", message: run.stop_message || "未为填满页面而生成内容。" });
    const actions = [];
    if (!["daily_budget_exhausted", "run_budget_exhausted"].includes(run.stop_reason)) {
      actions.push({
        label: "调整范围再扫描",
        onClick: () => $("#console-title")?.scrollIntoView({ behavior: "smooth", block: "start" }),
      });
    }
    if (run.mode === "demo") {
      actions.push({
        label: "配置真实检索",
        quiet: true,
        onClick: () => openLayer("eval"),
      });
    }
    renderEmptyState({ ...info, actions });
  }

  function renderEmptyState({ title, message, actions = [] }) {
    const body = $("#results-body");
    body.replaceChildren();
    const empty = el("div", "empty-state");
    empty.appendChild(el("div", "empty-icon", "∅"));
    empty.appendChild(el("h3", "", title));
    empty.appendChild(el("p", "", message));
    if (actions.length) {
      const wrap = el("div", "empty-actions");
      actions.forEach((action) => {
        const button = el("button", action.quiet ? "mini-btn mini-btn-quiet" : "mini-btn", action.label);
        button.type = "button";
        button.addEventListener("click", action.onClick);
        wrap.appendChild(button);
      });
      empty.appendChild(wrap);
    }
    body.appendChild(empty);
  }

  function openDetail(eventId) {
    if (!app.currentRun) return;
    const event = (app.currentRun.events || []).find((item) => item.id === eventId);
    if (!event) return;
    app.activeEventId = eventId;
    const content = $("#detail-content");
    content.replaceChildren(buildDetail(app.currentRun, event));
    $("#detail-loading").hidden = true;
    openLayer("detail");
    const panel = $("#detail-drawer");
    panel.scrollTop = 0;
    if (!event.read_at && event.change_type !== "unchanged") {
      markEventRead(event);
    }
  }

  function buildDetail(run, event) {
    const root = el("div", "detail-scroll");
    const header = el("div", "drawer-header");
    const headerLeft = el("div");
    headerLeft.appendChild(el("p", "eyebrow small", "EVENT DOSSIER / 事件档案"));
    headerLeft.appendChild(el("h2", "detail-title", event.title));
    const close = el("button", "icon-btn drawer-close");
    close.type = "button";
    close.setAttribute("aria-label", "关闭事件详情");
    close.textContent = "×";
    close.addEventListener("click", () => closeLayer("detail"));
    header.append(headerLeft, close);
    root.appendChild(header);

    const topline = el("div", "detail-topline");
    const tags = el("div", "detail-tags");
    const topic = el("span", "topic-tag", event.topic);
    topic.dataset.topic = event.topic;
    tags.appendChild(topic);
    tags.appendChild(
      el(
        "span",
        `change-tag ${event.change_type || "new"}`,
        event.change_type === "updated" ? "实质更新" : event.change_type === "unchanged" ? "已收录" : "新收录"
      )
    );
    if (run.mode === "demo") tags.appendChild(el("span", "demo-tag", "虚构样例"));
    topline.appendChild(tags);
    topline.appendChild(el("span", "mono", `#${String(event.id || "").slice(-6).toUpperCase()}`));
    root.appendChild(topline);

    const dateline = el("div", "detail-dateline");
    const dateWrap = el("span");
    dateWrap.appendChild(document.createTextNode("事件日期 "));
    dateWrap.appendChild(el("strong", "", event.event_date ? formatDateOnly(event.event_date) : "未确认"));
    dateline.appendChild(dateWrap);
    dateline.appendChild(
      el(
        "span",
        `confidence-chip ${event.date_confidence === "unknown" ? "unknown" : ""}`,
        DATE_CONFIDENCE[event.date_confidence] || "日期待确认"
      )
    );
    dateline.appendChild(el("span", "", `${(event.facts || []).length} 条已核验事实`));
    dateline.appendChild(el("span", "", `${event.independent_source_count || 0} 个来源域名`));
    root.appendChild(dateline);

    const primary = primarySource(event);
    if (run.mode !== "demo" && primary && isHttpUrl(primary.url)) {
      const originalLink = el("a", "detail-original-link");
      originalLink.href = primary.url;
      originalLink.target = "_blank";
      originalLink.rel = "noopener noreferrer";
      originalLink.referrerPolicy = "no-referrer";
      originalLink.appendChild(el("span", "", "查看原网页"));
      originalLink.appendChild(
        el("span", "detail-original-domain", `${primary.domain || "外部链接"} ↗`)
      );
      root.appendChild(originalLink);
    }

    if (run.mode === "demo") {
      root.appendChild(
        el(
          "div",
          "demo-detail-note",
          "此事件的标题、项目、来源、日期和事实均为虚构演示内容。来源使用保留域名，无法访问，也不代表真实网页。"
        )
      );
    }

    root.appendChild(el("p", "detail-summary", event.summary || "暂无摘要。"));

    if (event.why_it_matters) {
      const section = el("section", "detail-section");
      section.appendChild(
        sectionHead("关注理由", "模型生成 · 与来源事实分开")
      );
      const box = el("div", "why-box");
      box.appendChild(el("span", "why-label", "WHY IT MATTERS"));
      box.appendChild(document.createTextNode(event.why_it_matters));
      section.appendChild(box);
      root.appendChild(section);
    }

    const factSection = el("section", "detail-section");
    factSection.appendChild(
      sectionHead("事实与证据", `${(event.facts || []).length} 条 · 已做逐字匹配`)
    );
    const facts = el("div", "fact-list");
    (event.facts || []).forEach((fact) => {
      const item = el("div", "fact-item");
      const top = el("div", "fact-top");
      top.appendChild(el("span", "fact-check", "✓"));
      top.appendChild(el("div", "fact-statement", fact.statement));
      item.appendChild(top);
      if (fact.conditions) {
        const conditions = el("p", "fact-conditions");
        conditions.appendChild(el("strong", "", "适用条件："));
        conditions.appendChild(document.createTextNode(fact.conditions));
        item.appendChild(conditions);
      }
      const evidenceList = el("div", "evidence-list");
      (fact.evidence || []).forEach((evidence) => {
        const evidenceNode = el("div");
        evidenceNode.appendChild(el("div", "evidence-quote", evidence.quote));
        const source = el("div", "evidence-source");
        source.appendChild(el("span", "evidence-verified", "✓ 原文片段匹配"));
        source.appendChild(el("span", "", evidence.domain || ""));
        if (evidence.published_at) {
          source.appendChild(el("span", "", `文章日期 ${formatDateOnly(evidence.published_at)}`));
        }
        if (run.mode !== "demo" && isHttpUrl(evidence.url)) {
          const link = el("a", "", "打开来源");
          link.href = evidence.url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.referrerPolicy = "no-referrer";
          source.appendChild(link);
        }
        evidenceNode.appendChild(source);
        evidenceList.appendChild(evidenceNode);
      });
      item.appendChild(evidenceList);
      facts.appendChild(item);
    });
    factSection.appendChild(facts);
    root.appendChild(factSection);

    if ((event.unresolved || []).length) {
      const section = el("section", "detail-section");
      section.appendChild(sectionHead("未确认事项", "保留不确定性"));
      const list = el("div", "unresolved-list");
      event.unresolved.forEach((text) => list.appendChild(el("div", "unresolved-item", text)));
      section.appendChild(list);
      root.appendChild(section);
    }

    const sourcesSection = el("section", "detail-section");
    sourcesSection.appendChild(
      sectionHead("来源", `${(event.sources || []).length} 篇实际读取`)
    );
    const sources = el("div", "sources-list");
    (event.sources || []).forEach((source) => {
      const item = el("div", "source-item");
      const top = el("div", "source-top");
      if (run.mode !== "demo" && isHttpUrl(source.url)) {
        const link = el("a", "source-title", source.title || source.url);
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.referrerPolicy = "no-referrer";
        top.appendChild(link);
      } else {
        top.appendChild(el("span", "source-title", source.title || "演示来源"));
      }
      top.appendChild(el("span", "source-role", source.role === "primary" ? "主要来源" : "佐证来源"));
      item.appendChild(top);
      const meta = el("div", "source-meta");
      meta.appendChild(el("span", "domain", source.domain || ""));
      if (source.published_at) meta.appendChild(el("span", "", `文章发布 ${formatDateOnly(source.published_at)}`));
      if (source.fetched_at) meta.appendChild(el("span", "", `抓取 ${formatDateTime(source.fetched_at)}`));
      if (run.mode === "demo") meta.appendChild(el("span", "source-disabled", "虚构来源，不提供访问"));
      item.appendChild(meta);
      sources.appendChild(item);
    });
    sourcesSection.appendChild(sources);
    root.appendChild(sourcesSection);

    const verification = run.verification || {};
    const section = el("section", "detail-section");
    section.appendChild(sectionHead("核验说明", "程序检查，不等于独立验证"));
    const box = el("div", "verification-box");
    const score = el("div", "verification-score");
    score.appendChild(el("span", "", "本次检索引用支持率"));
    score.appendChild(
      el(
        "strong",
        "",
        verification.citation_support_rate === null || verification.citation_support_rate === undefined
          ? "—"
          : `${verification.citation_support_rate}%`
      )
    );
    box.appendChild(score);
    box.appendChild(
      document.createTextNode(
        `${verification.evidence_verified || 0} / ${verification.evidence_total || 0} 个原文片段通过匹配。${
          verification.note || "程序只校验来源存在与片段匹配，语义支持需另行判断。"
        }`
      )
    );
    section.appendChild(box);
    root.appendChild(section);

    root.appendChild(
      el(
        "p",
        "detail-footer-note",
        "事件日期、文章发布时间与抓取时间分别保留。转载合并不等于多源独立验证；来源事实与模型生成的关注理由已分开呈现。"
      )
    );
    return root;
  }

  function sectionHead(title, meta) {
    const head = el("div", "detail-section-head");
    head.appendChild(el("h3", "", title));
    head.appendChild(el("span", "", meta));
    return head;
  }

  function primarySource(event) {
    const sources = Array.isArray(event.sources) ? event.sources : [];
    return sources.find((source) => source.role === "primary") || sources[0] || null;
  }

  function isHttpUrl(value) {
    try {
      const parsed = new URL(value);
      return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch (_) {
      return false;
    }
  }

  async function markEventRead(event) {
    try {
      await api(`/api/events/${encodeURIComponent(event.id)}/read`, { method: "POST" });
      event.read_at = new Date().toISOString();
      app.resultsSig = null;
      renderResults(app.currentRun, true);
      app.updates = app.updates.filter((item) => item.id !== event.id);
      renderUpdateBanner();
      await refreshHistory(false);
    } catch (_) {
      // Reading state is non-critical to the dossier.
    }
  }

  async function markCurrentRunRead() {
    if (!app.currentRun) return;
    try {
      await api(`/api/runs/${encodeURIComponent(app.currentRun.id)}/read`, { method: "POST" });
      (app.currentRun.events || []).forEach((event) => {
        if (!event.read_at) event.read_at = new Date().toISOString();
      });
      app.resultsSig = null;
      renderResults(app.currentRun, true);
      await refreshUpdates();
      await refreshHistory(false);
      toast("本期事件已标记为已读。", "success");
    } catch (error) {
      toast(error.message || "标记已读失败。", "error");
    }
  }

  async function cancelCurrentRun() {
    if (!app.currentRun) return;
    const button = $("#cancel-btn");
    button.disabled = true;
    try {
      await api(`/api/runs/${encodeURIComponent(app.currentRun.id)}/cancel`, { method: "POST" });
      app.currentRun.status = "cancelling";
      app.currentRun.cancel_requested = true;
      renderProgress(app.currentRun);
      toast("已请求取消，已完成的检索结果会保留。", "info");
      startPolling();
    } catch (error) {
      button.disabled = false;
      toast(error.message || "取消失败。", "error");
    }
  }

  async function refreshHistory(render = true) {
    try {
      const data = await api("/api/runs?limit=40");
      app.runs = data.runs || [];
      $("#history-count").textContent = String(app.runs.length);
      if (render) renderHistory();
      else renderHistory();
    } catch (_) {
      if (render) $("#history-list").replaceChildren(el("p", "history-empty", "无法加载检索历史。"));
    }
    updateStartState();
  }

  function renderHistory() {
    const container = $("#history-list");
    container.replaceChildren();
    if (!app.runs.length) {
      container.appendChild(
        el("p", "history-empty", "还没有检索记录。完成第一次扫描后，任务、查询和事件都会保存在本地 SQLite 中。")
      );
      return;
    }
    app.runs.forEach((run) => {
      const button = el("button", "history-item");
      button.type = "button";
      if (app.currentRun && app.currentRun.id === run.id) button.classList.add("current");
      const top = el("div", "history-top");
      top.appendChild(el("span", "history-time", formatHistoryTime(run.created_at)));
      const badges = el("div", "history-badges");
      badges.appendChild(el("span", "history-status " + statusClass(run.status), STATUS_LABELS[run.status] || run.status));
      badges.appendChild(el("span", "history-status", run.mode === "demo" ? "DEMO" : "LIVE"));
      top.appendChild(badges);
      button.appendChild(top);

      const topics = el("div", "history-topics");
      (run.topics || []).forEach((topic) => topics.appendChild(el("span", "history-topic", topic)));
      if (!run.topics || !run.topics.length) topics.appendChild(el("span", "", "未记录话题"));
      button.appendChild(topics);

      const meta = el("div", "history-meta");
      meta.appendChild(el("span", "", `${run.card_count || 0} 个事件`));
      meta.appendChild(el("span", "", `${run.window === "day" ? "24 小时" : "7 天"}`));
      meta.appendChild(el("span", "", `${run.progress || 0}%`));
      if (run.unread > 0) {
        const unread = el("span", "history-unread");
        unread.appendChild(el("i", "dot"));
        unread.appendChild(document.createTextNode(`${run.unread} 条未读`));
        meta.appendChild(unread);
      }
      button.appendChild(meta);
      button.addEventListener("click", () => {
        closeLayer("history");
        loadRun(run.id, { scroll: true });
      });
      container.appendChild(button);
    });
  }

  function bindEvents() {
    $("#scan-form").addEventListener("submit", handleStart);
    $("#custom-topic").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addCustomTopic(event.target.value);
      }
    });
    $("#add-topic-btn").addEventListener("click", () => addCustomTopic($("#custom-topic").value));
    $$("#window-segmented button").forEach((button) => {
      button.addEventListener("click", () => {
        app.window = button.dataset.window;
        syncSegmented();
        renderHero();
      });
    });
    $$("#mode-segmented button").forEach((button) => {
      button.addEventListener("click", () => {
        app.mode = button.dataset.mode;
        syncSegmented();
        syncModeUI();
        renderHero();
      });
    });
    $("#history-btn").addEventListener("click", () => {
      refreshHistory(false).then(() => {
        renderHistory();
        openLayer("history");
      });
    });
    $("#mark-run-read-btn").addEventListener("click", markCurrentRunRead);
    $("#read-all-updates-btn").addEventListener("click", markAllUpdatesRead);
    $("#view-updates-btn").addEventListener("click", viewLatestUpdate);
    $("#cancel-btn").addEventListener("click", cancelCurrentRun);
    $("#dismiss-error").addEventListener("click", clearInlineError);
    $("#eval-btn").addEventListener("click", () => openLayer("eval"));
    $("#footer-eval-btn").addEventListener("click", () => openLayer("eval"));
    $("#interest-open-btn").addEventListener("click", () => openInterestPicker());
    $("#results-change-direction-btn").addEventListener("click", () => openInterestPicker());
    $("#back-to-radar-btn").addEventListener("click", () => setView("radar", { scroll: true }));
    $("#radar-interest-btn").addEventListener("click", () => openInterestPicker());
    $("#interest-return-radar").addEventListener("click", () => {
      closeLayer("interest");
      if (app.currentRun) setView("radar", { scroll: false });
    });
    $("#radar-rescan-btn").addEventListener("click", () => performScan());
    $("#radar-settings-btn").addEventListener("click", () => {
      setView("home", { scroll: false });
      $("#console-title").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $("#interest-start").addEventListener("click", handleInterestAction);
    $("#interest-back").addEventListener("click", () => {
      app.interestRound = 1;
      renderInterestStep();
    });
    $("#interest-skip").addEventListener("click", skipInterestPicker);
    $("#orb-pause").addEventListener("click", toggleOrbPause);
    $("#interest-shuffle").addEventListener("click", shuffleBroadInterests);
    $$("#interest-mode-switch button").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.disabled) return;
        app.mode = button.dataset.interestMode;
        syncSegmented();
        syncModeUI();
        syncInterestModeUI();
        updateStartState();
      });
    });
    let resizeTimer = null;
    window.addEventListener("resize", () => {
      if (!$("#interest-layer").classList.contains("visible")) return;
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(startOrbAnimation, 180);
    });
    $$("[data-close]").forEach((node) => {
      node.addEventListener("click", () => closeLayer(node.dataset.close));
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if ($("#interest-layer").classList.contains("visible")) {
        closeLayer("interest");
      } else if ($("#detail-layer").classList.contains("visible")) {
        closeLayer("detail");
      } else if ($("#history-layer").classList.contains("visible")) {
        closeLayer("history");
      } else if ($("#eval-layer").classList.contains("visible")) {
        closeLayer("eval");
      }
    });
    const queryDetails = $("#query-details");
    queryDetails.addEventListener("toggle", () => {
      // User intent wins; polling re-renders but does not reset this element.
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
