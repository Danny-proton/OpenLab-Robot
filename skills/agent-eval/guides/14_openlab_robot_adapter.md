# Guide 14 — OpenLab Robot Adapter

OpenLab Robot 是基于 cc-haha（Claude Code 复现）的执行机。本 adapter 让 agent-eval 能评测 OpenLab Robot / cc-haha / Claude Code 类的 agent。

## 工作原理

```
agent-eval runner
    │
    │ case.input.user_message
    ▼
openlab_robot_adapter.py
    │
    │ subprocess 调用
    ▼
./bin/claude-haha --print --verbose \
    --input-format stream-json --output-format stream-json \
    --session-id <uuid> --permission-mode bypassPermissions
    │
    │ stdin: 一条 NDJSON user 消息
    │ stdout: NDJSON SDK 消息流
    ▼
sdk_to_uatr() 转换
    │
    │ SDK 消息 → UATR 事件
    ▼
agent-eval scorer / diagnoser / multi_judge
```

## 安装 cc-haha

```bash
# 1. 安装 Bun
curl -fsSL https://bun.sh/install | bash

# 2. 克隆 cc-haha（你们改名为 OpenLab Robot）
git clone https://github.com/NanmiCoder/cc-haha.git
cd cc-haha
bun install
cp .env.example .env

# 3. 配置 API key
echo 'ANTHROPIC_AUTH_TOKEN=sk-your-token' >> .env

# 4. 测试
./bin/claude-haha -p "hello"
```

## 配置 adapter

修改 `.agent-eval/config.yaml`：

```yaml
adapter: openlab_robot
```

修改 `.agent-eval/adapters/openlab_robot.yaml`：

```yaml
type: openlab_robot
bin: /path/to/cc-haha/bin/claude-haha   # 改成你的路径
workdir: /tmp/openlab-work               # agent 工作目录
env:
  ANTHROPIC_AUTH_TOKEN: sk-your-token
  ANTHROPIC_MODEL: claude-sonnet-4-20250514
permission_mode: bypassPermissions
max_turns: 20
max_budget_usd: 1.0
timeout_s: 600
allowed_tools: []  # 空 = 全部允许
```

## SDK 消息 → UATR 映射

cc-haha 的 stream-json 输出是 NDJSON，每行一条 SDK 消息。adapter 转换规则：

| SDK 消息 | UATR 事件 | 说明 |
|---------|-----------|------|
| `system.init` | `agent.run.start` | 会话启动，含 tools/model/cwd |
| `assistant` + `tool_use` block | `tool.call.start` | 模型决定调工具 |
| `tool_progress` | (合并到 tool.call.end) | 工具执行进度 |
| `user` + `tool_result` block | `tool.call.end` | 工具返回结果 |
| `assistant` + `text` block | `model.call.end` | 模型文本输出 |
| `system.hook_*` | `planner.step` | Hook 生命周期 |
| `result.success` | `agent.run.end` | 最终成功结果 |
| `result.error_*` | `agent.run.end` (status=error) | 最终失败结果 |

## 评测 Claude Code skill

OpenLab Robot adapter 特别适合评测 Claude Code skill 本身：

1. 在 workdir 下放你的 `.claude/skills/<skill-name>/SKILL.md`
2. case 的 `user_message` 写触发 skill 的问题
3. case 的 `expected_tools` 写期望 skill 调用的工具
4. 跑 `eval_runner.py`，adapter 会调 cc-haha 执行，trace 自动转 UATR

```yaml
# 评测 Claude Code skill 的 case 示例
- id: skill_trigger_test
  name: 测试 risk-review skill 是否触发
  input:
    user_message: "帮我审查这个贷款申请的风险"
  expected:
    final_decision:
      contains: ["流水波动", "负债", "担保"]
  expected_tools:
    required: [analyzeCashflow, checkDebtRatio]  # skill 应调用的工具
    forbidden: [approveLoanDirectly]
```

## 权限模式

cc-haha 支持 5 种权限模式，评测建议用 `bypassPermissions`：

| 模式 | 说明 | 评测适用 |
|------|------|---------|
| default | 每个工具调用都问权限 | ❌ 会卡住 |
| acceptEdits | 自动接受文件编辑 | ⚠️ 部分场景 |
| plan | 只规划不执行 | ❌ 不调工具 |
| **bypassPermissions** | 跳过所有权限检查 | ✅ 评测沙箱用 |

## 成本控制

cc-haha 支持 `--max-turns` 和 `--max-budget-usd`，adapter 透传：

```yaml
max_turns: 20          # 最多 20 轮（防止死循环）
max_budget_usd: 1.0    # 最多花 1 美元（防止烧钱）
```

超出限制时 cc-haha 会返回 `result.error_max_turns` 或 `result.error_max_budget_usd`，adapter 会标记为 `status: error`。

## 故障排查

**`bin_not_found` 错误**：
- 检查 `bin` 路径是否正确
- 检查 cc-haha 是否 `bun install` 过

**`timeout` 错误**：
- 增大 `timeout_s`
- 或减小 `max_turns`

**`no_result` 错误**：
- 检查 API key 是否有效
- 检查 `ANTHROPIC_BASE_URL` 是否可达
- 看 stderr 日志（adapter 会返回 stderr 前 1000 字符）

**trace 事件很少**：
- 确认 `--verbose` 已加（adapter 自动加）
- 确认 `--output-format stream-json`（adapter 自动加）

## 与其他 adapter 对比

| adapter | 适用 agent | 调用方式 | trace 来源 |
|---------|-----------|---------|-----------|
| mock | 测试 pipeline | 内存模拟 | mock 生成 |
| http (spring_ai_http) | Spring AI agent | HTTP POST | 后端返回 |
| **openlab_robot** | **cc-haha / Claude Code** | **subprocess CLI** | **stream-json stdout** |
