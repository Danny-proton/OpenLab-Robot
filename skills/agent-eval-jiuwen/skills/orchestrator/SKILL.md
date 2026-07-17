---
name: orchestrator
description: "编排子 skill（JiuwenSwarm 适配）。按用户需求依次驱动 4 阶段流水线 + 桥接 + agent-eval eval loop。负责阶段间的数据流衔接、用户交互节奏、SideCar 状态上报。本身不调任何脚本，只协调其他子 skill 和主 SKILL.md 的能力。"
allowed-tools: bash, read, write, edit, task, question, todo_create, todo_complete, todo_insert, todo_list, todo_remove, send_message, list_members, view_task
---

# Orchestrator 编排子 skill（JiuwenSwarm 适配）

> **架构定位**：这是"大 skill 套小 skill 套 script"结构里的**编排小 skill**。
> 它不直接调脚本，而是协调其他 4 个子 skill（requirements-analysis / test-case-generator / test-executor / test-reporter）+ agent-eval 主分支的 eval loop 能力（diagnoser / multi_judge / optimizer）。
> 大 skill（`agent-eval-jiuwen/SKILL.md`）负责整体入口和触发，本 orchestrator 负责**单次评测运行内**的阶段编排。
>
> **JiuwenSwarm 适配说明**：
> - 所有"用 `task` 工具 spawn 子 agent"的地方，在 **Team 模式**下都可改用 `send_message` 把子任务派发给已存在的 Teammate（每个子 skill 对应一个 Teammate 角色）。
> - 用 `list_members` 查看当前团队组成，用 `view_task` 跟踪派发出去的子任务状态。
> - 用户交互问询统一用 `question` 工具（替代 Claude Code 的 AskUserQuestion）。
> - 进度跟踪可用 `todo_create` / `todo_complete` / `todo_insert` / `todo_list` / `todo_remove` 维护阶段清单（替代 Claude Code 的 TodoWrite），与 sidecar.py 的 progress.jsonl 互补：todo_* 是 Agent 内部任务视图，progress.jsonl 是跨工具持久化视图。

## 完整阶段流（一次评测运行）

```
┌─────────────────────────────────────────────────────────────────┐
│  阶段 1: requirements-analysis  ──→  requirements_analysis.xlsx  │
│    （prompt 在子 skill，Agent 用 task 工具生成 JSON，脚本写 Excel）│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段 2: test-case-generator     ──→  test_cases.xlsx            │
│    （prompt 在子 skill，Agent 用 task 工具并行生成 JSON，脚本写 Excel）│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段 3: test-executor                                          │
│    3a. execute_testcases.py ──→ execution_results.xlsx          │
│    3b. excel_to_uatr.py     ──→ UATR trace + cases YAML (桥接)   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段 5-7: agent-eval eval loop（主分支原封不动的能力）          │
│    diagnoser.py     ──→ F1-F8 失败归因                          │
│    multi_judge.py   ──→ 9 Judge 评审                             │
│    opik_adapter.py  ──→ HRPO 根因                                │
│    reference_optimizer.py ──→ reference 注入                     │
│    auto_patcher.py  ──→ A/B 全自动优化                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段 4.5: test-case-self-optimization【V1.1 新增】              │
│    case_quality_checker.py  ──→ 12 维质量评分                    │
│    mutation_generator.py    ──→ 变异 kill matrix                 │
│    case_optimizer.py        ──→ 错误分布+缺口+建议生成+apply      │
│    case_iteration_report.py ──→ 迭代报告 (MD + HTML)             │
│    （改测试本身，不改被测 Agent；与阶段5-7的prompt自优化正交）    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段 4: test-reporter                                           │
│    generate_report.py  ──→ 4 阶段汇总报告 (MD + HTML)            │
│    html_report.py      ──→ eval-loop 深度报告 (含 F1-F8 / Judge) │
│    case_iteration_report.py ──→ 用例自优化迭代报告 (V1.1)        │
│    pdf_report.py       ──→ PDF 版（可选）                         │
│    dashboard.py        ──→ 多轮趋势 Dashboard（可选）            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段 9: report-portal【v1.1.1 新增】                            │
│    report_portal.py    ──→ 统一门户 portal.html                  │
│    （聚合 4/4.5/5-7 全部产物 + progress 时间线 + 质量分雷达）     │
│    （深色玻璃态 + 悬浮动效 + SVG 图表，单 HTML 可邮件分享）       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        用户决定：迭代增强（回阶段 1-2）还是收工
```

> **进度埋点（v1.1.1）**：阶段 1-9 每步开始/结束都调 `sidecar.py`，事件自动持久化到 `.agent-eval/data/progress.jsonl`，被门户 Progress 页聚合为 9 步水平时间线 + 每步耗时 tooltip。无需额外配置。

## 编排职责

### 1. 启动前信息收集（首次必跑）

调主分支 `ask_setup.py` 收集缺失信息：

```bash
python ${SKILL_PATH}/scripts/ask_setup.py --stage startup --config .agent-eval/config.yaml --emit-questions
```

把返回的 questions 用 `question` 工具问用户。若 `.agent-eval/config.yaml` 不存在，先 scaffold：

```bash
python ${SKILL_PATH}/scripts/eval_runner.py --scaffold .
```

### 2. 依次驱动 4 阶段

按上图顺序，每进入一个阶段：
- 调 `sidecar.py --status running --step N --step-name "阶段名"` 上报进度
- 委派给对应子 skill（读取 `skills/<phase>/SKILL.md` 并按其指示执行）
- 阶段完成后调 `sidecar.py --status completed --step N --run-id <run_id>`

### 3. 阶段间数据流校验

每个阶段完成后，校验产出文件存在且非空：

| 阶段 | 产出 | 校验 |
|------|------|------|
| 1 | `data/requirements_analysis.xlsx` | `测试维度` sheet 行数 ≥ 1 |
| 2 | `data/test_cases.xlsx` | `测试用例` sheet 行数 ≥ 1 |
| 3a | `data/execution_results.xlsx` | `执行结果` 行数 = 用例数 |
| 3b | `.agent-eval/traces/<run_id>.jsonl` | 行数 ≥ 用例数 |
| 5 | `.agent-eval/reports/<run_id>_diagnosis.md` | 文件存在 |
| 6 | `.agent-eval/scores/<run_id>_judges.json` | 文件存在 |
| 7 | `.agent-eval/patches/candidate_*.md` | 若有 patch 则存在 |
| 4 | `data/test_report.html` + `.agent-eval/reports/<run_id>.html` | 两份都存在 |
| 9 | `.agent-eval/reports/portal.html` | v1.1.1，文件存在且 >10KB |

校验失败则停在该阶段，向用户报告原因，询问是否重试或跳过。

### 4. 迭代决策

阶段 4 完成后，向用户展示 F1-F8 错误分布，询问：
- **迭代增强**：基于错误分布回到阶段 1-2，补充用例覆盖失败维度，重跑阶段 3-7
- **接受现状**：归档报告，结束本轮
- **自动优化**：若阶段 7 产出了 candidate patch，调 `auto_patcher.py --auto-apply` 自动应用并 A/B

无论哪种决策，收尾时都应生成统一门户（阶段 9）：

```bash
python ${SKILL_PATH}/scripts/sidecar.py --status running --step 9 --step-name "生成统一门户"
python ${SKILL_PATH}/scripts/report_portal.py --config .agent-eval/config.yaml
python ${SKILL_PATH}/scripts/sidecar.py --status completed --step 9
```

门户聚合本轮所有报告 + 进度时间线 + 迭代记录 + 12 维质量分，单 HTML 文件可邮件分享或归档。

### 5. 记忆沉淀

每轮结束时把用户偏好写入 memory_kb：

```bash
python ${SKILL_PATH}/scripts/memory_kb.py --remember preference --key adapter --value mobile_bank_http
python ${SKILL_PATH}/scripts/memory_kb.py --remember preference --key per_scenario --value 3
```

下一轮自动 recall，跳过重复询问。

## 与大 skill（agent-eval-jiuwen/SKILL.md）的分工

| 层级 | 职责 |
|------|------|
| 大 skill `agent-eval-jiuwen/SKILL.md` | 触发判定（用户说"测手机银行 agent"时激活）、整体能力清单、目录结构、命令速查 |
| 本 orchestrator | 单次评测运行内的阶段编排、数据流校验、迭代决策 |
| 子 skill（4 个） | 每阶段的 prompt 文字 + task 工具指示 + 调用哪个机械脚本 |
| scripts/ | 机械 I/O：Excel 读写、HTTP 执行、格式转换、UATR 桥接、诊断打分、报告渲染（零 LLM）|

## 重要约束

- ❌ 本 orchestrator 不直接拼 prompt（那是各子 skill 的职责）
- ❌ 不调任何外部 LLM API
- ✅ 只做协调：读子 skill 指示 → 委派 → 校验 → 上报 → 决策
- ✅ 每步调 sidecar 上报进度，让用户看到流水线状态
- ✅ 阶段间数据流必须校验，断了就停
