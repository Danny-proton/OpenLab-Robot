# Agent Eval Skill 版本历史

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
