---
name: mobile-bank-agent-eval
description: "Use proactively when evaluating mobile banking agents. Incremental extension of agent-eval: adds automated test case generation via sub-skills (requirements analysis + test case design). Agent generates cases through Task tool. Scripts only do deterministic YAML IO. Reuses agent-eval for execution/scoring/diagnosis/report/optimization via path reference. Trigger: 手机银行测试, agent 评测, 用例生成, mobile bank test."
allowed-tools: Bash(python *), Bash(python3 *), Read, Write, Edit, Grep, Glob, Task, AskUserQuestion
---

# 手机银行 Agent 自动评测 Skill

**agent-eval 的增量扩展。** 只新增用例生成能力，其余复用 agent-eval。

## 架构（增量，不复制）

```
skills/
├── agent-eval/                         ← 主 skill（不改动，提供全部通用能力）
│   ├── scripts/                        ← 25 个通用脚本
│   ├── agents/                         ← 9 个评审 agent
│   ├── docs/                           ← 文档
│   └── examples/
└── mobile-bank-agent-eval/             ← 本 skill（只放增量）
    ├── SKILL.md                        ← 主编排
    ├── skills/                         ← 子 skill（用例生成，Agent 自己做）
    │   ├── requirements-analysis/
    │   └── test-case-design/
    ├── scripts/                        ← 只放定制脚本
    │   ├── case_io.py                  ← YAML 用例读写
    │   └── excel_adapter.py            ← Excel→YAML 转换
    ├── adapters/                       ← 子 skill 形式执行器适配器（占位）
    │   ├── cdp-web-executor/
    │   ├── script-executor/
    │   └── api-executor/
    ├── docs/                           ← 定制文档
    └── examples/
```

## 运行时引用

本 skill 不复制 agent-eval 的脚本，运行时通过路径引用：

```bash
AGENT_EVAL=skills/agent-eval

# 阶段 1-2: 用例生成（本 skill 的子 skill）
# Agent 通过 Task 工具自己生成维度和用例
# 调本 skill 的 case_io.py 写 YAML

# 阶段 3-8: 复用 agent-eval
python $AGENT_EVAL/scripts/eval_runner.py --config .agent-eval/config.yaml --split train
python $AGENT_EVAL/scripts/diagnoser.py --config .agent-eval/config.yaml --latest
python $AGENT_EVAL/scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id>
python $AGENT_EVAL/scripts/html_report.py --config .agent-eval/config.yaml --run <run_id>
python $AGENT_EVAL/scripts/reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply
python $AGENT_EVAL/scripts/auto_patcher.py --config .agent-eval/config.yaml --baseline-run <run_id> --split regression --auto-apply
```

## 工作流程

### 阶段 1: 需求分析（子 skill）
委托 `requirements-analysis` 子 skill → Agent 自己分析需求 → 调 `case_io.py` 写 YAML

### 阶段 2: 用例设计（子 skill）
委托 `test-case-design` 子 skill → Agent 自己设计用例 → 调 `case_io.py` 写 cases YAML

### 阶段 3-8: 评测优化（复用 agent-eval）
调用 `skills/agent-eval/scripts/` 下的脚本执行/诊断/评审/报告/优化

## 关键原则

- **增量扩展**：不复制 agent-eval，只新增定制部分
- **可合并**：合并回 main 时只有新增文件，零冲突
- **用例生成由 Agent 完成**：通过 Task 工具，不在脚本里调 LLM
- **脚本只做确定性工作**：YAML IO / Excel 转换
- **执行器和用例输入都通过适配器解耦**
