# Agent Eval Skill 版本历史

## v2.1.0 (2026-07-14)

基于用户提供的 `agent_eval_skill_main.zip` 增强版同步，新增 5 个脚本：

- `memory_kb.py` — KnowledgeCycle 记忆系统（.agent-eval/.memory/ 读写，兼容 Claude Code memory）
- `pdf_report.py` — PDF 报告生成器（weasyprint HTML→PDF）
- `report_manager.py` — 报告 CRUD 管理器（list/get/search/update/delete/reindex）
- `sidecar.py` — 评测进度状态面板（标准化 JSON，Claude Code 渲染进度卡片）
- `tracer_scorer.py` — TRACE 五维评测引擎（Trust/Reliability/Adaptability/Convention/Effectiveness）

同时包含用户对 SKILL.md / agents / scripts / guides 的所有增强修改。

## v2.0.0 (2026-07-14)

Claude Code 标准 plugin 重构 + agent 符合官方 frontmatter 标准 + trace 调用结构 + Dashboard 修复。

## v1.1.0

F8 执行冗余失败 + HRPO 层次化根因 + reference 自动注入 + auto_patcher。

## v1.0.0

多评审 Agent + DeepEval/Opik adapter + Dashboard + CI 回归。

## v0.5.0

UATR trace 中间层 + 专业 HTML 报告。

## v0.1.0

本地评测闭环（F1-F7 失败归因 + 5 硬指标 + A/B + patch）。
