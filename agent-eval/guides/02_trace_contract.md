# Guide 02 — Trace 合约

v0 不上 OTel 平台，直接写 NDJSON。这份指南定义 trace 事件的最小 schema、事件类型、以及 Spring AI 那边怎么吐出这些事件。

## 为什么不上 OTel

OTel 适合做大规模分布式观测，但 v0 阶段它带来三个问题：

1. 部署成本——OTel Collector + 后端存储，对本地实验过重。
2. 字段不可控——Spring AI 默认导出的 trace 字段不一定是我们评测需要的。
3. 默认不导出 prompt/completion 内容（官方明确说因为可能敏感且体量大），但评测恰恰需要看 prompt 和 tool arguments。

所以 v0 自己控制字段，写本地 NDJSON。每个 run 一个 `.jsonl` 文件，一行一个事件。未来要接 Opik/Langfuse/Phoenix，只要加一个 exporter 把 NDJSON 转成它们的格式即可。

## 事件 schema

每个事件是一个 JSON 对象，字段如下：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `run_id` | string | 是 | 评测 run 的 ID |
| `case_id` | string | 是 | 这条 trace 属于哪条 case |
| `case_run_id` | string | 是 | `<run_id>::<case_id>`，全局唯一 |
| `ts` | string (ISO 8601) | 是 | 事件时间戳，带时区 |
| `event` | string | 是 | 事件类型，见下表 |
| `step` | int | 是 | 第几步，从 1 开始 |
| `agent` | string | 否 | agent 名称（多 agent 系统中区分） |
| `trace_id` | string | 否 | agent 内部 trace ID，用于关联外部系统 |
| `tool` | string | 否 | `tool_call` / `tool_result` 事件时的工具名 |
| `arguments` | object | 否 | `tool_call` 时的参数 |
| `result` | object | 否 | `tool_result` 时的返回（可脱敏） |
| `status` | string | 否 | `success` / `error` / `timeout` |
| `latency_ms` | int | 否 | 该步耗时 |
| `prompt_hash` | string | 否 | `prompt_rendered` 时的 system prompt hash |
| `model` | string | 否 | `model_call` 时的模型名 |
| `input_tokens` | int | 否 | `model_call` 时的输入 token |
| `output_tokens` | int | 否 | `model_call` 时的输出 token |
| `advisor` | string | 否 | `advisor_enter` / `advisor_exit` 时的 advisor 名 |
| `error` | object | 否 | `error` 事件时的错误详情 `{type, message}` |
| `final_answer` | string | 否 | `agent_final` 时的最终答案 |
| `memory_query` | string | 否 | `memory_retrieval` 时的查询 |
| `memory_hits` | array | 否 | `memory_retrieval` 时命中的记忆条目 |

## 事件类型（v0 只支持这 11 种）

| 事件 | 何时发 | 必填字段 |
|------|--------|---------|
| `agent_start` | agent 开始处理一条 case | `agent` |
| `prompt_rendered` | system prompt 渲染完成 | `prompt_hash`, `model` |
| `model_call` | 一次 LLM 调用开始 | `model`, `input_tokens`(可后填), `output_tokens`(可后填) |
| `tool_call` | 决定调用某个工具 | `tool`, `arguments` |
| `tool_result` | 工具返回 | `tool`, `result`, `status`, `latency_ms` |
| `memory_retrieval` | 检索项目记忆 | `memory_query`, `memory_hits` |
| `advisor_enter` | 进入某个 Advisor | `advisor` |
| `advisor_exit` | 离开某个 Advisor | `advisor`, `status`, `latency_ms` |
| `agent_final` | agent 输出最终答案 | `final_answer` |
| `error` | 任意步骤出错 | `error` |
| `agent_end` | agent 完成本 case | `status`, `latency_ms` |

## 一个最小例子

```jsonl
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:00+09:00","event":"agent_start","step":1,"agent":"loan-risk-agent"}
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:00+09:00","event":"prompt_rendered","step":2,"prompt_hash":"sha256:abc123","model":"glm-4.6"}
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:01+09:00","event":"model_call","step":3,"model":"glm-4.6","input_tokens":1200,"output_tokens":45}
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:01+09:00","event":"tool_call","step":4,"tool":"load_loan_application","arguments":{"application_id":"A001"}}
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:01+09:00","event":"tool_result","step":5,"tool":"load_loan_application","result":{"summary":"loaded"},"status":"success","latency_ms":120}
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:02+09:00","event":"tool_call","step":6,"tool":"analyze_cashflow","arguments":{"application_id":"A001"}}
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:02+09:00","event":"tool_result","step":7,"tool":"analyze_cashflow","result":{"volatility":"high"},"status":"success","latency_ms":421}
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:03+09:00","event":"agent_final","step":8,"final_answer":"流水波动较大，建议补充担保材料后复审。"}
{"run_id":"20260702-183000-baseline-loan_v1","case_id":"loan_risk_001","case_run_id":"20260702-183000-baseline-loan_v1::loan_risk_001","ts":"2026-07-02T18:30:03+09:00","event":"agent_end","step":9,"status":"success","latency_ms":3120}
```

## trace_normalizer.py 做什么

不同 adapter 吐出的 trace 格式可能不一样（mock adapter 吐的就是上面这个标准格式；Spring AI 的 `EvalTraceAdvisor` 吐的是 Java 端的 JSON，字段名可能略有不同）。`trace_normalizer.py` 的职责是：

1. 读取 adapter 配置里 `trace_mapping` 字段，把外部字段名映射到内部 schema。
2. 校验必填字段是否齐全。缺字段的行会被写到 `traces/<run_id>.invalid.jsonl` 而不是主文件。
3. 按 `step` 排序。

## Spring AI 那边怎么吐

见 `spring-ai-integration/`：

- `EvalTraceAdvisor.java` — 挂在 ChatClient 的 Advisor 链上，记录 `agent_start` / `prompt_rendered` / `model_call` / `advisor_enter` / `advisor_exit` / `agent_final` / `agent_end`。
- `EvalToolCallbackWrapper.java` — 包一层 `ToolCallback`，记录 `tool_call` / `tool_result`。

两个类都把事件写到一个 `BlockingQueue`，由后台线程 flush 到 HTTP endpoint（runner 提供）或本地文件。Spring AI 工程师只需要在 agent 配置里挂上这两个 bean，不需要改业务代码。

## 脱敏

`tool_result` 里的 `result` 字段可能含敏感数据。adapter 配置里可以指定 `redact_fields`（如 `["ssn", "id_card"]`），`trace_normalizer.py` 会把这些字段替换成 `<redacted>`。`final_answer` 默认不脱敏——评测需要看完整答案。

## 大小与保留

单条 case 的 trace 一般 5–50 个事件，每个事件 < 2KB。一次 20 case 的 run 大约几百 KB，完全可以 Git 追踪。如果 trace 过大，可以在 config 里设 `trace_max_kb_per_case`，超过的话只保留前 N 步 + 最后一步 + 所有 error 事件。
