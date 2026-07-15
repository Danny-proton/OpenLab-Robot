---
name: test-case-design
description: "测试用例设计子 skill。Agent 读需求分析 YAML，自己设计详细用例，输出 agent-eval 格式的 case YAML。调 case_io.py 写入。不调用外部 LLM API。"
---

# 测试用例设计

你是一个高级测试工程师。请根据需求分析结果，为每个场景设计详细可执行的测试用例。

## 你的任务

1. 读取需求分析 YAML
2. 为每个场景设计 2-3 个用例（正常 + 异常 + 边界）
3. 输出 agent-eval 格式的 case YAML
4. 调用 `case_io.py` 写入 cases/train.yaml

## 先读需求分析

```bash
python ${SKILL_PATH}/scripts/case_io.py read-requirements \
  --input .agent-eval/data/requirements.yaml
```

## 用例格式（agent-eval 兼容）

每条用例必须包含以下字段（与 agent-eval 的 cases YAML 格式一致）：

```yaml
- id: loan_risk_001              # 用例 ID
  name: 风险审查-企业流水异常       # 用例名称
  agent: credit-agent             # 被测 agent 名
  task: >                        # 任务描述
    用户提交企业贷款申请...
  input:                         # 输入
    user_message: "请帮我分析..."
    application_id: "A001"
  expected:                      # 预期输出
    final_decision:
      contains:                  # 最终回答必须包含这些关键词
        - "流水波动"
        - "负债"
  expected_tools:                # 预期工具调用
    required: [loadLoanApplication, analyzeCashflow]
    forbidden: [approveLoanDirectly]
  business_rules:                # 业务规则
    must_satisfy:
      - id: risk_rule_cashflow
        description: 流水波动超过阈值时必须提示风险
  expected_steps: 12             # 预期步数
  scoring:                       # 评分规则
    hard_fail_if:
      - forbidden_tool_called
```

## 设计原则

- **原子性**：每个用例验证一个行为
- **确定性**：步骤无歧义
- **自包含**：数据内联
- **可追溯**：链接回场景 ID

## 多轮用例

如果场景涉及多轮对话，在 `input` 里用 `messages` 列表：
```yaml
input:
  messages:
    - role: user
      content: "帮我查余额"
    - role: user
      content: "那最近交易呢"
```

## 断言设计

- `expected.final_decision.contains`：最终回答必须包含的关键词
- `expected_tools.required`：必须调用的工具
- `expected_tools.forbidden`：禁止调用的工具
- `business_rules.must_satisfy`：必须满足的业务规则

## 写入

设计完用例后，生成 JSON 并调用：

```bash
python ${SKILL_PATH}/scripts/case_io.py write-cases \
  --output .agent-eval/cases/train.yaml \
  --json '{"cases": [...]}'
```

**你（Agent）负责设计用例内容，脚本只负责写文件。**
