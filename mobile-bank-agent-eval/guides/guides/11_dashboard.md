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
