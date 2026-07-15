---
name: mobile-bank-agent-eval
description: "Use proactively when evaluating mobile banking agents. Independently deployable. Contains all agent-eval core scripts + test case generation sub-skills. Agent generates cases via Task tool. Pluggable executor adapters (mock/HTTP/CDP/script/API). Trigger: 手机银行测试, agent 评测, 用例生成, mobile bank test."
allowed-tools: Bash(python *), Bash(python3 *), Read, Write, Edit, Grep, Glob, Task, AskUserQuestion
---

# 手机银行 Agent 自动评测 Skill

**独立可部署。** 内置 agent-eval 全部核心能力 + 用例生成扩展。

## 架构

```
mobile-bank-agent-eval/
├── SKILL.md                        ← 主编排
├── scripts/                        ← 26个脚本（24通用+2定制）
├── skills/                         ← 子skill（Agent自己生成用例）
│   ├── requirements-analysis/
│   └── test-case-design/
├── adapters/                       ← 子skill形式执行器适配器
│   ├── cdp-web-executor/           ← CDP网页执行（待实现）
│   ├── script-executor/            ← 脚本执行（待实现）
│   └── api-executor/               ← API执行（待实现）
├── agents/                         ← 9个评审agent
├── guides/                         ← 15篇
└── examples/
```

## 工作流程

### 阶段1-2: 用例生成（子skill，Agent自己做）
1. 委托 requirements-analysis → Agent分析需求 → 调case_io.py写YAML
2. 委托 test-case-design → Agent设计用例 → 调case_io.py写cases

### 阶段3-8: 评测优化（内置agent-eval能力）
3. eval_runner.py 执行
4. diagnoser.py 诊断F1-F8
5. multi_judge.py 多Judge评审
6. html_report.py 报告
7. reference_optimizer.py reference注入
8. auto_patcher.py A/B

## 执行器适配器
通过config.yaml的adapter字段选择：mock/http/openlab_robot/cdp_web/script/api
参见 https://gitee.com/HongKongJournalist/OpenLab-Robot/blob/master/skills/https://gitee.com/HongKongJournalist/OpenLab-Robot/blob/master/skills/agent-eval/docs/ADAPTER_SPEC.md

## 用例输入适配器
YAML（case_io.py）/ Excel（excel_adapter.py）

## 关键原则
- 用例生成由Agent完成，不在脚本里调LLM
- 脚本只做确定性工作
- 执行器和用例输入都通过适配器解耦
- 独立可部署，不依赖agent-eval目录
