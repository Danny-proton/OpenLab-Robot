# Guide 03 — 指标合约

v0 只做 5 个硬指标 + 3 个软指标。每个指标的定义写在 `.agent-eval/metrics/<name>.yaml`，scorer 读这些文件计算。**禁止在 scorer 里硬编码指标**——加指标必须加 metric 文件。

## 5 个硬指标（v0 必须实现）

### 1. task_success（任务成功）

- **定义**：最终答案是否满足 case 里 `expected.final_decision` 的所有约束。
- **判定方式**：规则优先。`expected.final_decision.contains` 是一个字符串数组，全部出现在 `final_answer` 里才算通过。如果 case 提供了 `expected.final_decision.regex`，则用正则匹配。复杂语义判定走 LLM judge（见下）。
- **取值**：`0.0` / `1.0`（失败 / 成功）。`hard_fail_if` 命中时直接 0。
- **LLM judge 模式**：当 case 标了 `expected.final_decision.llm_judge: true` 时，scorer 会调用配置的 LLM judge（adapter 里指定），传入 `task` / `input` / `final_answer` / `expected.final_decision.description`，让 LLM 给 0/0.5/1 三档。v0 默认不开。

### 2. tool_correctness（工具调用正确性）

- **定义**：实际调用的工具序列是否满足 case 里 `expected_tools` 的约束。
- **子项**：
  - `required_tool_recall` — `expected_tools.required` 中的工具是否都被调用过。`recall = 命中数 / required 数`。
  - `forbidden_tool_violation` — `expected_tools.forbidden` 中的工具是否被调用过。命中即整条 case 硬失败。
  - `order_soft_score` — `expected_tools.order.soft` 给出了一个期望顺序，按最长公共子序列比例打分。`soft` 表示不严格要求，只是参考。
- **取值**：`tool_correctness = 0.5 * recall + 0.3 * order_soft + 0.2 * (1 - forbidden_called_count)`。forbidden 命中时直接硬失败，不进这个公式。

### 3. business_rule_coverage（业务规则覆盖）

- **定义**：case 里 `business_rules.must_satisfy` 列出的关键业务规则，是否在 trace 或最终答案里有体现。
- **判定方式**：每条规则可以指定：
  - `trace_event_contains` — trace 里是否出现过包含某关键词的事件（如 `tool_result.result.volatility == "high"`）。
  - `final_answer_contains` — 最终答案里是否包含某关键词。
  - `llm_judge` — 复杂语义，让 LLM 判断答案是否遵守该规则。
- **取值**：`coverage = 满足的规则数 / 总规则数`。

### 4. output_schema_validity（输出结构合规）

- **定义**：如果 case 指定了 `expected.structured_output_schema`（指向一个 JSON Schema 文件），最终答案能否解析成符合该 schema 的对象。
- **判定方式**：
  1. 尝试从 `final_answer` 里抽出 JSON（支持纯 JSON、markdown code fence、`<json>...</json>` 标签三种）。
  2. 用 `jsonschema` 库验证。
- **取值**：`1.0`（完全合规）/ `0.5`（能解析但不完全合规）/ `0.0`（解析失败）。

### 5. efficiency（效率）

- **定义**：agent 是否绕路、重复调用、无效调用。
- **子项**：
  - `step_count_score` = `min(expected_steps, actual_steps) / max(expected_steps, actual_steps)`，case 里 `expected_steps` 可选，不填则用 split 中位数。
  - `repeat_tool_call_penalty` = `1 - min(repeat_count / total_tool_calls, 0.5)`，重复调用同一工具同一参数超过 2 次开始扣分。
  - `error_recovery_score` — 出现 error 事件后是否还能正常完成。能恢复给 1，直接挂掉给 0。
- **取值**：`efficiency = 0.4 * step_count_score + 0.3 * (1 - repeat_penalty) + 0.3 * error_recovery_score`。

## 3 个软指标（v0.1 再加，v0 先占位）

| 指标 | 说明 | v0 状态 |
|------|------|---------|
| `answer_relevance` | 答案是否答到点上 | 占位，返回 1.0 |
| `evidence_faithfulness` | 答案是否基于输入材料，没有幻觉 | 占位，返回 1.0 |
| `step_efficiency` | 比 efficiency 更细：每步是否必要 | 占位，返回 1.0 |

软指标占位的原因：v0 不强制接 LLM judge，避免本地运行依赖外部 API。如果你有 LLM judge endpoint，可以在 metric 文件里把 `llm_judge: true` 打开。

## 加权总分

```
score = 0.35 * task_success
      + 0.20 * tool_correctness
      + 0.20 * business_rule_coverage
      + 0.15 * output_schema_validity
      + 0.10 * efficiency
      - hard_fail_penalty
```

`hard_fail_penalty = 1.0`（任何一条 `hard_fail_if` 命中）。所以一条硬失败的 case 总分 ≤ 0。

权重在 `config.yaml` 里可以覆盖，但 v0 不建议改——这组权重是按"工具正确性比效率重要、业务规则比输出结构重要"的工程直觉拍的，改之前先想清楚。

## metric 文件长什么样

`.agent-eval/metrics/tool_call.yaml`：

```yaml
name: tool_correctness
version: 1
description: 工具调用是否满足 case 的 expected_tools 约束
type: hard
weight: 0.20
components:
  - name: required_tool_recall
    formula: hit_count / required_count
    source: trace
    source_filter:
      event: tool_call
  - name: forbidden_tool_violation
    formula: violation_count
    source: trace
    source_filter:
      event: tool_call
    hard_fail: true
  - name: order_soft_score
    formula: lcs_ratio(expected_order, actual_order)
    source: trace
    source_filter:
      event: tool_call
aggregate: 0.5 * required_tool_recall + 0.3 * order_soft_score + 0.2 * (1 - min(forbidden_tool_violation, 1))
```

scorer 读这个文件，按 `source_filter` 从 trace 里抽出相关事件，按 `formula` 计算。`formula` 里能引用的函数有限：`hit_count` / `violation_count` / `lcs_ratio` / `contains` / `matches_regex` / `jsonschema_valid`。**不要在 formula 里写任意 Python**——那会让 metric 不可复现。

## 硬失败优先级

如果一条 case 同时命中多个硬失败，scorer 只在 `scores/<run_id>.json` 里记一条 `hard_fail_reason`（取第一个命中的）。diagnoser 会看到所有命中的硬失败，分别归因。

## 单 case 分数 vs 汇总分数

- 单 case 分数：上面的加权公式。
- 汇总分数：单 case 分数的算术平均。

**禁止**用 max / min / 中位数作为汇总——它们会掩盖失败。诊断只看单 case 分数。

## 指标的可复现性

metric 必须是确定性的：同一条 case + 同一条 trace + 同一个 metric 文件，必须算出同一个分数。LLM judge 模式破坏这一点，所以 v0 默认关闭，开启时要在 case 里显式标 `llm_judge: true` 并接受分数会有 ±0.1 抖动。
