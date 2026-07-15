---
name: test-executor
description: "用例执行子 skill。读取测试用例 Excel，根据环境信息执行 HTTP 请求。"
---

# 测试用例执行

先向用户询问：
- 目标环境 URL、请求头、请求方法（默认 POST）、请求体 JSON 模板、超时时间
- 被测接口是否为 SSE 流式响应（如果是，添加 --stream 参数）
- 是否上传了修改后的测试用例 Excel

按用户提供的信息执行：
```bash
python {SKILL_PATH}/scripts/execute_testcases.py \
  --input "用例文件路径" \
  --output {SKILL_PATH}/data/execution_results.xlsx \
  --base-url "URL" [--method POST] [--timeout 120] \
  --headers '{"Content-Type":"application/json"}' \
  --body '{"messages":[{"role":"user","content":"{{请求输入}}"}]}' \
  [--cases TC-0001,TC-0002] [--stream]
```

`{{列名}}` 会被替换为测试用例 Excel 中对应列的内容。
将工具返回的 stdout 直接作为回复。
