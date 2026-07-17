# Agent Eval Skill 版本历史

## v1.1.2 (2026-07-17) — 合并 dev-skill-eval 增量特性（标注 / 成本 / 采样 / SSE / xlsx）【本次合并】

把 Gitee `dev-skill-eval` 分支（`susu999xiaoxiao/OpenLab-Robot`）相对主线的**纯增量**特性合并进 v1.1，**不改动 v1.1 任何既有文件逻辑**，只新增文件 + 追加文档。合并后 v1.1 同时具备「用例自优化」+「人工标注校准」+「成本/Span 追踪」+「分层采样」能力。

### 新增脚本（6 个，全部零 LLM，直接复用 v1.1 的 `common.py`）

- `scripts/annotate_server.py` — 标注 Web 服务（HTTP，`templates/annotate.html`）
- `scripts/annotator.py` — 标注数据管理（load / validate / stats / export）
- `scripts/cost_tracker.py` — Span 管理 + 成本追踪（build-spans / report，按 case/tool/dimension/time/iteration 聚合）
- `scripts/sse_stream.py` — SSE 流式推送服务
- `scripts/stratified_sampler.py` — 分层采样（时间窗口 + 申请类型 + 风险等级 + 地区/分行，proportional/equal/weighted）
- `scripts/xlsx_importer.py` — Excel 导入/导出（用例导入 + 标注模板导出 + 标注结果导入）

### 新增评审 Agent（1 个）

- `agents/annotation-judge.md` — 标注判定辅助（校准、推断、建议），用于人工标注与自动评分对齐

### 新增模板（2 个，`templates/`）

- `templates/annotate.html` — Web 标注页面
- `templates/cost_report.html` — 成本报表页面

### 新增指标（7 个，`examples/.agent-eval/metrics/`）

- 业务价值（bv_）：`bv_customer_experience` / `bv_decision_accuracy` / `bv_sop_completeness` / `bv_terminology_accuracy`
- 性能效率（pe_）：`pe_token_consumption` / `pe_tool_efficiency`
- 风险控制（rc_）：`rc_risk_classification`

### 合并原则

- v1.1 的 `common.py`（794 行，含 8-mode `mock_config` + legacy 兼容）是 dev-skill-eval `common.py`（733 行，仅 legacy）的**超集** → 直接复用，零修改
- 6 个新增脚本 `import common as C` 全部通过 v1.1 超集 common.py，`--help` 与功能验证均通过
- 不覆盖 v1.1 任何既有文件，仅追加本节文档

## v1.1.1 (2026-07-17) — 报告统一管理 + 进度埋点 + 可视化重构

在 v1.1.0 基础上完成"报告统一管理 + 执行流程进度管理 + 可视化深度优化"三件事。**不改变评测逻辑，只增强可观测性与报告呈现**。

### 核心新增 1：报告统一门户（report_portal.py）

一个自包含 HTML 门户，把散落在 `.agent-eval/` 各处的报告/进度/迭代/质量分聚合到**同一个网站**的 5 个页面：

- **Overview** — 6 张 KPI 卡片 + run 分数 sparkline + 最近报告表
- **Reports** — 报告卡片网格 + 客户端搜索/类型筛选/预览展开
- **Progress** — 9 步进度环 + 水平时间线（每步 tooltip 含耗时）+ 平均耗时条形图 + session 表
- **Iterations** — 质量分趋势 sparkline + 迭代卡片（before/after 对比）
- **Quality** — 12 维雷达图 + 加权总分条 + 低分维度告警 + 维度详情卡

**设计语言**：深色玻璃态（`backdrop-filter: blur(12px)` + slate-900 基底 + `linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)` 渐变高亮）+ 鼠标悬浮动效（`translateY(-4px)` + `box-shadow: 0 12px 32px rgba(99,102,241,.25)` + 左侧色条 `::before` 渐显）。

### 核心新增 2：进度埋点（progress_tracker.py + sidecar 改造）

- **`progress_tracker.py`**（新）：进度事件持久化层。`emit()` 追加写 `progress.jsonl`，`timeline()` 按 session_id 聚合并计算每步 `duration_ms`，`summary()` 给出总事件数/sessions/各步平均耗时。
- **`sidecar.py` 改造**：向后兼容。原本只 emit JSON 到 stdout，现在同时通过 `progress_tracker.emit()` 持久化。session_id 自动续接（同一次评测运行的多个 step 共享一个 session_id），无需用户改调用方式。

### 核心新增 3：可视化重构（深色玻璃态 + SVG 图表 + 悬浮动效）

三处报告生成器统一升级到与门户一致的设计语言：

| 脚本 | 升级内容 |
|------|---------|
| `generate_report.py` | + 3 张 SVG 图表（维度通过率横向条形 / 优先级堆叠柱 / 响应时间分布）+ 修复 `output_path` 未定义 bug + 全量 HTML escape |
| `case_iteration_report.py` | + 3 张 SVG 图表（质量分前后对比条形 / 错误分布 Pareto + 累计百分比 / Mutation kill 热力图）+ 复用 `PORTAL_CSS` 保证视觉一致 |
| `report_portal.py` | 内置 SVG 工具集：进度环 / sparkline / 12 维雷达 / KPI 卡 / 时间线，全部带 `<title>` tooltip |

所有图表带 `<title>` 原生 tooltip（鼠标悬浮显示数值），关键卡片带 `:hover` 升起动效。

### 新增脚本（2 个，全部零 LLM）

- `progress_tracker.py` — 进度事件持久化 + timeline 聚合 + summary 统计
- `report_portal.py` — 统一门户生成器（5 页 + SVG 图表 + 客户端 JS 筛选）

### 新增文档

- `docs/PRD_REPORT_PORTAL.md` — 门户 + 进度埋点 PRD（含验收标准 §8）
- `docs/PRD_ORCHESTRATION.md` 更新 — 阶段 9 生成门户 + 进度埋点章节

### 端到端验证

- `sidecar.py` → `progress_tracker.py` pipeline：3 个 step 事件 session_id 续接正确，timeline 正确计算 duration_ms=11000ms
- `report_portal.py`：44KB 门户 HTML，5 页全部有数据（8 报告 / 1 session / 1 迭代 / 12 维质量分）
- `generate_report.py`：31KB HTML，3 张 SVG 图表 + 9 tooltip + 8 hover 规则，`output_path` bug 已修复
- `case_iteration_report.py`：41KB HTML，3 张 SVG 图表 + 51 tooltip，深色玻璃态与门户一致

### 设计原则强化

- **统一设计语言**：门户/4阶段报告/迭代报告共享同一套深色玻璃态 CSS（`PORTAL_CSS` 常量复用）
- **进度可观测**：9 步评测流程每步都有 running/completed/failed 状态持久化，门户实时聚合
- **零外部依赖**：所有 SVG 图表手写，无 Chart.js / D3，单 HTML 文件可邮件分享

## v1.1.0 (2026-07-16) — 用例自优化版

**业界空白能力**。在 v2.3.0-mobile-bank 基础上演进，聚焦**用例自优化**（test-case self-optimization）。
业界只有 prompt 自优化（改被测 Agent），本版本首次实现 test-case 自优化（改测试本身）。

### 核心新增：用例自优化闭环

完成一轮评测后自动迭代测试用例集，使下一轮测试的覆盖度和有效率提升：

- **错误分布分析**：从 F1-F8 诊断识别集中类型（占比>40% 或 ≥3 条）
- **Spec 缺口识别**：维度缺口/工具缺口/DFX缺口/过简单维度
- **12 维质量评分**：9 标准 + 3 Agent 专属（工具/工作流/记忆覆盖率）
- **Mutation kill matrix**：6 类变异（漏调/重复/参数错/空结果/幻觉/冗余），参考 Meta ACH
- **增强建议生成**：add/modify/deprecate/spec_changes 四类建议
- **迭代报告**：MD + HTML，含质量分前后对比 + mutation 检出率

### 新增脚本（5 个，全部零 LLM）

- `case_io.py` — cases YAML 读写，保留完整 canonical schema（expected_tools/business_rules/expected_steps/scoring + V1.1 test_level/category/lifecycle/dimension_id/mock_config）
- `case_quality_checker.py` — 12 维确定性质量评分
- `case_optimizer.py` — 用例自优化核心（错误分布+缺口+建议+apply）
- `mutation_generator.py` — 变异生成 + kill matrix
- `case_iteration_report.py` — 迭代报告 MD + HTML

### 新增子 skill

- `skills/test-case-self-optimization/SKILL.md` — 阶段 4.5 用例自优化编排（含 AskUserQuestion 交互指示）

### 吸收 test-design-agent-raw 成熟设计

- `requirements-analysis` 子 skill 扩展：UC 15 字段块 + testspec 4 表（测试对象/操作/数据/关系）
- `test-case-generator` 子 skill 扩展：7 测试方法库 + 20 项自检（16 成熟 + 4 Agent 专属）+ 五层断言 schema

### mock 系统扩展

- `common.py` 的 `_call_mock` 支持 `mock_config.mode` 配置 8 种失败触发：
  skip_tool / repeat_tool / wrong_param / empty_result / hallucinate / redundant / no_memory / success
- `examples/.agent-eval/cases/train.yaml` 扩展到 8 条用例，覆盖所有自优化触发点

### 新增文档

- `docs/DELTA_GENERAL_TO_AGENT.md` — 通用测试转 Agent 评测的新增点分析（20 个新增点）
- `docs/PRD_REQUIREMENT_TESTDESIGN.md` — 需求分析与测试设计流程（吸收成熟设计）
- `docs/PRD_MOCK_SYSTEM.md` — mock 系统设计
- `docs/PRD_CASE_SELF_OPTIMIZATION.md` — 用例自优化详细设计（重写）
- `docs/DESIGN_OVERVIEW.md` — 设计总纲（V1.1 更新）
- `guides/17_case_self_optimization.md` — 用例自优化指南

### 端到端验证

mock 系统测试结果：8 条用例 → 诊断 14 条（F3.1/F4.4/F5.3/F6.1/F7.3/F7.4/F8.1/F8.2/F8.4）→
质量分 0.88 → 0.99（apply 后）→ mutation 检出率 42% → 新增 9 条用例填补缺口。

### 双闭环架构

```
一轮评测
  ↓
[阶段 5-7] prompt 自优化（改被测 Agent）—— reference_optimizer + auto_patcher
  ↓
[阶段 4.5] 用例自优化（改测试本身）—— case_optimizer + mutation_generator  ← V1.1 新增
  ↓
重跑评测 → Agent 越来越准，测试越来越全
```

### 保留（v2.3.0 原样）

- 4 阶段流水线 + excel_to_uatr 桥接器
- 9 个评审 Agent + F1-F8 失败归因 + HRPO 根因
- reference 注入 + auto_patcher A/B 优化
- ask_setup 向导 + SideCar + memory_kb + 报告管理 + Dashboard + CI 回归
- 3 个 adapter（mock/spring_ai_http/openlab_robot）

## v2.3.0-mobile-bank (2026-07-15)

**架构修正版**。在 v2.2.0 基础上修正两个核心架构问题，演进而非重写主分支能力。

### 修正的问题

1. **脚本零 LLM**：v2.2.0 的 `generate_requirements.py` / `generate_testcases.py` 内嵌 `LLM_BASE_URL`（默认 OpenAI）+ `requests.post` 调外部 LLM，强耦合运行环境。v2.3.0 把这两脚本的 LLM 调用全部剥离，只保留 JSON → Excel 机械写入 + list + read。
2. **prompt 移入子 skill**：v2.2.0 的 prompt 工程全埋在脚本里。v2.3.0 把完整 prompt 文字移到 `skills/requirements-analysis/SKILL.md` 和 `skills/test-case-generator/SKILL.md`，Agent 自己读、自己生成 JSON，或用 Task 工具委派/并行委派给子 agent。
3. **桥接而非平行**：v2.2.0 把 diagnoser/multi_judge/optimizer 列为"阶段 5-7"但没接上。v2.3.0 新增 `excel_to_uatr.py` 桥接器，把 4 阶段 Excel 产出翻译成 UATR trace + cases YAML + scores，**接回**主分支 eval loop。

### 新增

- `scripts/excel_to_uatr.py` — Excel → UATR trace + cases YAML + runs + scores 桥接器（零 LLM）
- `guides/16_mobile_bank_pipeline.md` — 4 阶段流水线 + 桥接指南
- 5 个子 skill 全部重写：prompt 文字 + Task 工具指示（替代 v2.2.0 的薄壳）

### 保留（主分支原封不动）

- 9 个评审 Agent（`agents/*.md`）
- F1-F8 失败归因 + HRPO 根因 + reference 注入 + auto_patcher
- 3 个 adapter（mock / spring_ai_http / openlab_robot）
- ask_setup 向导 + SideCar + memory_kb + 报告管理 + Dashboard + CI 回归
- `execute_testcases.py`（纯 HTTP 执行器）+ `generate_report.py`（纯报告渲染器）原样保留

### 架构

大 skill（`SKILL.md` 编排入口）套小 skill（`skills/*/SKILL.md` 每阶段 prompt + Task 指示）套 script（`scripts/*.py` 零 LLM 机械 I/O）三层结构。

## v2.2.0-mobile-bank (2026-07-15)

手机银行定制版本。基于 agent-eval v2.1.0，增加四阶段流水线：

- 阶段1: 需求分析（generate_requirements.py → Excel）
- 阶段2: 用例生成（generate_testcases.py → Excel）
- 阶段3: 用例执行（execute_testcases.py → Excel）
- 阶段4: 报告生成（generate_report.py → HTML+MD）

保留原始 Excel 输入输出格式，结合 agent-eval 的 F1-F8 诊断/HRPO/reference/auto_patcher 能力。
大 skill 套小 skill 结构：5 个子 skill 对应各阶段。

> ⚠️ 已知问题（v2.3.0 修正）：脚本内嵌 LLM URL、prompt 埋在脚本里、4 阶段流水线与 eval loop 未桥接。

## v2.1.0 (2026-07-14)

基于用户提供的增强版同步，新增 5 个脚本：
- memory_kb.py / pdf_report.py / report_manager.py / sidecar.py / tracer_scorer.py

## v2.0.0 (2026-07-14)

标准 plugin 重构 + agent 符合官方 frontmatter 标准 + trace 调用结构 + Dashboard 修复。

## v1.1.0

F8 执行冗余失败 + HRPO 层次化根因 + reference 自动注入 + auto_patcher。

## v1.0.0

多评审 Agent + DeepEval/Opik adapter + Dashboard + CI 回归。

## v0.5.0

UATR trace 中间层 + 专业 HTML 报告。

## v0.1.0

本地评测闭环（F1-F7 失败归因 + 5 硬指标 + A/B + patch）。
