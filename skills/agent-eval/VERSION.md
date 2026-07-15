# Agent Eval Skill 版本历史

## v2.2.0-mobile-bank (2026-07-15)

手机银行定制版本。基于 agent-eval v2.1.0，增加四阶段流水线：

- 阶段1: 需求分析（generate_requirements.py → Excel）
- 阶段2: 用例生成（generate_testcases.py → Excel）
- 阶段3: 用例执行（execute_testcases.py → Excel）
- 阶段4: 报告生成（generate_report.py → HTML+MD）

保留原始 Excel 输入输出格式，结合 agent-eval 的 F1-F8 诊断/HRPO/reference/auto_patcher 能力。
大 skill 套小 skill 结构：5 个子 skill 对应各阶段。

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
