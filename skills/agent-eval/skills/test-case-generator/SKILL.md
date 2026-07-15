---
name: test-case-generator
description: "用例生成子 skill。读取需求分析 Excel，调用脚本批量生成测试用例。"
---

# 测试用例生成

先列出维度：
```bash
python {SKILL_PATH}/scripts/generate_requirements.py --list {SKILL_PATH}/data/requirements_analysis.xlsx
```

向用户展示维度，询问：每个场景生成几条用例？全部维度还是指定维度？

按用户选择执行：
```bash
python {SKILL_PATH}/scripts/generate_testcases.py \
  --input {SKILL_PATH}/data/requirements_analysis.xlsx \
  --output {SKILL_PATH}/data/test_cases.xlsx \
  --per-scenario N [--dimensions DIM-001,DIM-002]
```

将工具返回的 stdout 直接作为回复。
