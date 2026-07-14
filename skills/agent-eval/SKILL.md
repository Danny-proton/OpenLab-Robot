---
name: agent-eval
description: Agent 评测与优化。当用户要测试、诊断、优化、A/B 验证、对比 Agent 行为、工具调用、工作流质量、业务规则合规、输出格式、skill 触发时使用。覆盖 OpenLab Robot (cc-haha) / Claude Code skill / Spring AI agent。支持 F1-F8 失败归因、HRPO 层次化根因、reference 自动注入、auto_patcher 全自动优化。即使用户只提一个组件（如"工具调用错了"）也触发，因为框架把 prompt/tool schema/tool policy/workflow/memory/skill 作为独立优化目标。
allowed-tools: Bash(python *), Bash(python3 *), Bash(git *), Bash(ls *), Bash(cat *), Bash(mkdir *), Bash(cp *), Bash(mv *), Bash(diff *), Bash(wc *), Bash(head *), Bash(tail *), Read, Write, Edit, Grep, Glob, AskUserQuestion
---

# Agent 评测与优化 Skill

你的职责是**评测并改进一个 Agent 系统**，不是只改 prompt。

## 轻量版说明

这是**轻量 skill 嵌套版**——无 MCP server、无 hooks，所有能力通过 Bash 直接调 Python 脚本实现。

**目录结构**（skill 嵌套）：
```
agent-eval/                    ← skill 根目录
├── SKILL.md                   ← 本文件
├── scripts/                   ← Python 脚本（直接 Bash 调）
│   ├── common.py
│   ├── eval_runner.py
│   ├── diagnoser.py
│   ├── multi_judge.py
│   ├── opik_adapter.py
│   ├── reference_optimizer.py
│   ├── auto_patcher.py
│   ├── html_report.py
│   ├── dashboard.py
│   ├── ci_regression.py
│   ├── ask_setup.py
│   └── adapters/
│       ├── openlab_robot_adapter.py
│       └── ...
├── agents/                    ← 9 个评审 Agent（Claude 自动委托）
├── guides/                    ← 15 篇文档
├── templates/                 ← 报告模板
└── examples/.agent-eval/      ← 示例配置（scaffold 时复制）
```

## 工作循环

1. **启动前**：跑 `ask_setup.py --emit-questions` 收集缺失信息，用 AskUserQuestion 问用户
2. **跑基线**：`python scripts/eval_runner.py --config .agent-eval/config.yaml --split train --variant baseline`
3. **诊断**：`python scripts/diagnoser.py --config .agent-eval/config.yaml --latest`
4. **多 Judge 评审**：`python scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id>`
5. **HRPO 分析**：`python scripts/opik_adapter.py --config .agent-eval/config.yaml --run <run_id> --optimizer hrpo`
6. **生成 reference**：`python scripts/reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply`
7. **A/B + 全自动**：`python scripts/auto_patcher.py --config .agent-eval/config.yaml --baseline-run <run_id> --split regression --auto-apply`
8. **生成报告**：`python scripts/html_report.py --config .agent-eval/config.yaml --run <run_id>`
9. **生成 Dashboard**：`python scripts/dashboard.py --config .agent-eval/config.yaml`

## 命令速查

所有脚本在 `${CLAUDE_SKILL_DIR}/scripts/` 下。

### 0. 启动前信息收集（首次必跑）

```bash
# 输出待问问题 JSON，供 AskUserQuestion 用
python ${CLAUDE_SKILL_DIR}/scripts/ask_setup.py --stage startup --config .agent-eval/config.yaml --emit-questions
```

5 个环节：startup / eval / judge / optimize / abtest，详见 `guides/15_setup_wizard.md`。

### 1. 首次初始化

```bash
python ${CLAUDE_SKILL_DIR}/scripts/eval_runner.py --scaffold .
```

### 2. 跑基线评测

```bash
python ${CLAUDE_SKILL_DIR}/scripts/eval_runner.py \
  --config .agent-eval/config.yaml \
  --split train \
  --variant baseline \
  --label <短标签>
```

输出：`runs/<run_id>.jsonl` + `traces/<run_id>.jsonl` + `scores/<run_id>.json` + `reports/<run_id>.html` + `scores/<run_id>.charts.json`

### 3. 诊断失败（F1-F8）

```bash
python ${CLAUDE_SKILL_DIR}/scripts/diagnoser.py \
  --config .agent-eval/config.yaml --latest
```

### 4. 多 Judge 评审

```bash
python ${CLAUDE_SKILL_DIR}/scripts/multi_judge.py \
  --config .agent-eval/config.yaml --run <run_id> --split train
```

### 5. HRPO 层次化根因分析

```bash
python ${CLAUDE_SKILL_DIR}/scripts/opik_adapter.py \
  --config .agent-eval/config.yaml --run <run_id> --optimizer hrpo
```

### 6. 生成并注入 reference

```bash
python ${CLAUDE_SKILL_DIR}/scripts/reference_optimizer.py \
  --config .agent-eval/config.yaml --run <run_id> --apply
```

### 7. 全自动优化循环

```bash
python ${CLAUDE_SKILL_DIR}/scripts/auto_patcher.py \
  --config .agent-eval/config.yaml \
  --baseline-run <baseline_run_id> \
  --split regression \
  --auto-apply
```

### 8. 生成 HTML 报告

```bash
python ${CLAUDE_SKILL_DIR}/scripts/html_report.py \
  --config .agent-eval/config.yaml --run <run_id> --split train
```

### 9. 生成 Dashboard

```bash
python ${CLAUDE_SKILL_DIR}/scripts/dashboard.py \
  --config .agent-eval/config.yaml
```

### 10. CI 持续回归

```bash
python ${CLAUDE_SKILL_DIR}/scripts/ci_regression.py \
  --config .agent-eval/config.yaml --ci
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

- `mock` — 内置，无需后端
- `spring_ai_http` — Spring AI agent HTTP 调用
- `openlab_robot` — OpenLab Robot (cc-haha) subprocess 调用

## 评审 Agent（9 个，自动委托）

Claude 根据 `agents/*.md` 的 description 自动委托：

- 6 个规则型 Judge：domain / tool-trace / workflow / faithfulness / regression / safety
- 3 个决策型：gatekeeper / optimizer-planner / patch-writer

## 重要规则

- **默认绝不能只改 system prompt**。Prompt / tool schema / tool policy / workflow / memory / skill 要分开考虑
- **接受规则是机械的**：train 提升 ≥0.03 + regression 零硬失败 + 零 forbidden tool + 无新失败 + latency 不超 1.5x
- **必须记录证据**：每条诊断引用 case_id + trace_id + event
- **patch 越小越好**
- **SafetyJudge veto 强制**

## 文档

所有 guide 在 `guides/` 目录（15 篇）。
