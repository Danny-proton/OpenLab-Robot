# Guide 01 — 工作流程

4 阶段流水线：需求分析 → 用例生成 → 测试执行 → 报告生成

## 流程图

```
用户需求文本
    │
    ▼
阶段1: generate_requirements.py
    │ 生成 10 维度 + 场景 → requirements.xlsx
    ▼
阶段2: generate_testcases.py
    │ 为每场景生成 N 用例 → test_cases.xlsx
    ▼
阶段3: execute_testcases.py
    │ 执行用例（mock/http/openlab）→ execution_results.xlsx + trace.jsonl
    ▼
阶段4: generate_report.py
    │ 生成 HTML + MD 报告 → test_report.html
    ▼
专业报告（含调用结构 + 失败归因）
```

## 一键跑通（mock 模式）

```bash
SKILL_PATH=.claude/skills/mobile-bank-agent-eval
python $SKILL_PATH/scripts/generate_requirements.py \
  --description "手机银行助手需求" \
  --output $SKILL_PATH/data/requirements_analysis.xlsx
python $SKILL_PATH/scripts/generate_testcases.py \
  --input $SKILL_PATH/data/requirements_analysis.xlsx \
  --output $SKILL_PATH/data/test_cases.xlsx --per-scenario 3
python $SKILL_PATH/scripts/execute_testcases.py \
  --input $SKILL_PATH/data/test_cases.xlsx \
  --output $SKILL_PATH/data/execution_results.xlsx --mock
python $SKILL_PATH/scripts/generate_report.py \
  --requirements $SKILL_PATH/data/requirements_analysis.xlsx \
  --testcases $SKILL_PATH/data/test_cases.xlsx \
  --results $SKILL_PATH/data/execution_results.xlsx \
  --trace $SKILL_PATH/data/trace.jsonl \
  --output $SKILL_PATH/data/test_report.html
```

无需 API key，全流程用 mock 跑通。
