---
name: test-case-self-optimization
description: "测试用例自优化子 skill（JiuwenSwarm 适配）。当一轮评测完成后，基于错误分布分析、spec 缺口、用例质量检查、mutation kill matrix，自动迭代测试用例集。改的是测试本身（case/spec/因子），不是被测 Agent。"
allowed-tools: bash, read, write, edit, task, question, todo_create, todo_complete, todo_insert, todo_list, todo_remove, send_message, list_members, view_task
---

# 用例自优化子 skill（阶段 4.5，JiuwenSwarm 适配）

> 本子 skill 是 agent-eval-jiuwen（V1.1）的核心创新。业界只有 prompt 自优化（改被测 Agent），本子 skill 实现 test-case 自优化（改测试本身）。

## 你的职责

完成一轮评测后，**优化测试用例集**，让下一轮测试的覆盖度和有效率提升。你不改被测 Agent，只改 cases YAML。

## 前置条件

- 已完成一轮评测：`eval_runner.py` + `diagnoser.py` + `scorer.py` 跑完
- 存在 `reports/<run_id>_diagnosis.json` 和 `scores/<run_id>.json`
- 存在 `cases/<split>.yaml`（完整 canonical schema）

## 8 步流程

### Step 1: 错误分布分析（自动）

调 `case_optimizer.py` 的分析逻辑（已内置）。读取 `diagnosis.json` 的 `by_failure_type`，识别集中类型（占比 > 40% 或绝对数 ≥ 3）。

```bash
# 生成建议（dry-run，先看不改）
python ${SKILL_DIR}/scripts/case_optimizer.py \
  --config .agent-eval/config.yaml \
  --run <run_id> --split train --dry-run
```

### Step 2: Spec 缺口识别（自动）

case_optimizer 内置：
- 维度缺口：某个 dimension_id 在 cases 中 0 用例
- 工具缺口：某个被测工具不在任何 case 的 expected_tools.required
- DFX 缺口：7 个 DFX 类型中某类 0 用例
- 过简单维度：某维度 100% 通过 且 用例数 ≥ 2

### Step 3: 用例质量检查（自动）

case_optimizer 内置调用 `case_quality_checker.py`，输出 12 维评分：
- 9 维（SPEC完整性/用例完整性/功能点/DFX/有效用例率/可执行性/无二义性/长度/断言可验证）
- 3 维 Agent 专属（工具覆盖率/工作流覆盖率/记忆覆盖率）

阈值：单维 < 0.6 标记低分；总分 < 0.75 触发质量增强。

### Step 4: Mutation 分析（自动）

case_optimizer 内置调用 `mutation_generator.py`：
- 生成 6 类变异（漏调工具/重复调用/参数错/空结果/幻觉/冗余步）
- 跑 kill matrix，看现有用例能否检出
- survived 的变异 → 用例需增强

### Step 5: 生成增强建议（自动）

case_optimizer 生成结构化建议 JSON（`data/<proposal_id>.json`）：
- `add_cases`：基于 F 集中 + 缺口 + survived 变异
- `modify_cases`：基于低分维度 + 断言不够强
- `deprecate_cases`：基于重复/过时
- `spec_changes`：基于新发现的业务规则

### Step 6: 与人确认（交互）

读建议 JSON，用 `question` 工具逐条问用户：

```
question:
  question: "检测到 F3.1 工具选择失败集中（3条），建议新增用例 loan_risk_009 验证工具选择边界。是否接受？"
  options:
    - "接受（推荐）"
    - "修改用例内容"
    - "拒绝"
```

对 4 类建议分别询问：
1. **新增用例**：建议的新 case 是否符合业务理解？多选接受/拒绝
2. **修改用例断言**：断言修改是否改变评测标准？逐条确认
3. **废弃用例**：用例是否有业务价值不能删？逐条确认
4. **spec 变更**：业务规则变更需确认

用户确认后，记录接受/拒绝的清单。

> **非交互模式**（CI/CD）：加 `--non-interactive`，全部接受。

### Step 7: 更新 cases YAML（自动）

调 `case_optimizer.py --apply`，通过 `case_io.py` 写入 cases YAML：
- 保留完整 canonical schema（不丢字段）
- 自动备份到 `data/backups/`
- 追加迭代记录到 `data/case_iterations.jsonl`

```bash
python ${SKILL_DIR}/scripts/case_optimizer.py \
  --config .agent-eval/config.yaml \
  --run <run_id> --split train --apply --non-interactive
```

> **重要**：add_cases 里的用例内容是模板（含"(待 Agent 生成)"占位）。apply 后，你应该读 `data/<proposal_id>.json` 的 add_cases，用 `task` 工具 spawn 子 agent（Team 模式下用 `send_message` 派发给 `test-case-self-optimization` Teammate）生成真实的用例内容（input/expected/business_rules），再 `edit` cases YAML 替换占位符。这一步是创造性的，必须由 Agent 完成，脚本不做。

### Step 8: 度量提升 + 报告（自动）

重跑评测，对比质量分变化：

```bash
# 重跑评测（用更新后的 cases）
python ${SKILL_DIR}/scripts/eval_runner.py \
  --config .agent-eval/config.yaml --split train --variant optimized

# 重新诊断
python ${SKILL_DIR}/scripts/diagnoser.py \
  --config .agent-eval/config.yaml --latest

# 生成迭代报告
python ${SKILL_DIR}/scripts/case_iteration_report.py \
  --config .agent-eval/config.yaml --latest
```

报告产出：
- `reports/case_iteration_<proposal_id>.md`
- `reports/case_iteration_<proposal_id>.html`

报告内容：错误分布 / spec 缺口 / 12 维质量分 / mutation kill matrix / 优化建议清单 / 质量分前后对比 / 迭代历史。

## 与 prompt 自优化的关系

用例自优化**不替代** prompt 自优化，而是**补充**：

```
一轮评测
  ↓
[阶段 5-7] prompt 自优化（改被测 Agent）
  - reference_optimizer → 注入 reference
  - mutator → 生成 patch
  - auto_patcher → A/B + Gatekeeper
  ↓
[阶段 4.5] 用例自优化（改测试本身）← 本子 skill
  - case_quality_checker → 12 维质量分
  - case_optimizer → 生成建议
  - mutation_generator → kill matrix
  - case_io --apply → 更新 cases
  - case_iteration_report → 报告
  ↓
重跑评测 → Agent 越来越准，测试越来越全（双闭环）
```

## 重要规则

1. **脚本零 LLM**：case_optimizer / mutation_generator / case_quality_checker 不调外部 LLM，所有建议基于规则映射
2. **创造性工作由 Agent 完成**：add_cases 的真实内容（input/expected/business_rules）由你（Agent）用 `task` 工具生成（Team 模式下用 `send_message` 派发），脚本只生成模板
3. **保留完整 schema**：case_io.py 写回时保留 expected_tools/business_rules/expected_steps/scoring 全部字段
4. **必须备份**：apply 前自动备份到 data/backups/
5. **必须记录迭代**：每轮 apply 追加 case_iterations.jsonl，含 quality_before/after
6. **接受规则是机械的**：质量分提升 + 覆盖率提升 + mutation 检出率提升才算成功迭代

## 触发条件

| 触发 | 说明 |
|------|------|
| 一轮测试完成 | eval_runner + diagnoser 跑完（默认） |
| 用户手动 | "优化用例" / "分析用例质量" |
| CI 自动 | regression 通过但分数下降 > 0.05 |
| 错误集中 | 某类 F 失败占比 > 40% |
| 覆盖缺口 | 某维度 0 用例 或 某工具 0 用例 |

## 命令速查

```bash
# 单独跑质量检查
python ${SKILL_DIR}/scripts/case_quality_checker.py --config .agent-eval/config.yaml --split train

# 单独跑 mutation kill matrix
python ${SKILL_DIR}/scripts/mutation_generator.py --config .agent-eval/config.yaml --latest --split train

# 完整自优化（dry-run）
python ${SKILL_DIR}/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train

# 完整自优化（apply）
python ${SKILL_DIR}/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train --apply --non-interactive

# 迭代报告
python ${SKILL_DIR}/scripts/case_iteration_report.py --config .agent-eval/config.yaml --latest

# cases 读写校验
python ${SKILL_DIR}/scripts/case_io.py --config .agent-eval/config.yaml --split train --validate
```
