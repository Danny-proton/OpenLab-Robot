---
name: test-reporter
description: "报告生成子 skill。读取执行结果 Excel，生成 Markdown 和 HTML 格式测试报告。"
---

# 测试报告

运行脚本（自动同时生成 .md 和 .html）：
```bash
python {SKILL_PATH}/scripts/generate_report.py \
  --requirements {SKILL_PATH}/data/requirements_analysis.xlsx \
  --testcases {SKILL_PATH}/data/test_cases.xlsx \
  --results {SKILL_PATH}/data/execution_results.xlsx \
  --output {SKILL_PATH}/data/test_report.md
```

将工具返回的 stdout 直接作为回复。
