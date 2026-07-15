# Agent Eval Skill — 手机银行定制版

基于 agent-eval 主 skill 的手机银行 Agent 评测与优化版本。

## 与主版本的区别

本版本在 agent-eval v2.1.0 基础上，增加了手机银行定制的四阶段流水线：

| 阶段 | 脚本 | 输入 | 输出 |
|------|------|------|------|
| 1. 需求分析 | generate_requirements.py | 需求文本 | requirements_analysis.xlsx |
| 2. 用例生成 | generate_testcases.py | requirements.xlsx | test_cases.xlsx |
| 3. 用例执行 | execute_testcases.py | test_cases.xlsx + 环境信息 | execution_results.xlsx |
| 4. 报告生成 | generate_report.py | 3个Excel | test_report.html + .md |

同时保留 agent-eval 全部通用能力：
- F1-F8 失败归因 + HRPO 层次化根因
- 9 个评审 Agent + Agreement Matrix
- reference 自动注入 + auto_patcher 全自动优化
- HTML 报告 + Dashboard + CI 回归

## 安装

```bash
cp -r skills/agent-eval .claude/skills/
```

## 使用

### 四阶段流水线（手机银行定制）

```bash
SKILL_DIR=.claude/skills/agent-eval

# 阶段1: 需求分析
python $SKILL_DIR/scripts/generate_requirements.py \
  --description "手机银行助手需求..." \
  --output $SKILL_DIR/data/requirements_analysis.xlsx

# 阶段2: 用例生成
python $SKILL_DIR/scripts/generate_testcases.py \
  --input $SKILL_DIR/data/requirements_analysis.xlsx \
  --output $SKILL_DIR/data/test_cases.xlsx --per-scenario 3

# 阶段3: 用例执行
python $SKILL_DIR/scripts/execute_testcases.py \
  --input $SKILL_DIR/data/test_cases.xlsx \
  --output $SKILL_DIR/data/execution_results.xlsx \
  --base-url http://localhost:8080/api/chat

# 阶段4: 报告生成
python $SKILL_DIR/scripts/generate_report.py \
  --requirements $SKILL_DIR/data/requirements_analysis.xlsx \
  --testcases $SKILL_DIR/data/test_cases.xlsx \
  --results $SKILL_DIR/data/execution_results.xlsx \
  --output $SKILL_DIR/data/test_report.html
```

### 诊断与优化（agent-eval 通用）

```bash
# 诊断 F1-F8
python $SKILL_DIR/scripts/diagnoser.py --config .agent-eval/config.yaml --latest

# 多 Judge 评审
python $SKILL_DIR/scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id>

# HRPO + reference + A/B
python $SKILL_DIR/scripts/auto_patcher.py --config .agent-eval/config.yaml --baseline-run <run_id> --split regression --auto-apply
```

## 环境变量

- `LLM_API_KEY`: LLM API key（阶段1-2 脚本内部集成 LLM 调用）
- `LLM_MODEL`: 模型名（默认 gpt-4o）
- `LLM_BASE_URL`: API 地址

## 子 skill

大 skill 套小 skill 结构：

| 子 skill | 阶段 | 说明 |
|---------|------|------|
| orchestrator | 编排 | 按顺序调用各阶段 |
| requirements-analysis | 1 | 需求分析 |
| test-case-generator | 2 | 用例生成 |
| test-executor | 3 | 用例执行 |
| test-reporter | 4 | 报告生成 |

## License

MIT
