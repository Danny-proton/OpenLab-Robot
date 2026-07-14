# Guide 04 — 测试执行

3 种执行模式 + UATR trace 收集。

## 执行模式

| 模式 | 参数 | 说明 |
|------|------|------|
| mock | --mock | 内置 mock agent，无需后端 |
| http | --base-url URL | HTTP 调用被测 agent |
| openlab | --openlab-bin PATH | subprocess 调 cc-haha |

## 断言验证

执行后自动验证断言：
- exact_match: resp == expected
- contains: expected 关键词都在 resp 里
- regex: 正则匹配
- status_code: HTTP 200
- llm_judge: 响应非空

## UATR Trace

每条用例执行生成 trace 事件：
- agent.run.start
- model.call.start / model.call.end
- tool.call.start / tool.call.end
- agent.run.end

trace 写入 JSONL，含调用结构（span_id / 参数 / 结果 / 延迟）。

## SSE 流式

`--stream` 支持 SSE 流式响应，逐行读取 `data:` 事件。
