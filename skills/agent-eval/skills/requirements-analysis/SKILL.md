---
name: requirements-analysis
description: "需求分析子 skill。运行 generate_requirements.py 生成测试维度和场景到 Excel。"
---

# 需求分析

运行脚本生成测试维度和场景：

```bash
python {SKILL_PATH}/scripts/generate_requirements.py \
  --description "用户的需求文本" \
  --output {SKILL_PATH}/data/requirements_analysis.xlsx
```

用户输入有多行时，将换行符替换为 `\n` 放入参数。

脚本返回的 stdout 已包含完整分析结果，直接展示给用户。

列出维度：
```bash
python {SKILL_PATH}/scripts/generate_requirements.py --list {SKILL_PATH}/data/requirements_analysis.xlsx
```
