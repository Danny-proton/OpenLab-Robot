---
name: agent-eval
description: Agent 评测与优化。当用户要测试、诊断、优化、A/B 验证、对比 Agent 行为、工具调用、工作流质量、业务规则合规、输出格式、skill 触发时使用。覆盖 OpenLab Robot (cc-haha) / Spring AI agent / 任意 HTTP agent。支持需求分析、用例生成、用例自优化、F1-F8 失败归因、HRPO 层次化根因、reference 自动注入、auto_patcher 全自动优化。即使用户只提一个组件也触发，因为框架把 prompt/tool schema/tool policy/workflow/memory/skill 作为独立优化目标。
allowed-tools: Bash(python *), Bash(python3 *), Bash(git *), Bash(ls *), Bash(cat *), Bash(mkdir *), Bash(cp *), Bash(mv *), Bash(diff *), Bash(wc *), Bash(head *), Bash(tail *), Read, Write, Edit, Grep, Glob, Task, AskUserQuestion
---

# Agent 评测与优化 Skill

你的职责是**评测并改进一个 Agent 系统**，不是只改 prompt。

## 目录结构

```
agent-eval/
├── SKILL.md                   ← 本文件
├── scripts/                   ← Python 脚本
│   ├── common.py              ← 公共工具（adapter/trace/YAML）
│   ├── eval_runner.py         ← 执行器（跑 case → trace → scores）
│   ├── scorer.py              ← 评分（5硬+3软+TRACE五维）
│   ├── diagnoser.py           ← 失败归因 F1-F8
│   ├── multi_judge.py         ← 多 Judge 评审
│   ├── opik_adapter.py        ← HRPO 层次化根因
│   ├── reference_optimizer.py ← reference 自动注入
│   ├── auto_patcher.py        ← 全自动优化循环
│   ├── html_report.py         ← HTML 报告
│   ├── dashboard.py           ← 交互式 Dashboard
│   ├── ci_regression.py       ← CI 持续回归
│   ├── ask_setup.py           ← 信息收集向导
│   ├── case_io.py             ← YAML 用例读写
│   ├── excel_adapter.py       ← Excel→YAML 转换
│   ├── ...                    ← 其余脚本
│   └── adapters/              ← 执行器适配器
├── skills/                    ← 子 skill（Agent 自己生成用例）
│   ├── requirements-analysis/
│   ├── test-case-design/
│   └── test-case-self-optimization/
├── adapters/                  ← 子 skill 形式执行器（占位）
├── agents/                    ← 9 个评审 agent
├── guides/                    ← 15 篇文档
├── docs/                      ← PRD/设计文档
└── examples/.agent-eval/      ← 示例配置
```

## 完整工作流程（8 阶段）

### 阶段 0: 启动前信息收集

```bash
python ${SKILL_DIR}/scripts/ask_setup.py --stage startup --config .agent-eval/config.yaml --emit-questions
```

用 AskUserQuestion 问用户：adapter 类型 / API key / 路径 / 模型 / 权限 / 成本控制。详见 `guides/15_setup_wizard.md`。

首次初始化：
```bash
python ${SKILL_DIR}/scripts/eval_runner.py --scaffold .
```

### 阶段 1: 需求分析

**做什么**：从用户需求文本 / Agent PRD / SPEC，生成 10 个测试维度和场景。

**怎么做**：委托 `skills/requirements-analysis/` 子 skill。Agent 自己分析需求（通过 Task 工具，不在脚本里调 LLM），生成维度+场景 JSON，然后调脚本写文件：

```bash
# Agent 生成 JSON 后，调脚本写 YAML
python ${SKILL_DIR}/scripts/case_io.py write-requirements \
  --output .agent-eval/data/requirements.yaml \
  --json '{"dimensions":[...],"scenarios":[...]}'
```

**产物**：`.agent-eval/data/requirements.yaml`（10 维度 + 场景）
**文档**：`docs/PRD_TEST_DESIGN.md`

### 阶段 2: 用例设计

**做什么**：根据维度和场景，设计详细测试用例（含多轮/边界/异常）。

**怎么做**：委托 `skills/test-case-design/` 子 skill。Agent 自己设计用例，输出 agent-eval 格式的 case YAML：

```bash
# Agent 先读需求分析
python ${SKILL_DIR}/scripts/case_io.py read-requirements \
  --input .agent-eval/data/requirements.yaml

# Agent 设计完用例后，调脚本写 YAML
python ${SKILL_DIR}/scripts/case_io.py write-cases \
  --output .agent-eval/cases/train.yaml \
  --json '{"cases":[...]}'
```

**产物**：`.agent-eval/cases/train.yaml`（agent-eval 格式用例）
**文档**：`docs/PRD_TEST_DESIGN.md`

**Excel 输入适配**：如果用户有 Excel 格式用例，用适配器转换：
```bash
python ${SKILL_DIR}/scripts/excel_adapter.py \
  --input test_cases.xlsx --output .agent-eval/cases/train.yaml
```

### 阶段 3: 用例执行

**做什么**：执行测试用例，收集响应和 UATR trace。

**怎么做**：调 `eval_runner.py`，通过 adapter 执行（mock/http/openlab_robot）：

```bash
python ${SKILL_DIR}/scripts/eval_runner.py \
  --config .agent-eval/config.yaml \
  --split train \
  --variant baseline \
  --label <短标签>
```

**产物**：
- `.agent-eval/runs/<run_id>.jsonl` — 每条 case 执行记录
- `.agent-eval/traces/<run_id>.jsonl` — UATR trace（24 类事件，含调用结构）
- `.agent-eval/scores/<run_id>.json` — 分数（5硬+3软+TRACE五维）
- `.agent-eval/reports/<run_id>.md` — 基线报告

### 阶段 4: 诊断失败

**做什么**：对每条失败 case 做 F1-F8 归因。

```bash
python ${SKILL_DIR}/scripts/diagnoser.py \
  --config .agent-eval/config.yaml --latest
```

**产物**：`.agent-eval/reports/<run_id>_diagnosis.md` + `.json`
**文档**：`guides/04_failure_taxonomy.md`

### 阶段 5: 多 Judge 评审

**做什么**：6 个规则型 Judge + Gatekeeper 综合评审。

```bash
python ${SKILL_DIR}/scripts/multi_judge.py \
  --config .agent-eval/config.yaml --run <run_id> --split train
```

**产物**：`.agent-eval/reports/<run_id>_judges.md` + `.json`（含 Agreement Matrix）
**文档**：`guides/09_multi_judge.md`

### 阶段 6: 报告生成

**做什么**：生成 HTML + Markdown 报告（11 节 + 9 SVG 图表 + 调用结构树）。

```bash
python ${SKILL_DIR}/scripts/html_report.py \
  --config .agent-eval/config.yaml --run <run_id> --split train
```

可选 PDF：
```bash
python ${SKILL_DIR}/scripts/pdf_report.py \
  --config .agent-eval/config.yaml --run <run_id>
```

Dashboard：
```bash
python ${SKILL_DIR}/scripts/dashboard.py \
  --config .agent-eval/config.yaml
```

**产物**：`<run_id>.html` + `<run_id>.md` + `dashboard.html`

### 阶段 7: 优化迭代

**做什么**：HRPO 根因分析 → reference 注入 → A/B 验证 → accept/reject。

```bash
# 7a. HRPO 层次化根因分析
python ${SKILL_DIR}/scripts/opik_adapter.py \
  --config .agent-eval/config.yaml --run <run_id> --optimizer hrpo

# 7b. 生成并注入 reference
python ${SKILL_DIR}/scripts/reference_optimizer.py \
  --config .agent-eval/config.yaml --run <run_id> --apply

# 7c. 全自动 A/B（生成→apply→A/B→评审→accept(git commit)/reject(git checkout)）
python ${SKILL_DIR}/scripts/auto_patcher.py \
  --config .agent-eval/config.yaml \
  --baseline-run <run_id> \
  --split regression \
  --auto-apply
```

**产物**：reference 文件 + patch + A/B 报告 + git commit/checkout
**文档**：`guides/13_step_optimization.md`

### 阶段 8: 用例自优化 + 迭代报告

**做什么**：完成一轮测试后，分析错误分布，迭代增强用例。

**怎么做**：委托 `skills/test-case-self-optimization/` 子 skill。Agent 分析 F1-F8 错误分布，识别 spec 缺口和用例质量问题，生成增强建议，与人确认后更新 cases YAML。

```bash
# Agent 读诊断结果
python ${SKILL_DIR}/scripts/diagnoser.py \
  --config .agent-eval/config.yaml --latest

# Agent 分析错误分布，生成增强建议
# （子 skill 指导 Agent 自己分析，不在脚本里调 LLM）

# 确认后更新用例
python ${SKILL_DIR}/scripts/case_io.py write-cases \
  --output .agent-eval/cases/train.yaml \
  --json '{"cases":[...]}'
```

然后回到阶段 3 重跑评测，对比质量提升。

**产物**：更新后的 cases YAML + 迭代报告
**文档**：`docs/PRD_CASE_SELF_OPTIMIZATION.md`

## CI 持续回归

```bash
python ${SKILL_DIR}/scripts/ci_regression.py \
  --config .agent-eval/config.yaml --ci

# 标记 last_known_good
python ${SKILL_DIR}/scripts/ci_regression.py \
  --config .agent-eval/config.yaml --mark-good <run_id>
```

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
| **F8** | **执行冗余失败** | **reference（核心：缩短轮数）** |

## Adapter

| 适配器 | 类型 | 说明 |
|--------|------|------|
| mock | 内置 | 无需后端 |
| spring_ai_http | 内置 | Spring AI agent HTTP 调用 |
| openlab_robot | 内置 | OpenLab Robot (cc-haha) subprocess |
| cdp_web | 子 skill | CDP 网页执行（待实现） |
| script | 子 skill | 脚本执行（待实现） |
| api | 子 skill | API 执行（待实现） |

用例输入适配器：YAML（case_io.py）/ Excel（excel_adapter.py）
适配器规范：`docs/ADAPTER_SPEC.md`

## 评审 Agent（9 个，自动委托）

- 6 个规则型 Judge：domain / tool-trace / workflow / faithfulness / regression / safety
- 3 个决策型：gatekeeper / optimizer-planner / patch-writer

## 重要规则

- **用例生成由 Agent 完成**（通过 Task 工具），不在脚本里调 LLM
- **脚本只做确定性工作**：YAML IO / HTTP 执行 / 断言验证 / 报告渲染
- **默认绝不能只改 system prompt**，6 类组件分开考虑
- **接受规则是机械的**：train 提升 ≥0.03 + regression 零硬失败 + 零 forbidden + 无新失败 + latency 不超 1.5x
- **必须记录证据**：每条诊断引用 case_id + trace_id + event

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
