---
name: agent-eval-v1.1
description: "Agent 评测与优化（V1.1 用例自优化版）。当用户要测试、诊断、优化、A/B 验证、对比 Agent 行为、工具调用、工作流质量、业务规则合规、输出格式、skill 触发、或用例自优化时使用。覆盖 OpenLab Robot (cc-haha) / Claude Code skill / Spring AI agent / 手机银行 HTTP agent。支持 4 阶段流水线（需求分析→用例生成→执行→报告）+ F1-F8 失败归因 + HRPO 层次化根因 + reference 自动注入 + auto_patcher 全自动优化 + 【V1.1 新增】用例自优化（12维质量评分+mutation kill matrix+错误分布分析+迭代报告）。即使用户只提一个组件（如'工具调用错了'）也触发，因为框架把 prompt/tool schema/tool policy/workflow/memory/skill 作为独立优化目标，同时把测试用例本身也作为可优化对象。"
allowed-tools: Bash(python *), Bash(python3 *), Bash(git *), Bash(ls *), Bash(cat *), Bash(mkdir *), Bash(cp *), Bash(mv *), Bash(diff *), Bash(wc *), Bash(head *), Bash(tail *), Read, Write, Edit, Grep, Glob, Task, AskUserQuestion
---

# Agent 评测与优化 Skill V1.1（用例自优化版）

你的职责是**评测并改进一个 Agent 系统**，不是只改 prompt。V1.1 同时把**测试用例本身**也作为可优化对象。

## 这是哪个版本

本 skill 是 **agent-eval v1.1.0**（用例自优化版），在 v2.3.0-mobile-bank 基础上演进而来（**演进，不是重写**）：

- ✅ **保留** v2.3.0 全部能力：4 阶段流水线、桥接器、9 个 judge agent、F1-F8 失败归因、HRPO 根因、reference 注入、auto_patcher、ask_setup 向导、SideCar、memory_kb、报告管理、Dashboard、CI 回归、3 个 adapter
- ➕ **【V1.1 核心】用例自优化**：业界空白能力。完成一轮评测后自动迭代测试用例集（改测试本身，不改被测 Agent）。包含 12 维质量评分 + mutation kill matrix + 错误分布分析 + spec 缺口识别 + 增强/修改/废弃建议 + 迭代报告
- ➕ **吸收 test-design-agent-raw 成熟设计**：UC 15 字段块 + testspec 4 表（测试对象/操作/数据/关系）+ 16 项自检表 + 7 测试方法库
- ➕ **mock 系统扩展**：支持 mock_config 配置 8 种失败触发模式（skip_tool/repeat_tool/wrong_param/empty_result/hallucinate/redundant/no_memory/success）
- ➕ **12 维质量评分**：9 标准 + 3 Agent 专属（工具覆盖率/工作流覆盖率/记忆覆盖率）
- ➕ **双闭环**：prompt 自优化（改 Agent）+ 用例自优化（改测试）正交运行
- ➕ **【v1.1.1】报告统一门户**：`report_portal.py` 把散落各处的报告/进度/迭代/质量分聚合到单 HTML 5 页网站（Overview/Reports/Progress/Iterations/Quality），深色玻璃态 + 悬浮动效
- ➕ **【v1.1.1】进度埋点**：`progress_tracker.py` + sidecar 改造，9 步评测流程每步 running/completed/failed 持久化到 `progress.jsonl`，session_id 自动续接，门户实时聚合时间线

## 目录结构（大 skill 套小 skill 套 script）

```
agent-eval-v1.1/                         ← 大 skill（V1.1 编排 + 入口）
├── SKILL.md                             ← 本文件
├── VERSION.md                           ← 版本历史（含 v1.1.0）
├── skills/                              ← 小 skill（每阶段一个，含 prompt 文字 + Task 工具指示）
│   ├── orchestrator/SKILL.md            ← 编排：按序驱动 4 阶段 + 桥接 + eval loop + 【V1.1】阶段4.5用例自优化
│   ├── requirements-analysis/SKILL.md   ← 阶段1: 需求分析 + 【V1.1】UC 15字段块 + testspec 4表
│   ├── test-case-generator/SKILL.md     ← 阶段2: 用例生成 + 【V1.1】7方法库 + 20项自检 + 五层断言
│   ├── test-executor/SKILL.md           ← 阶段3: 调 execute_testcases.py + excel_to_uatr.py 桥接
│   ├── test-reporter/SKILL.md           ← 阶段4: 调 generate_report.py + html_report.py
│   └── test-case-self-optimization/SKILL.md  ← 【V1.1 新增】阶段4.5: 用例自优化编排
├── scripts/                             ← 只做机械工作（零 LLM 调用）
│   ├── generate_requirements.py         ← 阶段1 机械层: JSON→Excel + list + read
│   ├── generate_testcases.py            ← 阶段2 机械层: JSON→Excel + list + read-scenarios
│   ├── execute_testcases.py             ← 阶段3a: 纯 HTTP 执行器（读 Excel→发请求→写 Excel）
│   ├── excel_to_uatr.py                 ← 阶段3b: 桥接器（Excel→UATR trace + cases YAML + score）
│   ├── generate_report.py               ← 阶段4a: 4 阶段汇总报告（MD + HTML）
│   ├── eval_runner.py                   ← 主分支: 通用执行器 + scaffold
│   ├── diagnoser.py                     ← 主分支: F1-F8 失败归因
│   ├── multi_judge.py                   ← 主分支: 9 Judge 评审
│   ├── opik_adapter.py                  ← 主分支: HRPO 层次化根因
│   ├── reference_optimizer.py           ← 主分支: reference 自动注入
│   ├── auto_patcher.py                  ← 主分支: A/B 全自动优化
│   ├── html_report.py / pdf_report.py   ← 主分支: 深度报告
│   ├── dashboard.py / report_manager.py ← 主分支: Dashboard + 报告 CRUD
│   ├── ask_setup.py / sidecar.py / memory_kb.py  ← 主分支: 向导 + 状态 + 记忆
│   ├── ci_regression.py / abtest.py / mutator.py / scorer.py / ...  ← 主分支其余
│   ├── case_io.py                       ← 【V1.1 新增】cases YAML 读写（保留完整 schema）
│   ├── case_quality_checker.py          ← 【V1.1 新增】12 维质量评分
│   ├── case_optimizer.py                ← 【V1.1 新增】用例自优化核心（错误分布+缺口+建议+apply）
│   ├── mutation_generator.py            ← 【V1.1 新增】变异 + kill matrix
│   ├── case_iteration_report.py         ← 【V1.1 新增】迭代报告 MD + HTML（v1.1.1 深色玻璃态重构）
│   ├── progress_tracker.py              ← 【v1.1.1 新增】进度事件持久化 + timeline 聚合
│   ├── report_portal.py                 ← 【v1.1.1 新增】统一门户（5 页 + SVG 图表 + 客户端筛选）
│   └── adapters/                        ← adapter（mock / spring_ai_http / openlab_robot）
├── agents/                              ← 主分支 9 个评审 Agent（保留）
├── guides/                              ← 主分支 15 篇 + guide 16 + 【V1.1】guide 17 用例自优化
├── docs/                                ← 主分支 + 【V1.1】DELTA/PRD_REQUIREMENT_TESTDESIGN/PRD_MOCK_SYSTEM
├── examples/.agent-eval/                ← 配置示例（【V1.1】8 条用例 + mock_config）
└── data/                                ← 运行产物（Excel/HTML/MD + 【V1.1】proposals/iterations/backups）
```

## 两条数据流（本版本的核心架构）

### 数据流 A：手机银行 4 阶段流水线（入口，Excel I/O）

```
用户需求文本
  │
  ▼  阶段1 requirements-analysis 子 skill
  │  （prompt 在子 skill，Agent 用 Task 工具生成 JSON，generate_requirements.py 写 Excel）
  ▼
requirements_analysis.xlsx
  │
  ▼  阶段2 test-case-generator 子 skill
  │  （prompt 在子 skill，Agent 用 Task 工具并行生成 JSON，generate_testcases.py 写 Excel）
  ▼
test_cases.xlsx
  │
  ▼  阶段3a test-executor 子 skill
  │  （execute_testcases.py 纯 HTTP 执行器，无 LLM）
  ▼
execution_results.xlsx
  │
  ▼  阶段3b 桥接器 excel_to_uatr.py（纯格式转换，无 LLM）
  ▼
UATR trace + cases YAML + runs + scores  ──→  接入数据流 B
```

### 数据流 B：agent-eval eval loop（主分支原封不动的能力）

```
UATR trace + cases YAML（来自数据流 A 桥接，或 eval_runner.py 直接跑）
  │
  ▼  diagnoser.py          → F1-F8 失败归因
  ▼  multi_judge.py        → 9 Judge 评审（Claude 读 agents/*.md 自行扮演或 Task 委派）
  ▼  opik_adapter.py       → HRPO 层次化根因
  ▼  reference_optimizer.py → reference 自动注入
  ▼  auto_patcher.py       → A/B 全自动优化
  ▼  html_report.py / pdf_report.py → 深度报告
  ▼  dashboard.py          → 多轮趋势
  ▼  ci_regression.py      → CI 持续回归
```

**两条数据流在阶段 3b 桥接器处汇合**。这是本版本相对主分支的关键演进：手机银行流水线不再孤立，而是把执行结果喂给主分支的全部诊断/优化能力。

## 完整工作循环

> 💬 = 需要用户交互确认 | ⚡ = 自动执行 | 📊 = 生成产物
> 阶段编号 1-4 是手机银行流水线，5-8 是主分支 eval loop（阶段 4 报告生成在最后）

1. **启动前** 💬：跑 `ask_setup.py --stage startup --emit-questions` 收集缺失信息；若无 `.agent-eval/config.yaml` 先 `eval_runner.py --scaffold .`；调 `sidecar.py --status running --step 1`
2. **阶段 1 需求分析** 💬⚡：读 `skills/requirements-analysis/SKILL.md` → Agent 用 Task 工具生成维度/场景 JSON → `generate_requirements.py --write-stdin` 写 Excel → `sidecar.py --status completed --step 1`
3. **阶段 2 用例生成** 💬⚡：读 `skills/test-case-generator/SKILL.md` → Agent 用 Task 工具并行生成用例 JSON → `generate_testcases.py --write-stdin` 写 Excel → `sidecar.py --status completed --step 2`
4. **阶段 3 用例执行 + 桥接** 💬⚡：读 `skills/test-executor/SKILL.md` → `execute_testcases.py` 发 HTTP → `excel_to_uatr.py` 桥接成 UATR trace → `sidecar.py --status completed --step 3 --run-id <run_id>`
5. **阶段 5 F1-F8 诊断** ⚡：`diagnoser.py --config .agent-eval/config.yaml --run <run_id>` → `sidecar.py --status completed --step 5`
6. **阶段 6 多 Judge 评审** 💬⚡：`ask_setup.py --stage judge --emit-questions` 确认启用的 Judge → `multi_judge.py --config .agent-eval/config.yaml --run <run_id> --split train`
7. **阶段 7 优化迭代** 💬⚡：`ask_setup.py --stage optimize --emit-questions` → `opik_adapter.py --optimizer hrpo` → `reference_optimizer.py --apply` → `auto_patcher.py --auto-apply`
8. **阶段 4 报告生成** 📊：读 `skills/test-reporter/SKILL.md` → `generate_report.py`（4 阶段汇总）+ `html_report.py`（eval loop 深度）+ 可选 `pdf_report.py` / `dashboard.py`

> **阶段编号说明**：报告生成编号为 4（手机银行流水线第 4 步），但实际执行在阶段 5-7 之后，因为它要汇总诊断 + Judge 结果。orchestrator 子 skill 负责这个顺序。

### 交互说明

每一步执行前，Claude 应先调对应 `ask_setup.py --stage <stage> --emit-questions`，把返回的 questions 用 `AskUserQuestion` 弹窗问用户。用户选择后可再跑 `ask_setup.py --stage <stage>`（不带 `--emit-questions`）持久化到 `config.yaml`。也可用 `--non-interactive` 跳过弹窗，全部默认，适合 CI/CD。

### SideCar 状态面板 + 进度埋点（v1.1.1）

每步开始/结束调 `scripts/sidecar.py` 输出 JSON，可据此渲染进度卡片。**v1.1.1 起**：sidecar 同时把事件持久化到 `.agent-eval/data/progress.jsonl`（通过 `progress_tracker.emit()`），session_id 自动续接，无需改调用方式：

```bash
python scripts/sidecar.py --status running --step 2 --step-name "用例生成"
python scripts/sidecar.py --status completed --step 2 --run-id <run_id> --score 0.723

# 查看进度时间线 / 汇总（v1.1.1）
python scripts/progress_tracker.py --config .agent-eval/config.yaml timeline
python scripts/progress_tracker.py --config .agent-eval/config.yaml summary
```

进度数据被 `report_portal.py` 的 Progress 页聚合，呈现 9 步水平时间线 + 每步耗时 tooltip + 平均耗时条形图。

### KnowledgeCycle 记忆

用户偏好和最佳实践自动写入 `.agent-eval/.memory/`：

```bash
python scripts/memory_kb.py --remember preference --key adapter --value mobile_bank_http
python scripts/memory_kb.py --recall preference
```

## 命令速查

所有脚本在 `${SKILL_DIR}/scripts/` 下。`${SKILL_DIR}` 是本 skill 根目录。

### 阶段 1：需求分析（手机银行流水线）

> prompt 在 `skills/requirements-analysis/SKILL.md`，Agent 用 Task 工具生成 JSON，脚本只写 Excel

```bash
# 列出维度
python ${SKILL_DIR}/scripts/generate_requirements.py --list ${SKILL_DIR}/data/requirements_analysis.xlsx

# 读回 JSON（供下游消费）
python ${SKILL_DIR}/scripts/generate_requirements.py --read ${SKILL_DIR}/data/requirements_analysis.xlsx

# 写 Excel（Agent 把生成的 JSON 通过 stdin 传入）
cat agent_generated.json | python ${SKILL_DIR}/scripts/generate_requirements.py --write-stdin --output ${SKILL_DIR}/data/requirements_analysis.xlsx
```

### 阶段 2：测试用例生成（手机银行流水线）

> prompt 在 `skills/test-case-generator/SKILL.md`，Agent 用 Task 工具并行生成 JSON，脚本只写 Excel

```bash
# 列出维度（决定生成范围）
python ${SKILL_DIR}/scripts/generate_testcases.py --list --input ${SKILL_DIR}/data/requirements_analysis.xlsx

# 读场景 JSON（喂给 Task 子 agent）
python ${SKILL_DIR}/scripts/generate_testcases.py --read-scenarios --input ${SKILL_DIR}/data/requirements_analysis.xlsx [--dimensions DIM-001,DIM-002]

# 写用例 Excel（Agent 把生成的 JSON 通过 stdin 传入）
cat cases.json | python ${SKILL_DIR}/scripts/generate_testcases.py --write-stdin --input ${SKILL_DIR}/data/requirements_analysis.xlsx --output ${SKILL_DIR}/data/test_cases.xlsx
```

### 阶段 3a：测试用例执行（手机银行流水线，纯 HTTP）

```bash
python ${SKILL_DIR}/scripts/execute_testcases.py \
  --input ${SKILL_DIR}/data/test_cases.xlsx \
  --output ${SKILL_DIR}/data/execution_results.xlsx \
  --base-url "http://localhost:8080/api/chat" \
  --method POST --timeout 120 \
  --headers '{"Content-Type":"application/json"}' \
  --body '{"messages":[{"role":"user","content":"{{用户输入}}"}]}'
# 可选: --cases TC-0001,TC-0002  --stream
```

`{{列名}}` 会被替换为用例 Excel 中对应列的内容。

### 阶段 3b：桥接到 eval loop（关键演进点）

```bash
python ${SKILL_DIR}/scripts/excel_to_uatr.py \
  --requirements ${SKILL_DIR}/data/requirements_analysis.xlsx \
  --testcases ${SKILL_DIR}/data/test_cases.xlsx \
  --results ${SKILL_DIR}/data/execution_results.xlsx \
  --config .agent-eval/config.yaml \
  --variant baseline --label "mobile-bank-$(date +%Y%m%d-%H%M%S)"
```

产出：`.agent-eval/traces/<run_id>.jsonl` + `cases/<run_id>.yaml` + `runs/<run_id>.jsonl` + `scores/<run_id>.json`

### 阶段 4：报告生成（手机银行流水线汇总 + eval loop 深度）

```bash
# 4 阶段汇总报告（MD + HTML）
python ${SKILL_DIR}/scripts/generate_report.py \
  --requirements ${SKILL_DIR}/data/requirements_analysis.xlsx \
  --testcases ${SKILL_DIR}/data/test_cases.xlsx \
  --results ${SKILL_DIR}/data/execution_results.xlsx \
  --output ${SKILL_DIR}/data/test_report.md

# eval loop 深度报告（含 F1-F8 / 9 Judge）
python ${SKILL_DIR}/scripts/html_report.py --config .agent-eval/config.yaml --run <run_id>

# 可选 PDF
python ${SKILL_DIR}/scripts/pdf_report.py --config .agent-eval/config.yaml --run <run_id> --page-size A4
```

### 阶段 5-7：agent-eval eval loop（主分支原封不动）

```bash
# 首次初始化（若无 .agent-eval/）
python ${SKILL_DIR}/scripts/eval_runner.py --scaffold .

# F1-F8 诊断
python ${SKILL_DIR}/scripts/diagnoser.py --config .agent-eval/config.yaml --run <run_id>

# 9 Judge 评审
python ${SKILL_DIR}/scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id> --split train

# HRPO 根因
python ${SKILL_DIR}/scripts/opik_adapter.py --config .agent-eval/config.yaml --run <run_id> --optimizer hrpo

# reference 注入
python ${SKILL_DIR}/scripts/reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply

# 全自动 A/B 优化
python ${SKILL_DIR}/scripts/auto_patcher.py --config .agent-eval/config.yaml --baseline-run <run_id> --split regression --auto-apply

# Dashboard
python ${SKILL_DIR}/scripts/dashboard.py --config .agent-eval/config.yaml

# CI 回归
python ${SKILL_DIR}/scripts/ci_regression.py --config .agent-eval/config.yaml --ci
```

### 报告管理（CRUD + 检索 + 统一门户）

```bash
python ${SKILL_DIR}/scripts/report_manager.py --config .agent-eval/config.yaml list --daily
python ${SKILL_DIR}/scripts/report_manager.py --config .agent-eval/config.yaml search --run <run_id>
python ${SKILL_DIR}/scripts/report_manager.py --config .agent-eval/config.yaml export <report_id> <路径>
python ${SKILL_DIR}/scripts/report_manager.py --config .agent-eval/config.yaml delete <report_id>

# v1.1.1 统一门户：聚合报告/进度/迭代/质量分到单 HTML 5 页网站
python ${SKILL_DIR}/scripts/report_portal.py --config .agent-eval/config.yaml
# 产出 .agent-eval/reports/portal.html，浏览器打开即可
```

## 失败类型 F1-F8（主分支保留）

| 代码 | 名称 | 修改对象 |
|------|------|---------|
| F1 | Skill 触发失败 | SKILL.md description |
| F2 | 任务理解失败 | prompt |
| F3 | 工具选择失败 | tool schema + policy |
| F4 | 工具参数失败 | tool schema + memory |
| F5 | Workflow 失败 | advisor 链 |
| F6 | Memory 失败 | memory + prompt |
| F7 | 输出失败 | prompt + memory |
| **F8** | **执行冗余失败** | **reference（核心：缩短轮数）** |

## Adapter（主分支保留 + 手机银行扩展）

- `mock` — 内置，无需后端，适合 demo / CI
- `spring_ai_http` — Spring AI agent HTTP 调用
- `openlab_robot` — OpenLab Robot (cc-haha) subprocess 调用
- **`mobile_bank_http`**（本版本隐式）— `execute_testcases.py` 是第 4 种 adapter，专做手机银行 HTTP agent 的批量用例执行；与 spring_ai_http 的区别：它读 Excel 用例表批量发请求、收集响应回 Excel，适合离线评测

## 评审 Agent（9 个，主分支保留）

Claude 根据 `agents/*.md` 的 description 自动委托（可用 Task 工具 spawn 子 agent 并行）：

- 6 个规则型 Judge：domain / tool-trace / workflow / faithfulness / regression / safety
- 3 个决策型：gatekeeper / optimizer-planner / patch-writer

## 重要规则（主分支保留 + 本版本强化）

- **默认绝不能只改 system prompt**。Prompt / tool schema / tool policy / workflow / memory / skill 要分开考虑
- **接受规则是机械的**：train 提升 ≥0.03 + regression 零硬失败 + 零 forbidden tool + 无新失败 + latency 不超 1.5x
- **必须记录证据**：每条诊断引用 case_id + trace_id + event
- **patch 越小越好**
- **SafetyJudge veto 强制**
- **【本版本强化】脚本零 LLM**：`scripts/` 下任何脚本不得 `import requests` 调外部 LLM API（OpenAI / DeepSeek / 自建模型 URL 一律禁止）。所有生成性 LLM 工作由 Agent（Claude）自己完成，或用 Task 工具委派给子 agent。脚本只做 I/O、格式转换、机械计算
- **【本版本强化】prompt 在子 skill**：4 阶段流水线的 prompt 全部在 `skills/*/SKILL.md` 里以文字呈现，不埋在脚本里
- **【本版本强化】桥接而非重写**：mobile-bank Excel 流水线通过 `excel_to_uatr.py` 接入主分支 eval loop，不复制主分支的诊断/优化逻辑
- **【V1.1 新增】双闭环优化**：prompt 自优化（改被测 Agent，阶段5-7）+ 用例自优化（改测试本身，阶段4.5）正交运行
- **【V1.1 新增】用例也是可优化对象**：cases YAML 的 add/modify/deprecate/spec_changes 由 case_optimizer 基于规则生成，创造性内容由 Agent 完成

## V1.1 用例自优化命令速查（本次重点）

```bash
# 12 维质量检查
python ${SKILL_DIR}/scripts/case_quality_checker.py --config .agent-eval/config.yaml --split train

# 变异 kill matrix（6 类变异）
python ${SKILL_DIR}/scripts/mutation_generator.py --config .agent-eval/config.yaml --latest --split train

# 用例自优化（dry-run，只生成建议）
python ${SKILL_DIR}/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train

# 用例自优化（apply，写入 cases YAML）
python ${SKILL_DIR}/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train --apply --non-interactive

# 迭代报告（MD + HTML）
python ${SKILL_DIR}/scripts/case_iteration_report.py --config .agent-eval/config.yaml --latest

# cases YAML 校验
python ${SKILL_DIR}/scripts/case_io.py --config .agent-eval/config.yaml --split train --validate
```

## 文档

| 文档 | 说明 |
|------|------|
| `skills/orchestrator/SKILL.md` | 编排子 skill（含 V1.1 阶段4.5用例自优化） |
| `skills/requirements-analysis/SKILL.md` | 阶段 1 子 skill（含 V1.1 UC 15字段 + testspec 4表） |
| `skills/test-case-generator/SKILL.md` | 阶段 2 子 skill（含 V1.1 7方法库 + 20项自检 + 五层断言） |
| `skills/test-executor/SKILL.md` | 阶段 3 子 skill（执行 + 桥接） |
| `skills/test-reporter/SKILL.md` | 阶段 4 子 skill（汇总 + 深度报告） |
| `skills/test-case-self-optimization/SKILL.md` | 【V1.1 新增】阶段 4.5 子 skill（用例自优化编排） |
| `guides/01-15` | 主分支 15 篇技术指南 |
| `guides/16_mobile_bank_pipeline.md` | 手机银行 4 阶段流水线 + 桥接指南 |
| `guides/17_case_self_optimization.md` | 【V1.1 新增】用例自优化指南 |
| `docs/DESIGN_OVERVIEW.md` | 设计总纲（V1.1 更新） |
| `docs/DELTA_GENERAL_TO_AGENT.md` | 【V1.1 新增】通用测试转 Agent 评测的新增点分析 |
| `docs/PRD_REQUIREMENT_TESTDESIGN.md` | 【V1.1 新增】需求分析与测试设计流程（吸收 test-design-agent-raw） |
| `docs/PRD_CASE_SELF_OPTIMIZATION.md` | 用例自优化 PRD（V1.1 详细设计） |
| `docs/PRD_MOCK_SYSTEM.md` | 【V1.1 新增】mock 系统设计 |
| `docs/PRD_REPORT_PORTAL.md` | 【v1.1.1 新增】报告门户 + 进度埋点 PRD（含验收标准 §8） |
| `docs/PRD_TEST_DESIGN.md` | 测试设计 PRD（v2.3.0 历史，已被 PRD_REQUIREMENT_TESTDESIGN 取代） |
| `docs/PRD_ORCHESTRATION.md` | 总流程管控 PRD |
| `docs/ADAPTER_SPEC.md` | 适配器接口规范 |
| `docs/RESEARCH_REPORT.md` | 业界调研报告 |

## 标注 / 成本 / 采样（v1.1.2 合并自 dev-skill-eval）

> 以下能力从 Gitee `dev-skill-eval` 分支**纯增量**合并而来，与 v1.1 用例自优化正交。所有脚本零 LLM，复用 v1.1 的 `common.py`。详见 `VERSION.md` v1.1.2 条目。

### 标注模式（人工校准 3+N 维度评分）

```bash
# 启动 Web 标注服务（浏览器访问 http://127.0.0.1:8766）
python ${SKILL_DIR}/scripts/annotate_server.py --config .agent-eval/config.yaml --port 8766

# 查看标注统计 / 校验 / 导出
python ${SKILL_DIR}/scripts/annotator.py --config .agent-eval/config.yaml --stats
python ${SKILL_DIR}/scripts/annotator.py --config .agent-eval/config.yaml --validate
python ${SKILL_DIR}/scripts/annotator.py --config .agent-eval/config.yaml --export annotations.json

# 导出 Excel 标注模板 / 填写后导入
python ${SKILL_DIR}/scripts/xlsx_importer.py --config .agent-eval/config.yaml --export-annotations
python ${SKILL_DIR}/scripts/xlsx_importer.py --config .agent-eval/config.yaml --import-annotations annotations_filled.xlsx
```

`agents/annotation-judge.md` 提供标注判定辅助（校准 / 推断 / 建议），用于把人工标注与自动评分对齐。

### 成本追踪与 Span 监控

```bash
# 从 trace 构建 Span 树（评测后必跑一次，才能出成本报表）
python ${SKILL_DIR}/scripts/cost_tracker.py --config .agent-eval/config.yaml --run <run_id> --build-spans

# 成本报表（按 case / tool / dimension / time / iteration 聚合）
python ${SKILL_DIR}/scripts/cost_tracker.py --config .agent-eval/config.yaml --run <run_id> --report --aggregate-by tool
```

### 分层采样

```bash
# 按比例分层采样（时间窗口 + 申请类型 + 风险等级 + 地区/分行）
python ${SKILL_DIR}/scripts/stratified_sampler.py --config .agent-eval/config.yaml --split train --sample-size 50 --out sampled.yaml
```

需在 `config.yaml` 配置 `stratified_sampling.enabled=true` 启用；未启用时返回全部用例（graceful fallback）。

### SSE 流式推送

```bash
python ${SKILL_DIR}/scripts/sse_stream.py --port 8765 --config .agent-eval/config.yaml
```

### Excel 用例导入（cases.xlsx → YAML）

```bash
python ${SKILL_DIR}/scripts/xlsx_importer.py --config .agent-eval/config.yaml --import-cases cases.xlsx --split train
```

### 新增指标族（`examples/.agent-eval/metrics/`）

- 业务价值 `bv_*`：customer_experience / decision_accuracy / sop_completeness / terminology_accuracy
- 性能效率 `pe_*`：token_consumption / tool_efficiency
- 风险控制 `rc_*`：risk_classification
