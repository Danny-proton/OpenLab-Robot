# Agent Eval Skill 版本历史

## v1.1.0 (2026-07-16) — 用例自优化版【V1.1 本次发布】

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
