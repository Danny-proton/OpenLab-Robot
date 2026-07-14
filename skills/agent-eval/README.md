# Agent Eval Skill (轻量嵌套版)

无 MCP server、无 hooks 的轻量版。所有能力通过 Bash 直接调 Python 脚本。

## 与 plugin 标准版的区别

| 维度 | plugin 标准版 | 轻量 skill 版（本版）|
|------|-------------|-------------------|
| 安装 | `claude --plugin-dir .` | 复制到 `.claude/skills/` |
| 能力暴露 | MCP server 10 个工具 | Bash 直接调 Python 脚本 |
| Hooks | 4 个事件钩子 | 无 |
| Agent 委托 | plugin agents/ 目录 | skill 内 agents/ 子目录 |
| 体积 | 207K | 更小 |
| 适合 | 完整 plugin 体验 | 快速上手、单步执行、嵌入式 |

## 安装

### 方式 1：项目级 skill

```bash
unzip agent-eval-skill-lite.zip
cp -r agent-eval /path/to/your/project/.claude/skills/
```

### 方式 2：用户级 skill

```bash
unzip agent-eval-skill-lite.zip
cp -r agent-eval ~/.claude/skills/
```

### 方式 3：直接用

```bash
unzip agent-eval-skill-lite.zip
cd agent-eval
# 直接调脚本
python scripts/eval_runner.py --scaffold /path/to/project
```

## 使用

### 在 Claude Code 里

安装后，对 Claude Code 说：
- "帮我评测这个 agent" → 触发 skill → Claude 用 Bash 调脚本
- "诊断一下最新的 run"
- "用 HRPO 分析根因"
- "跑 A/B 验证"

### 直接命令行

```bash
# 初始化
python scripts/eval_runner.py --scaffold .

# 跑基线
python scripts/eval_runner.py --config .agent-eval/config.yaml --split train --variant baseline

# 诊断
python scripts/diagnoser.py --config .agent-eval/config.yaml --latest

# 多 Judge
python scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id>

# HRPO 分析
python scripts/opik_adapter.py --config .agent-eval/config.yaml --run <run_id> --optimizer hrpo

# 生成 reference
python scripts/reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply

# 全自动优化
python scripts/auto_patcher.py --config .agent-eval/config.yaml --baseline-run <run_id> --split regression --auto-apply

# HTML 报告
python scripts/html_report.py --config .agent-eval/config.yaml --run <run_id>

# Dashboard
python scripts/dashboard.py --config .agent-eval/config.yaml
```

## 目录结构

```
agent-eval/
├── SKILL.md                   ← skill 入口（allowed-tools 含 Bash/AskUserQuestion）
├── scripts/                   ← 19 个 Python 脚本 + 4 个 adapter
│   ├── common.py
│   ├── eval_runner.py
│   ├── diagnoser.py
│   ├── scorer.py
│   ├── multi_judge.py
│   ├── opik_adapter.py
│   ├── reference_optimizer.py
│   ├── auto_patcher.py
│   ├── html_report.py
│   ├── dashboard.py
│   ├── ci_regression.py
│   ├── ask_setup.py
│   ├── charts.py
│   ├── trace_normalizer.py
│   ├── mutator.py
│   ├── abtest.py
│   ├── report.py
│   ├── deepeval_adapter.py
│   ├── patch_manager.py
│   └── adapters/
│       ├── openlab_robot_adapter.py
│       ├── spring_ai_to_uatr.py
│       ├── claude_code_otel_to_uatr.py
│       └── generic_json_to_uatr.py
├── agents/                    ← 9 个评审 Agent（Claude 自动委托）
│   ├── domain-judge.md
│   ├── tool-trace-judge.md
│   ├── workflow-judge.md
│   ├── faithfulness-judge.md
│   ├── regression-judge.md
│   ├── safety-judge.md
│   ├── gatekeeper.md
│   ├── optimizer-planner.md
│   └── patch-writer.md
├── guides/                    ← 15 篇文档
├── templates/                 ← 报告模板
└── examples/.agent-eval/      ← 示例配置（scaffold 时复制）
    ├── config.yaml
    ├── cases/
    ├── metrics/
    ├── adapters/
    ├── mutators/
    └── schemas/
```

## 核心能力

1. **F1-F8 失败归因**（F8 是执行冗余：轮数过多/重复规划/无效中间步/探索式徘徊）
2. **HRPO 层次化根因分析**（4 层：现象→直接原因→根因→修复层）
3. **reference 自动注入**（8 个模板：执行路径/工具决策树/字段映射等）
4. **auto_patcher 全自动循环**（生成 reference → A/B → 评审 → accept/reject）
5. **专业 HTML 报告**（11 节 + 9 SVG 图表 + 调用结构树 + 调用链详情表）
6. **交互式 Dashboard**（10 页，暗色主题）
7. **9 个评审 Agent**（6 规则型 + 3 决策型，Claude 自动委托）
8. **CI 持续回归**（exit 0/1，last_known_good 机制）

## 依赖

- Python 3.9+
- PyYAML（必需）
- jsonschema（可选）

## License

MIT
