---
name: mobile-bank-agent-eval
description: "Use proactively when evaluating mobile banking agents. Extends agent-eval with automated test case generation via sub-skills. Agent generates test dimensions and cases through Task tool (not scripts calling LLM). Scripts only do deterministic YAML IO. Reuses agent-eval for execution/scoring/diagnosis/report/optimization. Trigger: 手机银行测试, agent 评测, 用例生成, 测试执行, mobile bank test, agent evaluation, 自动化测试."
allowed-tools: Bash(python *), Bash(python3 *), Bash(ls *), Bash(cat *), Bash(mkdir *), Bash(cp *), Read, Write, Edit, Grep, Glob, Task, AskUserQuestion
---

# 手机银行 Agent 自动评测 Skill

**agent-eval 的支线扩展。** 只补充用例生成能力（需求分析 + 用例设计），其余全部复用 agent-eval。

## 架构

```
agent-eval/                    ← 主轴（不动，提供执行/评分/诊断/报告/优化）
mobile-bank-agent-eval/        ← 你在这里（补充用例生成）
├── skills/
│   ├── requirements-analysis/ ← 子 skill：Agent 自己分析需求生成维度
│   └── test-case-design/      ← 子 skill：Agent 自己设计用例
├── scripts/
│   └── case_io.py             ← 唯一脚本：YAML 读写（不调 LLM）
└── examples/
```

## 工作流程

### 阶段 1-2: 用例生成（本 skill 提供）

委托给子 skill，Agent 自己生成：

1. **需求分析** — 委托 `requirements-analysis` 子 skill
   - Agent 读用户需求文本
   - 按 10 维度框架生成维度 + 场景
   - 调 `case_io.py write-requirements` 写入 `.agent-eval/data/requirements.yaml`

2. **用例设计** — 委托 `test-case-design` 子 skill
   - Agent 读需求分析 YAML
   - 为每个场景设计用例（agent-eval 的 YAML case 格式）
   - 调 `case_io.py write-cases` 写入 `.agent-eval/cases/train.yaml`

### 阶段 3-8: 评测与优化（复用 agent-eval）

生成 case 后，直接调用 agent-eval 的脚本：

3. **执行** — `python <agent-eval>/scripts/eval_runner.py --config .agent-eval/config.yaml --split train --variant baseline`
4. **诊断** — `python <agent-eval>/scripts/diagnoser.py --config .agent-eval/config.yaml --latest`
5. **多 Judge** — `python <agent-eval>/scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id>`
6. **报告** — `python <agent-eval>/scripts/html_report.py --config .agent-eval/config.yaml --run <run_id>`
7. **reference** — `python <agent-eval>/scripts/reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply`
8. **A/B** — `python <agent-eval>/scripts/auto_patcher.py --config .agent-eval/config.yaml --baseline-run <run_id> --split regression --auto-apply`

## 关键原则

- **需求分析和用例设计由 Agent 完成**（通过 Task 工具），不在脚本里调 LLM
- **脚本只做确定性工作**：YAML 读写
- **子 skill 用文字指导 Agent**，不包含 LLM 调用代码
- **解耦**：脚本不依赖特定运行环境（不调 claude-haha binary）
- **复用**：执行/评分/诊断/报告/优化全部用 agent-eval

## 10 个测试维度

1. 业务场景覆盖 2. 业务流程覆盖 3. 用户角色与意图覆盖
4. 业务规则与约束覆盖 5. 输入形态与上下文覆盖 6. 安全与边界覆盖
7. 多轮对话状态覆盖 8. 异常恢复流程覆盖 9. 性能与延迟边界覆盖
10. 合规与监管覆盖
