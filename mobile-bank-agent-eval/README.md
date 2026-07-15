# Mobile Bank Agent Eval Skill

**agent-eval 的支线扩展。** 只补充用例生成能力（需求分析 + 用例设计），其余全部复用 agent-eval。

## 与 agent-eval 的关系

```
agent-eval（主轴）               mobile-bank-agent-eval（支线）
├── 执行（eval_runner）           ├── 用例生成（子 skill + Agent）
├── 评分（scorer）                │   ├── requirements-analysis
├── 诊断（diagnoser F1-F8）       │   └── test-case-design
├── 多 Judge（9 agent）           └── YAML IO（case_io.py）
├── 报告（html_report 11节）
├── reference（8 模板自动注入）
└── A/B（auto_patcher）
```

**mobile-bank-agent-eval 只做两件事**：
1. Agent 自己分析需求，生成 10 维度 + 场景
2. Agent 自己设计用例，输出 agent-eval 格式的 case YAML

**其余全部复用 agent-eval**：执行/评分/诊断/报告/优化。

## 目录结构

```
mobile-bank-agent-eval/
├── SKILL.md                        ← 主编排
├── skills/                         ← 子 skill（prompt 驱动）
│   ├── requirements-analysis/
│   │   └── SKILL.md                ← Agent 自己分析需求
│   └── test-case-design/
│       └── SKILL.md                ← Agent 自己设计用例
├── scripts/
│   └── case_io.py                  ← 唯一脚本：YAML 读写（不调 LLM）
├── guides/
│   └── 01_workflow.md
└── examples/
    └── sample_requirements.txt
```

## 关键原则

- **需求分析和用例设计由 Agent 完成**（通过 Task 工具），不在脚本里调 LLM
- **脚本只做确定性工作**：YAML 读写
- **解耦**：不调 robot binary，不依赖运行环境
- **复用**：执行/评分/诊断/报告/优化全部用 agent-eval

## 安装

```bash
# 两个 skill 一起装
cp -r skills/agent-eval .claude/skills/
cp -r skills/mobile-bank-agent-eval .claude/skills/
```

## 使用

对 Claude Code 说："帮我评测手机银行 Agent"

Claude 会：
1. 触发 mobile-bank-agent-eval
2. Agent 自己生成用例（通过子 skill）
3. 调用 agent-eval 执行/评分/诊断/报告
