# Guide 07 — UATR Trace Schema (v0.5)

UATR = Universal Agent Trace Record。这是 agent-eval v0.5 引入的统一 trace 中间层，用于把 Spring AI、Claude Code、LangChain、AutoGen 等不同框架的执行轨迹统一成一种 JSONL 格式。

## 为什么需要 UATR

v0 的 trace 是 agent-eval 内部 schema，字段偏少（11 类事件、扁平结构）。v0.5 升级到 UATR 后：

1. **跨框架统一**：Spring AI 和 Claude Code 的 trace 都能转成 UATR，diagnoser/scorer 不需要为每个框架写一份。
2. **OpenTelemetry 对齐**：UATR 的 `attributes` 字段兼容 OTel GenAI semantic conventions（如 `gen_ai.system`、`gen_ai.operation.name`）。
3. **支持 span 层级**：v0 是扁平事件流，UATR 有 `span_id` / `parent_span_id`，能表达子 agent 调用链。
4. **支持 artifact 引用**：prompt / completion / tool arguments 这些大字段不再内联，用 `content_ref` 指向 artifacts 目录，trace 文件本身保持小。
5. **可导出**：UATR → DeepEval / Opik / Langfuse 都可以做 exporter。

## 一条 UATR 事件的最小结构

```json
{
  "schema_version": "uatr-0.5",
  "run_id": "run_20260702_001",
  "case_id": "loan_risk_001",
  "case_run_id": "run_20260702_001::loan_risk_001",
  "trace_id": "abc123",
  "span_id": "span_003",
  "parent_span_id": "span_001",

  "timestamp": "2026-07-02T20:30:00+09:00",
  "framework": "spring_ai",
  "source": "advisor_wrapper",

  "event_type": "tool.call",
  "actor": {
    "type": "agent",
    "name": "loan-risk-agent",
    "role": "executor"
  },

  "component": {
    "type": "tool",
    "name": "analyze_cashflow"
  },

  "input": {
    "content_ref": "artifacts/input/loan_risk_001.json",
    "content_hash": "sha256:xxxx",
    "redacted": true
  },

  "output": {
    "summary": "cashflow volatility detected",
    "content_hash": "sha256:yyyy"
  },

  "metrics": {
    "latency_ms": 421,
    "input_tokens": 1200,
    "output_tokens": 320,
    "cost_usd": 0.0021
  },

  "status": "success",

  "attributes": {
    "tool.arguments": {
      "application_id": "A001"
    },
    "gen_ai.system": "spring_ai",
    "gen_ai.operation.name": "execute_tool"
  }
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `schema_version` | 是 | 固定 `uatr-0.5` |
| `run_id` | 是 | 评测 run ID |
| `case_id` | 是 | case ID |
| `case_run_id` | 是 | `<run_id>::<case_id>` |
| `trace_id` | 否 | agent 内部 trace ID（OTel 兼容） |
| `span_id` | 否 | 当前 span ID |
| `parent_span_id` | 否 | 父 span ID（用于嵌套调用链） |
| `timestamp` | 是 | ISO 8601 带时区 |
| `framework` | 是 | `spring_ai` / `claude_code` / `langchain` / `autogen` / `generic` |
| `source` | 否 | 事件来源：`advisor_wrapper` / `tool_callback` / `otel_export` / `mock` |
| `event_type` | 是 | 见下表 |
| `actor` | 否 | `{type, name, role}` 描述行为主体 |
| `component` | 否 | `{type, name}` 描述被操作的组件 |
| `input` | 否 | `{content_ref, content_hash, redacted}` 或直接内联 |
| `output` | 否 | `{summary, content_hash}` 或直接内联 |
| `metrics` | 否 | `{latency_ms, input_tokens, output_tokens, cost_usd}` |
| `status` | 是 | `success` / `error` / `timeout` / `cancelled` |
| `attributes` | 否 | 自由 KV，OTel 兼容字段放这里 |

## 事件类型（v0.5 固定 24 类）

### Agent 生命周期
- `agent.run.start` — agent 开始处理 case
- `agent.run.end` — agent 完成本 case
- `agent.delegate` — 委派给子 agent（Claude Code Task / Spring AI sub-agent）

### Model 调用
- `model.call.start` — LLM 调用开始
- `model.call.end` — LLM 调用结束

### Tool 调用
- `tool.call.start` — 工具调用开始
- `tool.call.end` — 工具调用结束
- `tool.call.error` — 工具调用异常

### Memory / 检索
- `memory.retrieve.start` — 记忆检索开始
- `memory.retrieve.end` — 记忆检索结束

### Skill（Claude Code）
- `skill.select` — 选择 skill
- `skill.load` — 加载 skill SKILL.md
- `skill.execute.start` — skill 开始执行
- `skill.execute.end` — skill 结束执行

### 规划 / 反思
- `planner.step` — planner 一步决策
- `reflection.step` — 反思一步

### 文件 / Shell / Browser
- `file.read` — 读文件
- `file.write` — 写文件
- `shell.command` — 执行 shell 命令
- `browser.action` — 浏览器操作

### 人工确认
- `human.approval.request` — 请求人工确认
- `human.approval.result` — 人工确认结果

### 评测 / 优化（agent-eval 自身）
- `judge.score` — judge 打分
- `optimizer.patch.proposed` — 优化器提出 patch
- `optimizer.patch.accepted` — patch 被接受
- `optimizer.patch.rejected` — patch 被拒绝

## v0 → UATR 映射

| v0 event | UATR event_type |
|----------|-----------------|
| `agent_start` | `agent.run.start` |
| `agent_end` | `agent.run.end` |
| `prompt_rendered` | `model.call.start`（带 `attributes.prompt_hash`） |
| `model_call` | `model.call.end`（带 input/output_tokens） |
| `tool_call` | `tool.call.start` |
| `tool_result` | `tool.call.end` |
| `memory_retrieval` | `memory.retrieve.end` |
| `advisor_enter` | `planner.step`（带 `attributes.advisor`） |
| `advisor_exit` | `planner.step` |
| `agent_final` | `agent.run.end`（带 `output.final_answer`） |
| `error` | 任意 `*.error` 或 `status: error` |

`trace_normalizer.py` 的 `v0_to_uatr()` 函数实现这个映射，向后兼容 v0 trace。

## 框架 → UATR 映射

### Spring AI

| Spring AI observation | UATR event_type |
|----------------------|-----------------|
| ChatClient call/stream | `agent.run.start` / `agent.run.end` |
| Advisor observation | `planner.step` |
| ChatModel observation | `model.call.start` / `model.call.end` |
| Tool observation | `tool.call.start` / `tool.call.end` |
| VectorStore observation | `memory.retrieve.start` / `memory.retrieve.end` |

`adapters/spring_ai_to_uatr.py` 实现。

### Claude Code（OTel）

| Claude Code span | UATR event_type |
|-----------------|-----------------|
| `claude_code.interaction` | `agent.run.start` / `agent.run.end` |
| `claude_code.llm_request` | `model.call.start` / `model.call.end` |
| `claude_code.tool` | `tool.call.start` / `tool.call.end` |
| `claude_code.tool.blocked_on_user` | `human.approval.request` |
| `claude_code.tool.execution` | `tool.call.end` |
| `claude_code.hook` | `planner.step` |
| Task 子 agent 嵌套 span | `agent.delegate` |

`adapters/claude_code_otel_to_uatr.py` 实现。

## Artifact 引用

prompt / completion / tool arguments 这些字段可能很大或含敏感数据。UATR 推荐：

1. 把完整内容写到 `artifacts/<case_run_id>/<event_id>.json`
2. trace 事件里只放 `content_ref`（相对 `.agent-eval/` 的路径）+ `content_hash`
3. `redacted: true` 表示内容已脱敏

这样 trace 文件本身保持小（单 case 几 KB），可以 Git 追踪；artifact 文件可以 .gitignore 或单独存储。

## 脱敏

`trace_normalizer.py` 的 `redact()` 函数支持 dot-path 脱敏。配置在 adapter yaml 的 `redact_fields`：

```yaml
redact_fields:
  - attributes.tool.arguments.ssn
  - attributes.tool.arguments.id_card
  - output.summary.phone
```

脱敏后的字段值替换成 `<redacted>`，同时 `input.redacted` 或 `output.redacted` 设为 `true`。

## 与 v0 的兼容

v0.5 仍支持读 v0 格式的 trace（扁平事件 + snake_case 字段）。`trace_normalizer.normalize()` 自动检测 `schema_version` 字段：没有就按 v0 处理，转成 UATR 再走后续流程。这意味着 v0 用户升级到 v0.5 后，旧 trace 仍可被 diagnoser/scorer 读取。
