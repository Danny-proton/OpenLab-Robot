---
name: test-case-design
description: "测试用例设计子 skill。Agent 读需求分析 YAML，自己设计用例，输出 agent-eval 格式的 case YAML。不调用外部 LLM API。"
---

# 测试用例设计

你是高级测试工程师。根据需求分析结果，为每个场景设计测试用例。

## 任务

1. 读需求分析 YAML
2. 为每个场景设计 2-3 个用例
3. 输出 agent-eval 格式的 case YAML
4. 调 case_io.py 写入

```bash
python ${SKILL_PATH}/scripts/case_io.py read-requirements \
  --input .agent-eval/data/requirements.yaml

python ${SKILL_PATH}/scripts/case_io.py write-cases \
  --output .agent-eval/cases/train.yaml \
  --json '{"cases":[...]}'
```

用例格式与 agent-eval 的 cases YAML 一复（id/task/input/expected/expected_tools/business_rules）。
Agent 自己设计用例，脚本只写文件。
