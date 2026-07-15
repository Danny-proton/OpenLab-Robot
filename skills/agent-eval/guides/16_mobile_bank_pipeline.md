# Guide 16 — 手机银行 4 阶段流水线 + 桥接

> 本指南解释 agent-eval v2.3.0-mobile-bank 新增的手机银行 4 阶段流水线，以及它如何通过 `excel_to_uatr.py` 桥接器接入主分支的 eval loop。读这份之前建议先读 `01_eval_loop.md`（主分支评测循环）和 `02_trace_contract.md`（UATR trace 合约）。

## 为什么有这条流水线

主分支的 eval loop 假设你已经有了 case YAML（`.agent-eval/cases/<split>.yaml`）和 adapter 配置。但对手机银行 / HTTP agent 这类场景，用户更习惯：

1. 给一段需求文本，让系统**生成测试维度和场景**（Excel）
2. 基于维度**生成详细测试用例**（Excel）
3. **批量执行用例**（HTTP 请求 → Excel 结果）
4. **出测试报告**（HTML + MD）

这是手机银行团队原有的工具链（`generate_requirements.py` / `generate_testcases.py` / `execute_testcases.py` / `generate_report.py`）。本版本保留这条流水线作为**入口**，但修正了原版的两个架构问题：

### 问题 1：脚本内嵌外部 LLM URL

原版 `generate_requirements.py` / `generate_testcases.py` 里：

```python
api_key = os.getenv("LLM_API_KEY", "")
base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
resp = requests.post(base_url + "/chat/completions", ...)
```

这把 prompt 拼装、LLM 调用、JSON 解析、Excel 写入四件事全塞进脚本，且强耦合 OpenAI 端点。换模型 / 换网关 / 离线运行都要改脚本。

**修正**：脚本剥离全部 LLM 代码，只做 JSON → Excel 的机械写入 + list + read。prompt 移到子 skill `skills/requirements-analysis/SKILL.md` 和 `skills/test-case-generator/SKILL.md` 里以文字呈现。Agent（Claude）自己读 prompt、自己生成 JSON，或用 Task 工具委派给子 agent 并行生成。脚本与任何外部模型 URL 完全解耦。

### 问题 2：4 阶段流水线与 agent-eval eval loop 两条平行线

原版 SKILL.md 把 `diagnoser.py` / `multi_judge.py` / `opik_adapter.py` 列为"阶段 5-7"，但根本没接上——4 阶段产出 Excel，eval loop 消费的是 UATR trace + cases YAML，中间没有桥。

**修正**：新增 `excel_to_uatr.py` 桥接器，把阶段 3 的 `execution_results.xlsx`（连同阶段 1/2 的 Excel）翻译成：

- `.agent-eval/traces/<run_id>.jsonl` — UATR 格式 trace（每条用例一组 agent_start / prompt_rendered / model_call / agent_final / agent_end 事件）
- `.agent-eval/cases/<run_id>.yaml` — case 定义（含 expected / business_rules，schema 对齐 `examples/.agent-eval/cases/train.yaml`）
- `.agent-eval/runs/<run_id>.jsonl` — run 记录
- `.agent-eval/scores/<run_id>.json` — 初步机械评分

桥接后，`diagnoser.py --run <run_id>` / `multi_judge.py --run <run_id>` / `opik_adapter.py --run <run_id>` 直接可用。

## 大 skill 套小 skill 套 script 的三层结构

```
agent-eval/SKILL.md                              ← 大 skill：触发、整体能力清单、命令速查
  │
  ├── skills/orchestrator/SKILL.md               ← 小 skill：单次运行内阶段编排
  │     │
  │     ├── skills/requirements-analysis/SKILL.md ← 小 skill：阶段 1 prompt 文字 + Task 工具指示
  │     │     │
  │     │     └── scripts/generate_requirements.py ← script：JSON→Excel 机械写入（零 LLM）
  │     │
  │     ├── skills/test-case-generator/SKILL.md   ← 小 skill：阶段 2 prompt 文字 + Task 工具并行指示
  │     │     │
  │     │     └── scripts/generate_testcases.py    ← script：JSON→Excel 机械写入（零 LLM）
  │     │
  │     ├── skills/test-executor/SKILL.md         ← 小 skill：阶段 3 执行 + 桥接指示
  │     │     │
  │     │     ├── scripts/execute_testcases.py     ← script：纯 HTTP 执行器（零 LLM）
  │     │     └── scripts/excel_to_uatr.py         ← script：Excel→UATR 桥接器（零 LLM）
  │     │
  │     └── skills/test-reporter/SKILL.md         ← 小 skill：阶段 4 报告指示
  │           │
  │           ├── scripts/generate_report.py       ← script：4 阶段汇总报告（零 LLM）
  │           └── scripts/html_report.py           ← script：eval loop 深度报告（主分支，零 LLM）
  │
  └── scripts/diagnoser.py / multi_judge.py / opik_adapter.py / ...  ← 主分支 eval loop 脚本（零 LLM）
```

**职责切分**：

| 层 | 职责 | 是否调 LLM |
|----|------|-----------|
| 大 skill SKILL.md | 触发判定、整体能力清单、命令速查、目录结构 | 否（Agent 自己读） |
| 小 skill SKILL.md | 该阶段的 prompt 文字 + Task 工具指示 + 调哪个脚本 | 否（Agent 自己读，自己生成 JSON） |
| script | 机械 I/O：Excel 读写、HTTP 执行、格式转换、UATR 桥接、诊断打分、报告渲染 | **否（零 LLM，硬规则）** |
| agents/*.md | 9 个 judge 的角色描述 + 评审标准 + 输出格式 | 否（Claude 读后自己扮演，或 Task 委派） |

## 数据流详解

### 阶段 1：需求分析

```
用户需求文本
  │
  ├─→ Agent 读 skills/requirements-analysis/SKILL.md
  │     │
  │     └─→ Agent 调 Task 工具，spawn 子 agent，传入【生成 prompt】+ 需求文本
  │           │
  │           └─→ 子 agent 返回 JSON {dimensions, scenarios, skill_suggestions}
  │
  ├─→ Agent 校验 JSON（剥离 markdown、json.loads、字段校验）
  │
  └─→ Agent 调脚本：cat json | generate_requirements.py --write-stdin --output ...xlsx
        │
        └─→ 脚本写 Excel（3 sheet），stdout 输出 JSON 摘要
```

### 阶段 2：用例生成

```
requirements_analysis.xlsx
  │
  ├─→ Agent 调脚本：generate_testcases.py --read-scenarios --input ...xlsx > /tmp/scenarios.json
  │
  ├─→ Agent 读 skills/test-case-generator/SKILL.md
  │     │
  │     └─→ 若场景 > 10，Agent 切分批次，一条消息内并行调多个 Task 工具
  │           │
  │           └─→ 每个 Task 子 agent 返回 {test_cases: [...]}
  │
  ├─→ Agent 合并 + 校验（tc_id 唯一性、scenario_id 存在性、必填字段）
  │
  └─→ Agent 调脚本：cat merged.json | generate_testcases.py --write-stdin --output ...xlsx
```

### 阶段 3：执行 + 桥接

```
test_cases.xlsx + 用户给的环境信息（URL/headers/body 模板）
  │
  ├─→ execute_testcases.py（纯 HTTP）
  │     │
  │     │  对每条用例：
  │     │    - 替换 body 模板里的 {{列名}} 占位符
  │     │    - POST 到 base-url
  │     │    - 收响应（支持 SSE --stream）
  │     │    - 写一行到 execution_results.xlsx
  │     │
  │     └─→ execution_results.xlsx
  │
  └─→ excel_to_uatr.py（桥接器，纯格式转换）
        │
        │  读 3 个 Excel（requirements + testcases + results）
        │  对每条用例：
        │    - 生成 UATR 事件流（agent_start / prompt_rendered / model_call / agent_final / agent_end）
        │    - 生成 case 定义（含 expected / business_rules）
        │    - 算初步机械评分（task_success / output_schema / latency）
        │
        └─→ .agent-eval/traces/<run_id>.jsonl
            .agent-eval/cases/<run_id>.yaml
            .agent-eval/runs/<run_id>.jsonl
            .agent-eval/scores/<run_id>.json
```

### 阶段 5-7：eval loop（主分支原封不动）

```
run_id（来自阶段 3b 桥接）
  │
  ├─→ diagnoser.py --run <run_id>      → F1-F8 失败归因
  ├─→ multi_judge.py --run <run_id>    → 9 Judge 评审
  ├─→ opik_adapter.py --run <run_id>   → HRPO 根因
  ├─→ reference_optimizer.py --run <run_id> --apply  → reference 注入
  └─→ auto_patcher.py --baseline-run <run_id> --auto-apply  → A/B 全自动优化
```

### 阶段 4：报告

```
3 个 Excel + run_id
  │
  ├─→ generate_report.py    → data/test_report.html + .md（4 阶段汇总）
  ├─→ html_report.py --run <run_id>  → .agent-eval/reports/<run_id>.html（深度，含 F1-F8 / Judge）
  └─→ pdf_report.py（可选） → .agent-eval/reports/<run_id>.pdf
```

## UATR trace 事件（桥接器生成）

桥接器为每条用例生成 5-6 个事件（对齐 `02_trace_contract.md` 的 11 类事件子集）：

| 事件 | step | 说明 |
|------|------|------|
| `agent_start` | 1 | agent 开始处理用例 |
| `prompt_rendered` | 2 | user_input 的 sha256 hash + model=unknown |
| `model_call` | 3 | input/output_tokens 留空（HTTP 黑盒拿不到） |
| `error` | 4（可选） | 仅当有错误信息时 |
| `agent_final` | 4 或 5 | final_answer = 实际响应（截断 4000 字符） |
| `agent_end` | 5 或 6 | status + latency_ms |

**为什么 model_call 的 tokens 留空**：`execute_testcases.py` 是黑盒 HTTP 调用，拿不到 SUT 内部的 token 计数。若需要 token 级 trace，改用 `openlab_robot` adapter（subprocess 调 cc-haha，能拿完整 SDK 消息流）。

## cases YAML schema（桥接器生成）

桥接器生成的 `cases/<run_id>.yaml` 对齐 `examples/.agent-eval/cases/train.yaml`：

```yaml
cases:
  - id: TC-0001
    name: 用例标题
    agent: mobile-bank-sut
    task: 场景描述
    input:
      user_message: "用户输入"
      preconditions: "前置条件"
    expected:
      final_decision:
        contains:
          - "预期结果片段1"
          - "预期结果片段2"
    business_rules:
      must_satisfy:
        - id: DIM-001
          description: "维度名 / 覆盖类型"
    meta:
      scenario_id: SC-001
      dimension_id: DIM-001
      priority: 高
      actual_response: "实际响应（截断 1000 字符）"
```

`assertion_type` 决定 `expected.final_decision` 的形式：
- `contains` → `contains: [片段1, 片段2]`（按 `;` `；` `\n` 拆分）
- `exact` → `equals: 完整文本`
- `regex` → `regex: 正则`
- `schema` / `status_code` / `tool_called` / `business_rule` → 暂降级为 contains

## 桥接后的诊断流程

```bash
# 1. 桥接（阶段 3b）
python scripts/excel_to_uatr.py --requirements data/requirements_analysis.xlsx \
  --testcases data/test_cases.xlsx --results data/execution_results.xlsx \
  --config .agent-eval/config.yaml --variant baseline --label "mobile-bank-001"
# 输出 run_id，例如 20260715-183000-baseline-mobile-bank-001

# 2. F1-F8 诊断（阶段 5）
python scripts/diagnoser.py --config .agent-eval/config.yaml --run 20260715-183000-baseline-mobile-bank-001

# 3. 9 Judge 评审（阶段 6）
python scripts/multi_judge.py --config .agent-eval/config.yaml --run 20260715-183000-baseline-mobile-bank-001 --split train

# 4. HRPO 根因（阶段 7）
python scripts/opik_adapter.py --config .agent-eval/config.yaml --run 20260715-183000-baseline-mobile-bank-001 --optimizer hrpo
```

## 与主分支 adapter 的关系

主分支有 3 个 adapter（`mock` / `spring_ai_http` / `openlab_robot`），本版本的手机银行流水线是第 4 种隐式 adapter（`mobile_bank_http`）：

| Adapter | 调用方式 | 拿到的 trace 粒度 | 适合场景 |
|---------|---------|------------------|---------|
| `mock` | 进程内模拟 | 完整 UATR（11 事件） | demo / CI |
| `spring_ai_http` | HTTP POST | Spring AI EvalTraceAdvisor 吐的 trace | Spring AI agent |
| `openlab_robot` | subprocess 调 cc-haha | 完整 SDK 消息流 → UATR | Claude Code 类 agent |
| **`mobile_bank_http`** | HTTP POST（批量） | 黑盒，仅 agent_start/final/end | 手机银行 HTTP agent，Excel 用例批量执行 |

**区别**：`mobile_bank_http` 是**批量离线评测**——读 Excel 用例表，逐条发请求，收集响应回 Excel，最后桥接。其他 adapter 是**单 case 实时评测**——eval_runner 逐条 case 调 adapter，adapter 即时返回 trace。

**何时用哪个**：
- 用户给的是 Excel 用例表 → 用手机银行流水线（阶段 1-4）
- 用户给的是 case YAML → 直接用主分支 eval_runner + adapter
- 两者可混用：手机银行流水线桥接出的 `cases/<run_id>.yaml` 可作为后续 eval_runner 的输入

## 扩展点

### 加新的生成阶段

若要加"阶段 1.5：SPEC 解析"（从 PRD/SPEC 提取工具列表 / advisor 链 / 业务规则）：

1. 新建 `skills/spec-parser/SKILL.md`，内含完整 prompt 文字 + Task 工具指示
2. 新建 `scripts/spec_parser.py`，只做 JSON → Excel/YAML 机械写入
3. 在 `orchestrator/SKILL.md` 阶段流里插入第 1.5 步
4. 在主 `SKILL.md` 命令速查加一节

### 加新的 adapter

若要加新的 SUT 类型：

1. 在 `scripts/adapters/` 加 `xxx_adapter.py`（实现 `__call__(case_input, case_run_id) -> {final_answer, raw_trace}`）
2. 在 `examples/.agent-eval/adapters/` 加 `xxx.yaml` 配置
3. 在 `guides/14_openlab_robot_adapter.md` 旁边加 `17_xxx_adapter.md`
4. 在主 `SKILL.md` Adapter 节加一行

### 加新的 Judge

若要加新的评审维度（如"合规 Judge"）：

1. 在 `agents/` 加 `compliance-judge.md`，按 `domain-judge.md` 的格式写角色 / 权限 / 输入 / 输出 / 评分规则 / 优先归因的失败类型
2. 在 `multi_judge.py` 的配置里启用
3. 在主 `SKILL.md` 评审 Agent 节加一行

## 常见问题

### Q: 为什么不用主分支的 eval_runner 直接跑手机银行 agent？

A: eval_runner 假设 case YAML 已存在。手机银行团队的习惯是从需求文本开始，Excel 进 Excel 出。4 阶段流水线满足这个习惯，桥接器负责把 Excel 产物翻译成 eval_runner 能消费的格式。两条路都通 eval loop。

### Q: 桥接器生成的 trace 粒度够 diagnoser 用吗？

A: 够。F1-F8 诊断主要看 `final_answer` vs `expected`、`status`、`latency_ms`。黑盒 trace 的 `agent_final` + `agent_end` 已足够触发 F2/F7/F8 归因。F3（工具选择）/ F4（工具参数）/ F5（workflow）需要 tool_call 事件，黑盒拿不到——若需这些维度的诊断，改用 `openlab_robot` adapter。

### Q: 阶段 2 并行 Task 调用会不会让 tc_id 冲突？

A: 不会。每个 Task 子 agent 生成的 tc_id 在它自己的批次内唯一，但跨批次可能重复。Agent 合并时按出现顺序重新编号 TC-0001, TC-0002, ...（见 `skills/test-case-generator/SKILL.md` 第 3 步）。

### Q: 脚本真的完全不调 LLM 吗？

A: 是。`rg -n "LLM_|requests|chat/completions|api_key|base_url" scripts/generate_requirements.py scripts/generate_testcases.py scripts/execute_testcases.py scripts/generate_report.py scripts/excel_to_uatr.py` 应该只在 `execute_testcases.py` 命中 `base_url`——那是 SUT 的 URL，不是 LLM 的。这是硬规则，违反即 bug。
