---
name: agent-eval
description: "手机银行 Agent 评测与优化。基于 agent-eval 主 skill，增加手机银行定制四阶段流水线：需求分析→用例生成→用例执行→报告生成。保留原始 Excel 输入输出格式。结合 agent-eval 的 F1-F8 失败归因、HRPO 根因分析、reference 自动注入、auto_patcher 优化能力。触发词：手机银行测试, agent 评测, 用例生成, 测试执行, 测试报告, mobile bank test, agent evaluation, 需求分析, 测试用例, 自动化测试。"
allowed-tools: Bash(python *), Bash(python3 *), Bash(git *), Bash(ls *), Bash(cat *), Bash(mkdir *), Bash(cp *), Bash(mv *), Bash(diff *), Bash(wc *), Bash(head *), Bash(tail *), Read, Write, Edit, Grep, Glob, Task, AskUserQuestion
---

# 手机银行 Agent 评测与优化 Skill

基于 agent-eval 主 skill 的手机银行定制版本。保留原始四阶段流水线（Excel 输入输出），结合 agent-eval 的诊断/优化能力。

## 目录结构

```
agent-eval/
├── SKILL.md                        ← 本文件（手机银行定制版）
├── VERSION.md                      ← 版本信息
├── scripts/                        ← 脚本
│   ├── generate_requirements.py    ← 阶段1: 需求分析（原始，Excel输出）
│   ├── generate_testcases.py       ← 阶段2: 用例生成（原始，Excel输出）
│   ├── execute_testcases.py        ← 阶段3: 用例执行（原始，Excel输出）
│   ├── generate_report.py          ← 阶段4: 报告生成（原始，HTML+MD输出）
│   ├── eval_runner.py              ← agent-eval 通用执行器
│   ├── diagnoser.py                ← F1-F8 失败归因
│   ├── multi_judge.py              ← 多 Judge 评审
│   ├── opik_adapter.py             ← HRPO 层次化根因
│   ├── reference_optimizer.py      ← reference 自动注入
│   ├── auto_patcher.py             ← 全自动优化循环
│   ├── html_report.py              ← agent-eval HTML 报告
│   ├── dashboard.py                ← 交互式 Dashboard
│   ├── ci_regression.py            ← CI 持续回归
│   ├── ...                         ← 其余通用脚本
│   └── adapters/                   ← 执行器适配器
├── skills/                         ← 子 skill（大skill套小skill）
│   ├── orchestrator/               ← 编排子skill
│   ├── requirements-analysis/      ← 需求分析子skill
│   ├── test-case-generator/        ← 用例生成子skill
│   ├── test-executor/              ← 用例执行子skill
│   └── test-reporter/              ← 报告生成子skill
├── agents/                         ← 9 个评审 agent
├── guides/                         ← 15 篇文档
├── docs/                           ← PRD/设计文档
├── data/                           ← 运行产物（Excel/HTML/MD）
└── examples/.agent-eval/           ← 示例配置
```

## 完整工作流程

### 阶段 1: 需求分析

**做什么**：从用户需求文本，生成 10 个测试维度和场景，输出到 Excel。

**脚本**：`generate_requirements.py`（保留原始，脚本内部集成 LLM 调用）

```bash
python ${SKILL_DIR}/scripts/generate_requirements.py \
  --description "用户的需求文本" \
  --output ${SKILL_DIR}/data/requirements_analysis.xlsx
```

**输入**：需求描述文本（多行用 `\n` 分隔）
**输出**：`data/requirements_analysis.xlsx`（3 个 sheet：测试维度/测试场景/Skill归属建议）
**子 skill**：`skills/requirements-analysis/`

列出维度：
```bash
python ${SKILL_DIR}/scripts/generate_requirements.py \
  --list ${SKILL_DIR}/data/requirements_analysis.xlsx
```

### 阶段 2: 测试用例生成

**做什么**：根据需求分析 Excel，为每个场景生成详细测试用例，输出到 Excel。

**脚本**：`generate_testcases.py`（保留原始，脚本内部集成 LLM 调用）

```bash
python ${SKILL_DIR}/scripts/generate_testcases.py \
  --input ${SKILL_DIR}/data/requirements_analysis.xlsx \
  --output ${SKILL_DIR}/data/test_cases.xlsx \
  --per-scenario 3
```

**输入**：requirements_analysis.xlsx
**输出**：`data/test_cases.xlsx`（用例ID/场景ID/维度ID/标题/优先级/前置条件/步骤/用户输入/预期结果/断言类型）
**子 skill**：`skills/test-case-generator/`

可选参数：`--dimensions DIM-001,DIM-002`（指定维度）、`--list`（列出维度）

### 阶段 3: 测试用例执行

**做什么**：读取测试用例 Excel，根据环境信息执行 HTTP 请求，收集响应和指标。

**脚本**：`execute_testcases.py`（保留原始）

```bash
python ${SKILL_DIR}/scripts/execute_testcases.py \
  --input ${SKILL_DIR}/data/test_cases.xlsx \
  --output ${SKILL_DIR}/data/execution_results.xlsx \
  --base-url "http://localhost:8080/api/chat" \
  --method POST \
  --timeout 120 \
  --headers '{"Content-Type":"application/json"}' \
  --body '{"messages":[{"role":"user","content":"{{用户输入}}"}]}'
```

**输入**：test_cases.xlsx + 环境信息（URL/headers/body）
**输出**：`data/execution_results.xlsx`（用例ID/状态码/响应时间/实际响应/结果）
**子 skill**：`skills/test-executor/`

支持 `--stream`（SSE 流式）、`--cases TC-0001,TC-0002`（指定用例）
`{{列名}}` 会被替换为用例 Excel 中对应列的内容

### 阶段 4: 报告生成

**做什么**：读取需求分析、测试用例、执行结果三个 Excel，生成 Markdown 和 HTML 报告。

**脚本**：`generate_report.py`（保留原始）

```bash
python ${SKILL_DIR}/scripts/generate_report.py \
  --requirements ${SKILL_DIR}/data/requirements_analysis.xlsx \
  --testcases ${SKILL_DIR}/data/test_cases.xlsx \
  --results ${SKILL_DIR}/data/execution_results.xlsx \
  --output ${SKILL_DIR}/data/test_report.html
```

**输入**：3 个 Excel
**输出**：`data/test_report.html` + `data/test_report.md`（同时生成双格式）
**子 skill**：`skills/test-reporter/`

### 阶段 5: 诊断失败（agent-eval 能力）

**做什么**：对执行结果做 F1-F8 失败归因。

```bash
python ${SKILL_DIR}/scripts/diagnoser.py \
  --config .agent-eval/config.yaml --latest
```

**文档**：`guides/04_failure_taxonomy.md`

### 阶段 6: 多 Judge 评审（agent-eval 能力）

```bash
python ${SKILL_DIR}/scripts/multi_judge.py \
  --config .agent-eval/config.yaml --run <run_id> --split train
```

### 阶段 7: 优化迭代（agent-eval 能力）

```bash
# HRPO 根因分析
python ${SKILL_DIR}/scripts/opik_adapter.py \
  --config .agent-eval/config.yaml --run <run_id> --optimizer hrpo

# reference 注入
python ${SKILL_DIR}/scripts/reference_optimizer.py \
  --config .agent-eval/config.yaml --run <run_id> --apply

# 全自动 A/B
python ${SKILL_DIR}/scripts/auto_patcher.py \
  --config .agent-eval/config.yaml \
  --baseline-run <run_id> --split regression --auto-apply
```

### 阶段 8: 迭代报告

回到阶段 1-2，根据 F1-F8 错误分布增强用例，重跑评测，对比质量提升。

## 子 skill 说明

大 skill 套小 skill，子 skill 用文字说明让 Agent 调用对应脚本：

| 子 skill | 对应阶段 | 调用脚本 |
|---------|---------|---------|
| orchestrator | 编排 | 按顺序调用各阶段 |
| requirements-analysis | 阶段1 | generate_requirements.py |
| test-case-generator | 阶段2 | generate_testcases.py |
| test-executor | 阶段3 | execute_testcases.py |
| test-reporter | 阶段4 | generate_report.py |

## 环境变量

脚本内部集成 LLM 调用，需要配置：
- `LLM_API_KEY`: LLM API key
- `LLM_MODEL`: 模型名（默认 gpt-4o）
- `LLM_BASE_URL`: API 地址（默认 OpenAI）

## 失败类型 F1-F8

| 代码 | 名称 | 修改对象 |
|------|------|---------|
| F1 | Skill 触发失败 | SKILL.md description |
| F2 | 任务理解失败 | prompt |
| F3 | 工具选择失败 | tool schema + policy |
| F4 | 工具参数失败 | tool schema + memory |
| F5 | Workflow 失败 | advisor 链 |
| F6 | Memory 失败 | memory + prompt |
| F7 | 输出失败 | prompt + memory |
| F8 | 执行冗余失败 | reference |

## 文档

| 文档 | 说明 |
|------|------|
| `guides/01-15` | 15 篇技术指南 |
| `docs/DESIGN_OVERVIEW.md` | 设计总纲 |
| `docs/PRD_TEST_DESIGN.md` | 测试设计 PRD |
| `docs/PRD_CASE_SELF_OPTIMIZATION.md` | 用例自优化 PRD |
| `docs/PRD_ORCHESTRATION.md` | 总流程管控 PRD |
| `docs/ADAPTER_SPEC.md` | 适配器接口规范 |
| `docs/RESEARCH_REPORT.md` | 业界调研报告 |
