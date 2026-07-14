# Guide 08 — 专业评测报告结构 (v0.5)

v0.5 把报告从"pass/fail + 单 case 表格"升级为 11 节结构化报告，同时输出 `charts.json` 供可视化使用。

## 输出文件

每次 run 产物（位于 `.agent-eval/runs/<run_id>/`）：

| 文件 | 内容 |
|------|------|
| `report.md` | Markdown 报告（11 节） |
| `report.html` | HTML 报告（单文件，内联 CSS + SVG 图表，可邮件分享） |
| `scores.json` | 单 case + 汇总分数 |
| `failures.json` | 失败归因（F1-F7） |
| `charts.json` | 8 类图所需数据 |
| `traces.uatr.jsonl` | UATR 格式 trace |
| `case_details.csv` | 单 case 详情（便于 Excel 打开） |
| `patch_summary.md` | 本轮 patch 摘要（如有 A/B） |

## 11 节报告结构

### 1. Executive Summary（执行摘要）

领导/评审一眼看懂的页面。包含：

- 本轮评测规模（train / regression / adversarial 各多少条）
- 总体 Task Success 率
- 相比上一版（或 baseline）的提升幅度
- 最主要失败类型
- 是否有回归风险
- 建议：accept / reject / investigate

### 2. Evaluation Setup（评测配置）

- 被测 agent 名称、版本
- adapter 类型（mock / spring_ai_http）
- 评测时间、run_id
- case 集合来源
- 指标权重配置

### 3. Overall Scorecard（总体评分卡）

7 个核心指标的卡片视图：

| 指标 | baseline | candidate | delta |
|------|----------|-----------|-------|
| Task Success | 68.0% | 76.5% | +8.5pp |
| Tool Correctness | 72.4% | 84.1% | +11.7pp |
| Business Rule Coverage | 65.0% | 78.0% | +13.0pp |
| Output Schema Validity | 91.0% | 93.0% | +2.0pp |
| Evidence Faithfulness | 88.0% | 90.0% | +2.0pp |
| Latency p50 | 3100ms | 3220ms | +120ms |
| Token Cost | 1.2k | 1.3k | +8% |

### 4. Scenario-Level Results（场景维度结果）

按 case 的 `scenario` 字段分组（如果 case 没标 scenario，按 `name` 前缀分组）。展示每个场景的通过率和主要失败类型。

### 5. Metric-Level Results（指标维度结果）

每个指标的详细分析：分布、最差 case、最好 case、与上版对比。

### 6. Tool / Workflow Trace Analysis（工具与流程分析）

- Required tool recall 明细（哪些工具最常被漏调）
- Forbidden tool violation 明细
- Tool call 顺序分析
- Workflow 步骤数分布
- 重复调用统计

### 7. Failure Taxonomy（失败归因）

按 F1-F7 分类统计，附 Pareto 图数据。每类失败列出代表 case。

### 8. Iteration and Patch History（迭代与 patch 历史）

如果是 A/B 报告，展示：

- baseline → candidate_001 → candidate_002 → ... 的分数曲线
- 每个 patch 的 impact matrix（对哪些指标有提升 / 退化）
- accept / reject 决策记录

### 9. Regression Risk（回归风险）

- regression split 上的硬失败数
- 新增失败 case 列表
- 与上一版的 case 级别 delta

### 10. Recommendations（建议）

基于以上分析给出 3-5 条具体建议，每条建议包含：

- 建议内容
- 预期影响（修哪类失败）
- 风险等级
- 建议优先级

### 11. Appendix: Case Details（附录：单 case 详情）

每条 case 一行：case_id / scenario / status / score / hard_fail / top_failure_type / trace_timeline_link。

## 8 类图表

`charts.json` 包含 8 类图的数据，HTML 报告用内联 SVG 渲染：

### 8.1 Overall Scorecard（指标卡片）

横向条形图，每个指标一行，baseline vs candidate 对比。

### 8.2 Scenario Bar Chart（场景柱状图）

每个场景一根柱子，高度 = 通过率。

### 8.3 Case × Metric Heatmap（热力图）

行 = case，列 = metric，颜色 = 分数（红→黄→绿）。

### 8.4 Failure Pareto（失败 Pareto 图）

按失败类型数量降序的柱状图 + 累计百分比折线。

### 8.5 Trace Timeline（trace 时间线）

单条 case 的执行时间线，横轴 = step，每步一个色块（不同 event_type 不同颜色）。

### 8.6 Tool Call Graph（工具调用图）

节点 = 工具，边 = 调用顺序，边的粗细 = 调用次数。

### 8.7 Iteration Curve（迭代曲线）

横轴 = 迭代版本，纵轴 = 分数 / 成功率 / 硬失败数。

### 8.8 Patch Impact Matrix（patch 影响矩阵）

行 = patch，列 = 指标 delta，颜色 = 正向(绿) / 负向(红)。

## HTML 报告设计原则

1. **单文件**：所有 CSS / SVG / 数据内联，不依赖外部资源，可邮件分享。
2. **打印友好**：用 `@media print` 优化打印样式，A4 纸能完整打印。
3. **响应式**：桌面 / 平板 / 手机都能读。
4. **无 JS 交互**（v0.5）：纯静态，所有图表用 SVG。v1 再加交互。
5. **配色**：专业蓝灰主色 + 语义色（绿=pass / 红=fail / 黄=warning）。
6. **可访问性**：图表有 `<title>`，颜色不只是红绿（加形状/标签区分）。
