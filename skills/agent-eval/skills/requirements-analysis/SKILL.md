---
name: requirements-analysis
description: "需求分析子 skill。Agent 自己分析需求，按 10 维度框架生成测试维度和场景。调 case_io.py 写入 YAML。"
---

# 需求分析

你是需求分析专家。根据用户提供的 Agent 需求说明，生成 10 个测试维度和场景。

## 10 个维度

1. 业务场景覆盖 2. 业务流程覆盖 3. 用户角色与意图覆盖
4. 业务规则与约束覆盖 5. 输入形态与上下文覆盖 6. 安全与边界覆盖
7. 多轮对话状态覆盖 8. 异常恢复流程覆盖 9. 性能与延迟边界覆盖
10. 合规与监管覆盖

## 任务

1. 分析需求文本
2. 为每个维度生成 3-5 个场景
3. 输出 JSON
4. 调 case_io.py 写入 YAML

```bash
python ${SKILL_PATH}/scripts/case_io.py write-requirements \
  --output .agent-eval/data/requirements.yaml \
  --json '{"dimensions":[...],"scenarios":[...]}'
```

Agent 自己做分析，脚本只写文件。详见 docs/PRD_TEST_DESIGN.md。
