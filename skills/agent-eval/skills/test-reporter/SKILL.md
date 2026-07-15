---
name: test-reporter
description: "报告生成子 skill（阶段 4）。读取需求分析 / 测试用例 / 执行结果三个 Excel，生成 4 阶段汇总报告（MD + HTML）。同时调用 agent-eval 主分支的 html_report.py / pdf_report.py 生成 eval-loop 深度报告（含 F1-F8 诊断 / 9 Judge / 优化建议）。脚本不调任何外部 LLM。"
allowed-tools: Bash(python *), Bash(python3 *), Read, Write, Edit, Task, AskUserQuestion
---

# 测试报告生成子 skill（阶段 4 / 4）

> **架构定位**：这是"大 skill 套小 skill 套 script"结构里的**小 skill** 层。
> 本阶段**没有生成性 LLM 工作**——报告是机械的数据汇总 + 模板渲染。
> 调用两个机械脚本：
> 1. `generate_report.py` —— 4 阶段流水线汇总报告（MD + HTML，从 3 个 Excel 读）
> 2. `html_report.py` / `pdf_report.py` —— agent-eval 主分支深度报告（从 run_id 读，含诊断 / Judge / 优化）
>
> 两个脚本零 LLM 调用。

## 你的输入

- `data/requirements_analysis.xlsx`（阶段 1 产出）
- `data/test_cases.xlsx`（阶段 2 产出）
- `data/execution_results.xlsx`（阶段 3 产出）
- `<run_id>`（阶段 3 桥接器产出，关联 `.agent-eval/traces/` / `scores/` / `runs/`）

## 你的输出

- `data/test_report.html` + `data/test_report.md`（4 阶段流水线汇总报告）
- `.agent-eval/reports/<run_id>.html`（agent-eval 深度报告，含 F1-F8 / 9 Judge / 优化建议）
- `.agent-eval/reports/<run_id>.pdf`（可选 PDF 版）

## 第 1 步：生成 4 阶段汇总报告

```bash
python ${SKILL_PATH}/scripts/generate_report.py \
  --requirements ${SKILL_PATH}/data/requirements_analysis.xlsx \
  --testcases ${SKILL_PATH}/data/test_cases.xlsx \
  --results ${SKILL_PATH}/data/execution_results.xlsx \
  --output ${SKILL_PATH}/data/test_report.md
```

脚本会自动同时生成 `.md` 和 `.html`（同名换扩展名）。内容包含：
- 测试维度概览（来自 requirements_analysis）
- 用例统计（按优先级 / 场景 / 维度分组，来自 test_cases）
- 执行结果（成功率 / 失败清单 / 响应时间分布，来自 execution_results）
- 结论与建议（基于通过率自动生成）

## 第 2 步：生成 agent-eval 深度报告（接主分支能力）

如果阶段 3 桥接 + 阶段 5-7 诊断已完成，用 `<run_id>` 调主分支报告器：

```bash
# HTML 深度报告（含 F1-F8 失败归因 / 9 Judge 评审 / HRPO 根因 / 优化 patch）
python ${SKILL_PATH}/scripts/html_report.py \
  --config .agent-eval/config.yaml --run <run_id>

# 可选 PDF 版
python ${SKILL_PATH}/scripts/pdf_report.py \
  --config .agent-eval/config.yaml --run <run_id> --page-size A4
```

深度报告与汇总报告的区别：
| 报告 | 数据源 | 内容 |
|------|--------|------|
| `data/test_report.html`（汇总） | 3 个 Excel | 维度 / 用例 / 执行结果统计 |
| `.agent-eval/reports/<run_id>.html`（深度） | UATR trace + scores + judges | F1-F8 归因 / Judge 评分 / 根因 / 优化 patch |

## 第 3 步：注册到报告管理索引

主分支的 `report_manager.py` 会自动把生成的报告注册到 `.agent-eval/reports/index.jsonl`。后续可用 CRUD 命令管理：

```bash
# 列出所有报告（按日期分组）
python ${SKILL_PATH}/scripts/report_manager.py --config .agent-eval/config.yaml list --daily

# 搜索某个 run 的报告
python ${SKILL_PATH}/scripts/report_manager.py --config .agent-eval/config.yaml search --run <run_id>

# 导出报告
python ${SKILL_PATH}/scripts/report_manager.py --config .agent-eval/config.yaml export <report_id> <目标路径>
```

## 第 4 步：生成 Dashboard（可选）

```bash
python ${SKILL_PATH}/scripts/dashboard.py --config .agent-eval/config.yaml
```

Dashboard 汇总所有 run 的趋势（分数 / F1-F8 分布 / latency / 优化历史），适合多轮迭代后看整体进步。

## 第 5 步：向用户汇报

把两份报告的路径展示给用户，并询问：
- 是否需要 PDF 版？
- 是否进入阶段 5-7（诊断 / Judge / 优化）？如果阶段 3 已桥接，这一步通常已自动完成
- 是否基于 F1-F8 错误分布回到阶段 1-2 增强用例，开启下一轮迭代？

## 重要约束

- ❌ 本子 skill 不许调任何外部 LLM API
- ❌ 报告内容由脚本机械渲染，不由 Agent 现编
- ✅ 汇总报告 + 深度报告并存，各司其职
- ✅ 报告自动注册到索引，可 CRUD 管理
