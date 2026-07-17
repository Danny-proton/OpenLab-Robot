---
name: test-executor
description: "用例执行子 skill（阶段 3）。读取测试用例 Excel，根据环境信息执行 HTTP 请求收集响应；执行完调用 excel_to_uatr.py 桥接器，把 Excel 结果翻译成 agent-eval 的 UATR trace + cases YAML，接入主分支的 F1-F8 诊断 / 多 Judge / 优化循环。脚本不调任何外部 LLM。"
allowed-tools: Bash(python *), Bash(python3 *), Read, Write, Edit, Task, AskUserQuestion
---

# 测试用例执行子 skill（阶段 3 / 4）

> **架构定位**：这是"大 skill 套小 skill 套 script"结构里的**小 skill** 层。
> 本阶段**没有生成性 LLM 工作**——执行是机械的 HTTP 调用，桥接是机械的格式转换。
> 所以本子 skill 不需要 Task 工具委派，直接调两个机械脚本：
> 1. `execute_testcases.py` —— 纯 HTTP 执行器（读用例 Excel → 发请求 → 收响应 → 写结果 Excel）
> 2. `excel_to_uatr.py` —— 桥接器（结果 Excel → UATR trace + cases YAML），把数据接入 agent-eval 主分支的 eval loop
>
> 两个脚本零 LLM 调用。

## 你的输入

- `data/test_cases.xlsx`（阶段 2 产出）
- 用户提供的被测环境信息（URL / method / headers / body 模板 / timeout / 是否 SSE 流式）

## 你的输出

- `data/execution_results.xlsx`（用例 ID / 状态码 / 响应时间 / 实际响应 / 结果 / 错误信息）
- `.agent-eval/traces/<run_id>.jsonl`（UATR 格式，桥接产出）
- `.agent-eval/cases/<run_id>.yaml`（cases YAML，桥接产出，供 diagnoser/multi_judge 消费）
- `.agent-eval/runs/<run_id>.jsonl`（run 记录，桥接产出）

## 第 1 步：向用户收集环境信息

用 `AskUserQuestion` 问：

1. **目标环境 URL**（如 `http://localhost:8080/api/chat`）
2. **请求方法**（默认 POST）
3. **请求头 JSON**（默认 `{"Content-Type": "application/json"}`，如需鉴权让用户补 `Authorization`）
4. **请求体 JSON 模板**（含 `{{列名}}` 占位符，如 `{{用户输入}}` 会被替换为用例 Excel 中对应列内容）
5. **超时秒数**（默认 120）
6. **是否 SSE 流式响应**（是则加 `--stream`）
7. **是否上传了修改后的测试用例 Excel**（用户可能手工调整过用例，若是则用用户给的路径）

body 模板示例：
```json
{"messages":[{"role":"user","content":"{{用户输入}}"}]}
```

`{{用户输入}}` / `{{用例 ID}}` / `{{场景引用}}` 等占位符会被 `execute_testcases.py` 替换为用例 Excel 中对应列的内容。

## 第 2 步：执行测试用例

```bash
python ${SKILL_PATH}/scripts/execute_testcases.py \
  --input "${SKILL_PATH}/data/test_cases.xlsx" \
  --output ${SKILL_PATH}/data/execution_results.xlsx \
  --base-url "URL" \
  --method POST \
  --timeout 120 \
  --headers '{"Content-Type":"application/json"}' \
  --body '{"messages":[{"role":"user","content":"{{用户输入}}"}]}' \
  [--cases TC-0001,TC-0002] \
  [--stream]
```

可选参数：
- `--cases TC-0001,TC-0002`：只跑指定用例（调试时用）
- `--stream`：SSE 流式响应模式，逐行读取 `data:` 事件并累加内容

脚本 stdout 输出执行摘要（总数 / 成功 / 失败 / 平均响应时间），展示给用户。

## 第 3 步：桥接到 agent-eval eval loop（关键演进点）

> 这一步是 mobile-bank 分支**重新接回**主分支能力的桥。没有它，4 阶段流水线和 agent-eval 的 F1-F8 / 多 Judge / 优化器就是两条平行线。

调用桥接器，把执行结果 Excel 翻译成 agent-eval 主分支能消费的 UATR trace + cases YAML：

```bash
python ${SKILL_PATH}/scripts/excel_to_uatr.py \
  --requirements ${SKILL_PATH}/data/requirements_analysis.xlsx \
  --testcases ${SKILL_PATH}/data/test_cases.xlsx \
  --results ${SKILL_PATH}/data/execution_results.xlsx \
  --config .agent-eval/config.yaml \
  --variant baseline \
  --label "mobile-bank-$(date +%Y%m%d-%H%M%S)"
```

桥接器产出（写入 `.agent-eval/` 标准目录）：
- `traces/<run_id>.jsonl` —— 每条用例一条 UATR 事件流（agent_start / model_call / tool_call / agent_final / agent_end）
- `cases/<run_id>.yaml` —— 从 test_cases.xlsx 转换的 case 定义（含 expected / business_rules）
- `runs/<run_id>.jsonl` —— run 记录（case_id / status / latency_ms / final_answer）
- `scores/<run_id>.json` —— 初步机械评分（task_success / output_schema / latency）

`run_id` 形如 `20260715-183000-baseline-mobile-bank-183000`，会被后续 diagnoser/multi_judge/optimizer 复用。

## 第 4 步：进入 agent-eval 诊断（阶段 5，由 orchestrator 衔接）

桥接完成后，orchestrator 会依次调用（这些是主分支原封不动的能力）：

```bash
# F1-F8 失败归因
python ${SKILL_PATH}/scripts/diagnoser.py --config .agent-eval/config.yaml --run <run_id>

# 9 Judge 评审
python ${SKILL_PATH}/scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id> --split train

# HRPO 根因
python ${SKILL_PATH}/scripts/opik_adapter.py --config .agent-eval/config.yaml --run <run_id> --optimizer hrpo
```

详见主 SKILL.md 的"阶段 5-7"。

## 重要约束

- ❌ 本子 skill 不许调任何外部 LLM API
- ❌ execute_testcases.py 只发 HTTP 请求到**用户指定的被测环境**，不调任何 LLM API
- ✅ 桥接器 excel_to_uatr.py 是纯格式转换，无 LLM
- ✅ 执行 + 桥接完成后，数据流交给 agent-eval 主分支的机械脚本和 9 个 judge agent
