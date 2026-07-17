# Guide 11 — 交互式 Dashboard (v1)

v1 的 Dashboard 是单文件 HTML + 原生 JS，10 个页面可切换，零外部依赖。

## 生成方式

```bash
python dashboard.py --config .agent-eval/config.yaml
```

输出 `.agent-eval/reports/dashboard.html`。聚合所有 run 的 scores / charts / diagnosis / judges 数据。

## 10 个页面

### 1. Overview
总览：总 run 数、最新硬失败、最新总分、已接受 patch 数、回归测试次数、最新 latency。最近 10 个 run 的表格。

### 2. Scenario
选择 run → 看该 run 的场景通过率条形图。每个场景一根条，颜色按通过率（绿/黄/红）。

### 3. Failures
选择 run → 看失败 Pareto（按类型降序的条形图）+ 失败详情表（case_id / 类型 / 建议修改 / mutation 规则）。

### 4. Trace Viewer
选择 run + case → 看该 case 的 trace 时间线（每步一个色块，颜色按 event_type）+ 步骤详情表。鼠标悬停色块看 tooltip。

### 5. Tool Graph
选择 run → 看工具调用频次条形图 + 调用顺序表（从→到→次数）。

### 6. Optimization
迭代曲线（每个 run 一根条，高度=分数）。已接受 patch 数。

### 7. Patch Compare
所有 A/B 的 Gatekeeper 决策历史表（run_id / verdict / 理由）。

### 8. Regression
回归测试历史表（时间 / run_id / 分数 / 硬失败 / PASS/FAIL）。数据来自 `regression_trend.jsonl`。

### 9. Judges
选择 run → 看 Judge 平均分条形图 + Judge Agreement Matrix 表 + Gatekeeper 结论。

### 10. Cost / Latency
所有 run 的 latency p50 / mean 表格。用于监控延迟退化。

## 设计原则

1. **暗色主题**：护眼，适合长时间看数据
2. **左侧导航固定**：10 个页面随时切换
3. **零外部依赖**：所有 CSS / JS / 数据内联，单文件可分享
4. **原生 JS**：不依赖 React / Vue，浏览器直接打开就能用
5. **响应式数据**：选择 run 后自动更新对应页面内容
6. **语义色**：绿 pass / 红 fail / 黄 warning，badge 样式统一

## 与 v0.5 HTML 报告的区别

| 维度 | v0.5 HTML 报告 | v1 Dashboard |
|------|---------------|--------------|
| 目的 | 单次 run 的专业报告 | 多 run 的交互式探索 |
| 数据 | 单个 run | 聚合所有 run |
| 交互 | 静态（除目录导航） | 可切换 run / case |
| 页面 | 11 节滚动 | 10 个 tab 切换 |
| 主题 | 亮色商务 | 暗色数据探索 |
| 输出 | `<run_id>.html` | `dashboard.html` |

两者互补：HTML 报告适合分享给领导，Dashboard 适合工程师自己探索。

## 扩展

v1 的 Dashboard 是纯静态的。如果要加交互（如点击 case 跳转 trace viewer），可以在 `JS_TEMPLATE` 里加 event listener。如果要接后端 API 做实时刷新，可以把 `collect_all_data` 改成 fetch 请求。

v2 可能会做 Web 服务版 Dashboard，但 v1 保持单文件静态。

---

## v1.1.1 报告统一门户（report_portal.py）

v1.1.1 新增 `report_portal.py`，是 Dashboard 的演进版本：把散落在 `.agent-eval/` 各处的**报告 / 进度 / 迭代 / 质量分**聚合到同一个网站的 5 个页面。与 v1 Dashboard 的关系是**互补 + 升级**：Dashboard 聚合 run 维度的分数/失败/Judge；门户聚合**跨产物类型**的统一视图（报告卡片 + 进度时间线 + 迭代历史 + 质量雷达）。

### 生成方式

```bash
python report_portal.py --config .agent-eval/config.yaml
```

输出 `.agent-eval/reports/portal.html`（单文件，可邮件分享）。

### 5 个页面

#### 1. Overview
6 张 KPI 卡片（报告总数 / 进度 session 数 / 迭代次数 / 12 维质量加权分 / 当前 run 分数 / 最近报告时间）+ run 分数 sparkline + 当前 run 信息卡 + 最近报告表。

#### 2. Reports
报告卡片网格，每张卡显示标题/类型/时间/run_id/大小。带客户端搜索框 + 类型下拉筛选 + 预览展开/收起。数据源：`report_manager.list_reports()`。

#### 3. Progress
9 步进度环（当前 session 完成度）+ 水平时间线（每步一个节点，颜色按状态：绿完成/蓝运行/红失败，hover 显示 tooltip 含 `duration_ms`）+ 各步平均耗时条形图 + session 列表表。数据源：`progress_tracker.timeline()` + `summary()`。

#### 4. Iterations
质量分趋势 sparkline（每次迭代的 weighted_total）+ 迭代卡片网格（每张卡显示 proposal_id / before-after 对比 / add/modify/deprecate 计数）。数据源：`case_io.load_iterations()`。

#### 5. Quality
12 维雷达图（9 标准 + 3 Agent 专属）+ 加权总分条 + 低分维度告警卡（<0.6）+ 12 个维度详情卡。数据源：`case_quality_*.json`（自动搜索 `reports_dir` 和 `data/`）。

### 设计语言：深色玻璃态

- 基底：`#0f172a`（slate-900）+ 两个径向渐变光晕（indigo 8% / violet 6%）
- 卡片：`rgba(30, 41, 59, 0.7)` + `backdrop-filter: blur(12px)` + 1px indigo 透明边框
- 高亮：`linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)` 渐变文字（KPI 数值、h1）
- 悬浮动效：`transform: translateY(-4px)` + `box-shadow: 0 12px 32px rgba(99,102,241,.25)` + 左侧色条 `::before` 渐显（width 3px→4px, opacity 0.4→1）
- SVG 图表：手写，无 Chart.js / D3，每个数据点带 `<title>` 原生 tooltip

### SVG 工具集（内置）

| 函数 | 用途 |
|------|------|
| `_svg_progress_ring(pct, size)` | 圆形进度环，`stroke-dasharray` + linearGradient |
| `_svg_sparkline(values, w, h)` | 迷你折线图，run 分数趋势 |
| `_svg_radar(dims, size)` | 12 维雷达图，多层网格 + 数据多边形 |
| `_svg_bar_h(items, ...)` | 横向条形图，各步平均耗时 |
| KPI 卡 / 时间线节点 / 维度卡 | HTML + CSS，带 `:hover` 升起 |

### 与 v1 Dashboard 对比

| 维度 | v1 Dashboard | v1.1.1 门户 |
|------|--------------|-------------|
| 聚合对象 | run 维度（分数/失败/Judge） | 跨产物类型（报告/进度/迭代/质量） |
| 页面数 | 10 | 5 |
| 进度可视化 | 无 | 9 步时间线 + 进度环 |
| 质量分可视化 | 无 | 12 维雷达 |
| 迭代历史 | 无 | sparkline + 卡片 |
| 设计语言 | 暗色数据探索 | 深色玻璃态 + 悬浮动效 |
| 数据源 | scores / charts / diagnosis | index.jsonl + progress.jsonl + case_iterations.jsonl + case_quality_*.json |

两者互补：Dashboard 适合工程师深挖单个 run；门户适合一眼看全本轮评测的**全部产物 + 进度 + 质量趋势**。建议每轮评测收尾时同时生成两者。

### 进度埋点契约

门户 Progress 页依赖 `sidecar.py` 持久化的事件。9 个 step 编号约定：

| step | 名称 | 何时上报 |
|------|------|---------|
| 1 | 需求分析 | requirements-analysis 子 skill 开始/结束 |
| 2 | 用例生成 | test-case-generator 子 skill 开始/结束 |
| 3 | 用例执行+桥接 | execute_testcases + excel_to_uatr 开始/结束 |
| 5 | F1-F8 诊断 | diagnoser.py 开始/结束 |
| 6 | 多 Judge 评审 | multi_judge.py 开始/结束 |
| 7 | 优化迭代 | reference_optimizer + auto_patcher 开始/结束 |
| 4.5 | 用例自优化 | case_optimizer 开始/结束（用 step=45 上报） |
| 4 | 报告生成 | generate_report + html_report 开始/结束 |
| 9 | 统一门户 | report_portal 开始/结束 |

session_id 自动续接：同一次评测运行的多个 step 共享一个 session_id（由 `progress_tracker` 根据"上一个非终态事件"推断）。无需用户传入。
