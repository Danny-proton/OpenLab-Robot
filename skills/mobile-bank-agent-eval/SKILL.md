---
name: mobile-bank-agent-eval
description: "Use proactively when evaluating mobile banking agents. 4-stage pipeline: requirements analysis → test case generation → test execution → report generation. Covers 10 test dimensions (business scenario/workflow/user role/business rules/input context/security/multi-turn state/error recovery/performance/compliance). Supports HTTP + OpenLab Robot + mock execution. Generates HTML report with trace call structure and failure attribution (F1-F8). Trigger: 手机银行测试, agent 评测, 用例生成, 测试执行, 测试报告, mobile bank test, agent evaluation."
allowed-tools: Bash(python *), Bash(python3 *), Bash(ls *), Bash(cat *), Bash(mkdir *), Bash(cp *), Read, Write, Edit, Grep, Glob, AskUserQuestion
---

# 手机银行 Agent 自动评测 Skill

4 阶段自动评测流水线，基于 agent-eval 主轴补充用例生成和执行能力。

## 工作流程（4 阶段）

### 阶段 1: 需求分析

```bash
python ${SKILL_PATH}/scripts/generate_requirements.py \
  --description "用户的需求文本" \
  --output ${SKILL_PATH}/data/requirements_analysis.xlsx
```

生成 10 个测试维度 + 场景到 Excel。支持 `--gherkin` 输出 Gherkin .feature 文件。

### 阶段 2: 测试用例生成

```bash
# 列出维度
python ${SKILL_PATH}/scripts/generate_requirements.py --list ${SKILL_PATH}/data/requirements_analysis.xlsx

# 生成用例
python ${SKILL_PATH}/scripts/generate_testcases.py \
  --input ${SKILL_PATH}/data/requirements_analysis.xlsx \
  --output ${SKILL_PATH}/data/test_cases.xlsx \
  --per-scenario 3
```

支持 `--multi-turn` 生成多轮对话用例，`--dimensions` 指定维度。

### 阶段 3: 测试执行

```bash
# mock 模式（无需后端）
python ${SKILL_PATH}/scripts/execute_testcases.py \
  --input ${SKILL_PATH}/data/test_cases.xlsx \
  --output ${SKILL_PATH}/data/execution_results.xlsx \
  --mock

# HTTP 模式
python ${SKILL_PATH}/scripts/execute_testcases.py \
  --input ${SKILL_PATH}/data/test_cases.xlsx \
  --output ${SKILL_PATH}/data/execution_results.xlsx \
  --base-url http://localhost:8080/api/chat \
  --body '{"messages":[{"role":"user","content":"{{用户输入}}"}]}'

# OpenLab Robot 模式
python ${SKILL_PATH}/scripts/execute_testcases.py \
  --input ${SKILL_PATH}/data/test_cases.xlsx \
  --output ${SKILL_PATH}/data/execution_results.xlsx \
  --openlab-bin /path/to/claude-haha
```

支持 `--stream` SSE 流式，`--cases` 指定用例，`--trace-output` trace 输出路径。

### 阶段 4: 报告生成

```bash
python ${SKILL_PATH}/scripts/generate_report.py \
  --requirements ${SKILL_PATH}/data/requirements_analysis.xlsx \
  --testcases ${SKILL_PATH}/data/test_cases.xlsx \
  --results ${SKILL_PATH}/data/execution_results.xlsx \
  --trace ${SKILL_PATH}/data/trace.jsonl \
  --output ${SKILL_PATH}/data/test_report.html
```

同时生成 .md + .html，HTML 含调用结构树 + 失败归因。

## 10 个测试维度

| 维度 | 覆盖类型 | 说明 |
|------|---------|------|
| DIM-001 | 业务场景覆盖 | 账户查询/转账/理财等典型场景 |
| DIM-002 | 业务流程覆盖 | 正常/替代/异常路径 |
| DIM-003 | 用户角色与意图覆盖 | VIP/普通用户、查询/操作/投诉 |
| DIM-004 | 业务规则与约束覆盖 | 限额/合规/if-then 逻辑 |
| DIM-005 | 输入形态与上下文覆盖 | 错别字/指代/不完整信息 |
| DIM-006 | 安全与边界覆盖 | 注入/越权/数据泄露 |
| DIM-007 | 多轮对话状态覆盖 | 上下文保持/状态迁移 |
| DIM-008 | 异常恢复流程覆盖 | 超时/网络错误后恢复 |
| DIM-009 | 性能与延迟边界覆盖 | 大数据量/高并发 |
| DIM-010 | 合规与监管覆盖 | 适当性管理/信息披露 |

## 执行模式

| 模式 | 参数 | 适用 |
|------|------|------|
| mock | `--mock` | 无后端，用内置 mock agent |
| http | `--base-url URL` | Spring AI / 任意 HTTP agent |
| openlab | `--openlab-bin PATH` | OpenLab Robot (cc-haha) |

## 失败归因（F1-F8 对应）

| 失败类型 | 说明 | 检测条件 |
|---------|------|---------|
| F2.1 | 任务理解失败 | 响应与预期完全不匹配 |
| F5.3 | 服务异常 | 状态码非 200 |
| F7.1 | 输出格式不符 | 正则不匹配 |
| F7.3 | 输出缺关键内容 | contains 断言失败 |
| F8.1 | 执行超时 | timeout |

## 环境变量

- `LLM_API_KEY`: LLM API key（有则调真实 LLM，无则 mock）
- `LLM_MODEL`: 模型名（默认 gpt-4o）
- `LLM_BASE_URL`: API 地址（默认 OpenAI）

无 API key 时自动用 mock LLM，全流程仍可跑通。

## 评审 Agent（4 个）

Claude 根据 description 自动委托：
- `requirements-analyst` — 需求分析
- `test-case-designer` — 用例设计
- `test-executor` — 用例执行
- `report-writer` — 报告生成
