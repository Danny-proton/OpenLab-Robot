# PRD — 测试用例自优化（V1.1 详细设计）

> **业界空白**：有 prompt 自优化（HRPO/GEPA），无 test-case 自优化。本文档定义这个概念并给出 V1.1 可实现设计。
>
> 本文档是 V1.1 的核心 PRD，对应实现：`scripts/case_io.py` / `case_quality_checker.py` / `case_optimizer.py` / `mutation_generator.py` / `case_iteration_report.py` + `skills/test-case-self-optimization/SKILL.md`。

## 0. 文档状态

| 项 | 值 |
|----|----|
| 版本 | v1.1.0 |
| 状态 | 设计完成，待实现 |
| 依赖 | diagnoser.py（F1-F8 诊断）/ scorer.py（评分）/ cases YAML schema |
| 产出 | case_optimization_proposal.json + case_iterations.jsonl + iteration report MD/HTML |

---

## 1. 概念定义

**测试用例自优化**：完成一轮测试后，基于错误分布分析、spec 增强、用例质量检查、mutation kill matrix，自动迭代测试用例集，使下一轮测试的覆盖度和有效率提升。

与 prompt 自优化的区别：
- prompt 自优化改的是 **被测 Agent**（prompt/tool/workflow/reference）—— 已由 `reference_optimizer.py` / `auto_patcher.py` 实现
- 用例自优化改的是 **测试本身**（case/spec/因子）—— 本 PRD 定义

两者**正交**：可以同时优化被测 Agent 和测试本身。本 skill 先跑 prompt 自优化（改 Agent），再跑用例自优化（改测试），形成双闭环。

## 2. 触发条件

| 触发 | 说明 | 自动/手动 |
|------|------|----------|
| 一轮测试完成 | eval_runner + diagnoser 跑完后 | 自动（可配置） |
| 用户手动 | "优化用例" / "分析用例质量" | 手动 |
| CI 自动 | regression 通过但分数下降 > 0.05 | 自动 |
| 错误集中 | 某类 F 失败占比 > 40% | 自动 |
| 覆盖缺口 | 某维度 0 用例 或 某工具 0 用例 | 自动 |

CLI 触发：
```bash
# 分析 + 生成建议（dry-run，不写 cases）
python case_optimizer.py --config .agent-eval/config.yaml --run <run_id> --split train

# 分析 + 生成 + 自动 apply 到 cases YAML
python case_optimizer.py --config .agent-eval/config.yaml --run <run_id> --split train --apply

# 只跑质量检查
python case_quality_checker.py --config .agent-eval/config.yaml --split train

# 只跑 mutation kill matrix
python mutation_generator.py --config .agent-eval/config.yaml --run <run_id> --split train
```

## 3. 输入 / 输出契约

### 3.1 输入

| 输入 | 路径 | 说明 |
|------|------|------|
| 诊断结果 | `reports/<run_id>_diagnosis.json` | F1-F8 分布 + 逐条诊断（含 evidence + suggested_mutation_target/rule） |
| 评分结果 | `scores/<run_id>.json` | 每条 case 的 metrics + hard_fails + weighted_score |
| 当前用例集 | `cases/<split>.yaml` | 完整 canonical schema（expected_tools/business_rules/expected_steps/scoring） |
| Trace | `traces/<run_id>.jsonl` | UATR 事件（mutation kill matrix 用） |
| 运行记录 | `runs/<run_id>.jsonl` | 每条 case 的执行记录 |
| 历史迭代 | `data/case_iterations.jsonl` | 上一轮的质量分/覆盖率（度量变化用） |
| 需求分析 | `data/requirements_analysis.xlsx`（可选） | 维度/场景（spec 缺口识别用） |
| Spec | `data/requirements_analysis.xlsx` 的"测试维度"sheet（可选） | 业务规则来源 |

### 3.2 输出

| 输出 | 路径 | 说明 |
|------|------|------|
| 优化建议 | `data/case_optimization_proposal_<ts>.json` | 结构化建议（add/modify/deprecate/spec_changes） |
| 迭代记录 | `data/case_iterations.jsonl` | 追加一行：run_id/proposal_id/accepted/quality_before/after |
| 更新的用例 | `cases/<split>.yaml`（--apply 时） | 保留完整 schema 的写回 |
| 迭代报告 MD | `reports/case_iteration_<ts>.md` | 人读报告 |
| 迭代报告 HTML | `reports/case_iteration_<ts>.html` | 可视化报告 |
| Mutation 报告 | `reports/case_mutation_<ts>.json` + `.md` | kill matrix + 未检出变异 |

### 3.3 优化建议 JSON Schema

```json
{
  "proposal_id": "prop-20260716-143000-train",
  "run_id": "20260716-140000-baseline-mobile-bank",
  "split": "train",
  "generated_at": "2026-07-16T14:30:00+08:00",
  "trigger": "round_complete | error_concentration | coverage_gap | manual",
  "analysis": {
    "error_distribution": {
      "F3.1": {"count": 1, "ratio": 0.33, "concentrated": true},
      "F7.3": {"count": 1, "ratio": 0.33, "concentrated": true},
      "F8.2": {"count": 1, "ratio": 0.33, "concentrated": true}
    },
    "spec_gaps": [
      {"dimension_id": "DIM-002", "dimension_name": "异常恢复", "case_count": 0, "severity": "high"},
      {"tool": "queryCreditScore", "case_count": 0, "severity": "medium"}
    ],
    "quality_scores": {
      "spec_completeness": 0.80,
      "case_completeness": 0.90,
      "feature_coverage": 0.70,
      "dfx_coverage": 0.43,
      "valid_case_ratio": 1.00,
      "executability": 0.67,
      "ambiguity_free": 0.85,
      "length_reasonable": 0.95,
      "assertion_verifiable": 0.80,
      "weighted_total": 0.79
    },
    "mutation_kills": {
      "total_mutations": 6,
      "killed": 4,
      "survived": 2,
      "kill_rate": 0.67,
      "survived_mutations": ["mut_skip_checkDebtRatio", "mut_wrong_param_id_card"]
    }
  },
  "add_cases": [
    {
      "suggested_id": "loan_risk_004",
      "reason": "F3.1 集中于工具选择失败，需补充工具选择边界用例",
      "trigger_failure_type": "F3.1",
      "case": {
        "id": "loan_risk_004",
        "name": "风险审查-工具选择边界-相似工具区分",
        "agent": "loan-risk-agent",
        "task": "用户提交申请，验证 Agent 能区分 analyze_cashflow 与 queryCreditScore 的调用时机",
        "input": {"user_message": "...", "application_id": "A004"},
        "expected": {"final_decision": {"contains": ["..."]}},
        "expected_tools": {"required": [...], "forbidden": [...]},
        "business_rules": {"must_satisfy": [...]},
        "expected_steps": 9,
        "scoring": {"hard_fail_if": ["forbidden_tool_called"]},
        "test_level": "gray_box",
        "category": "functional",
        "lifecycle": "active"
      }
    }
  ],
  "modify_cases": [
    {
      "case_id": "loan_risk_002",
      "reason": "F8.2 检出但断言不够强：expected_steps=9 但实际 mock 产生 17 步仍未触发硬失败",
      "field": "scoring.hard_fail_if",
      "old_value": ["forbidden_tool_called", "missing_required_business_rule"],
      "new_value": ["forbidden_tool_called", "missing_required_business_rule", "step_count_exceeds_1.5x"],
      "trigger_failure_type": "F8.2"
    }
  ],
  "deprecate_cases": [
    {
      "case_id": "loan_risk_003",
      "reason": "与 loan_risk_002 重复（同为正常通过场景），有效用例率下降",
      "action": "mark_deprecated"
    }
  ],
  "spec_changes": [
    {
      "type": "add_business_rule",
      "rule_id": "risk_rule_step_count",
      "description": "执行步数不得超过 expected_steps 的 1.5 倍",
      "applies_to": "all cases",
      "reason": "F8 集中说明缺少效率断言"
    }
  ],
  "quality_before": {"weighted_total": 0.79, "feature_coverage": 0.70},
  "quality_after_estimated": {"weighted_total": 0.88, "feature_coverage": 0.90},
  "summary": "检出 F3.1/F7.3/F8.2 三类集中失败，2 个 spec 缺口，mutation 检出率 67%。建议新增 1 用例、修改 1 用例断言、废弃 1 重复用例、新增 1 业务规则。预计质量分 0.79→0.88。"
}
```

## 4. 分析维度（5 个）

### 4.1 错误分布分析（F1-F8）

从 `diagnosis.json` 的 `by_failure_type` 统计。集中阈值 = 某类占比 > 40% 或 绝对数 ≥ 3。

| 错误集中类型 | 含义 | 用例增强策略（自动生成 add_cases 的依据） |
|-------------|------|-------------|
| F1-F2 集中 | 任务理解/识别失败 | 补充任务类型识别用例；加更多场景覆盖 |
| F3 集中 | 工具选择失败 | 增加工具选择边界用例；细化 expected_tools；加相似工具区分用例 |
| F4 集中 | 工具参数失败 | 增加参数边界用例（等价类/边界值）；细化 arguments 断言；加字段映射用例 |
| F5 集中 | Workflow 失败 | 增加异常恢复流程用例；加 fallback 场景；加中断恢复用例 |
| F6 集中 | Memory 失败 | 增加多轮上下文用例；加记忆检索触发用例 |
| F7 集中 | 输出失败 | 细化 expected.contains 关键词；加输出格式断言；加幻觉检测用例 |
| F8 集中 | 执行冗余 | 调整 expected_steps；加效率用例；加 scoring.hard_fail_if: step_count_exceeds_1.5x |

**自动规则**：`diagnoses[].suggested_mutation_target` + `suggested_mutation_rule` 是生成 add_cases 的主信号。每条诊断的 evidence 提供 case 上下文。

### 4.2 Spec 缺口识别

两类缺口：
- **维度缺口**：某个 dimension_id 在 cases 中 0 用例 → severity: high
- **工具缺口**：某个被测工具不在任何 case 的 expected_tools.required 里 → severity: medium
- **DFX 缺口**：7 个 DFX 类型中某类 0 用例 → severity: medium
- **过简单维度**：某维度 100% 通过 且 用例数 ≥ 2 → 可能太简单，severity: low（建议加边界/异常用例）

数据来源：
- 维度/场景来自 `requirements_analysis.xlsx` 的"测试维度"+"测试场景" sheet（若存在）
- 工具列表来自 config 或 cases 中出现过的所有 expected_tools.required 取并集
- DFX 类型来自用例 category 字段（functional/dfx_security/adversarial + DFX 子类）

### 4.3 用例质量检查（9 维度 + Agent 专属 3 维 = 12 维）

确定性检查，不调 LLM：

| # | 维度 | 权重 | 检查方法 | Agent 专属 |
|---|------|------|---------|-----------|
| 1 | SPEC 完整性 | 0.13 | 用例覆盖需求维度比例 | |
| 2 | 用例完整性 | 0.09 | 字段齐全（id/input/expected/expected_tools/business_rules/expected_steps/scoring） | |
| 3 | 功能点覆盖度 | 0.13 | 10 维度是否都有用例 | |
| 4 | DFX 覆盖度 | 0.13 | 性能/安全/兼容/可靠/韧性/可服务/可维护 7 维 | |
| 5 | 有效用例率 | 0.09 | 无过时/重复/不可执行用例（lifecycle=deprecated 算无效） | |
| 6 | 执行可行性 | 0.09 | 上次执行通过率 > 0 | |
| 7 | 无二义性 | 0.09 | 步骤/预期无歧义（启发式：含"等等"/"之类的"/"可能"算二义） | |
| 8 | 长度合理 | 0.04 | 用例步数 < 10，task token < 500 | |
| 9 | 断言可验证 | 0.09 | expected 可自动验证（contains/equals/regex/schema 非纯主观） | |
| 10 | **工具覆盖率** | 0.04 | 被测工具列表中每条都有用例覆盖 | ✓ Agent 专属 |
| 11 | **工作流覆盖率** | 0.04 | 前置检查/异常恢复/fallback 场景有用例 | ✓ Agent 专属 |
| 12 | **记忆覆盖率** | 0.04 | expect_memory_use 场景覆盖 | ✓ Agent 专属 |

权重合计 1.00。阈值：单维 < 0.6 标记为低分维度；总分 < 0.75 触发质量增强建议。

**实现**：`case_quality_checker.py`，纯确定性，输入 cases YAML + 可选 requirements Excel + 可选 scores，输出 12 维评分 JSON。

### 4.4 Mutation 驱动用例增强（参考 Meta ACH arXiv 2501.12862）

思路：生成少量"变异 Agent 行为"，看现有用例能否检出（kill）。未检出的变异 → 补充用例。

**变异类型**（6 种，覆盖 F3/F4/F7/F8）：

| 变异 ID | 变异行为 | 对应失败类型 | 现有用例应检出方式 |
|---------|---------|------------|------------------|
| mut_skip_tool | 漏调一个 required 工具 | F3.1 | expected_tools.required 断言 |
| mut_repeat_tool | 同一工具重复调用 3 次 | F3.3 | （需新增 repeat 断言） |
| mut_wrong_param | 工具参数传错（如 id_card→applicant_name） | F4.4 | tool_result.status=error 检测 |
| mut_empty_result | 工具返回空结果 | F5.3 | fallback 场景断言 |
| mut_hallucinate | final 编造 trace 没有的数字 | F7.4 | 幻觉检测断言 |
| mut_redundant_steps | 注入 2x model_call（笨模式） | F8.2/F8.4 | expected_steps + step_count 断言 |

**kill matrix**：

| 变异 | case_001 | case_002 | case_003 | ... | 需补 |
|------|----------|----------|----------|-----|------|
| mut_skip_analyze_cashflow | ✅(F3.1) | ❌ | ❌ | | case_002/003 需增强 |
| mut_wrong_param | ❌ | ❌ | ✅(F4.4) | | case_001/002 需增强 |

**实现**：`mutation_generator.py`
1. 从 cases YAML 提取正常行为模板
2. 对每个 case 注入 6 种变异之一（轮转），生成变异 trace
3. 用 diagnoser 的归因逻辑跑变异 trace，看是否产出对应 F 诊断
4. 产出诊断 = killed；未产出 = survived
5. survived 的变异 → add_cases 建议（增强能检出该变异的用例）

**注意**：mutation 不真正跑被测 Agent，而是在 mock trace 基础上机械修改（删一个 tool_call / 改一个参数 / 加 model_call），再用 diagnoser 检查。零 LLM。

### 4.5 质量提升度量

| 维度 | 指标 | 衡量方法 |
|------|------|---------|
| 覆盖度 | 功能点覆盖率 | 已覆盖维度 / 总维度 |
| 覆盖度 | DFX 覆盖率 | 已覆盖 DFX 类型 / 7 |
| 覆盖度 | 工具覆盖率 | 有用例的工具 / 总工具 | ✓ Agent |
| 覆盖度 | Mutation 检出率 | killed / total_mutations |
| 质量 | 二义性率 | 有二义用例 / 总用例 |
| 质量 | 有效用例率 | lifecycle=active / 总用例 |
| 质量 | 质量分 | 12 维加权分 |
| 迭代 | 新增用例数 | 本轮 add_cases 数 |
| 迭代 | 修改用例数 | 本轮 modify_cases 数 |
| 迭代 | 废弃用例数 | 本轮 deprecate_cases 数 |
| 迭代 | 质量分变化 | quality_after - quality_before |
| 迭代 | 覆盖率变化 | coverage_after - coverage_before |

## 5. 迭代流程（8 步）

```
完成一轮测试（eval_runner + diagnoser + scorer）
  ↓
Step 1: 错误分布分析 [case_optimizer.py]
  - 读 diagnosis.json 的 by_failure_type
  - 识别集中类型（ratio > 0.4 或 count >= 3）
  ↓
Step 2: Spec 缺口识别 [case_optimizer.py]
  - 维度缺口（0 用例的 dimension）
  - 工具缺口（0 用例的 tool）
  - DFX 缺口（0 用例的 DFX 类型）
  - 过简单维度（100% 通过）
  ↓
Step 3: 用例质量检查 [case_quality_checker.py]
  - 12 维度确定性评分
  - 识别低分维度（< 0.6）
  ↓
Step 4: Mutation 分析 [mutation_generator.py]
  - 生成 6 类变异
  - 跑 kill matrix
  - 识别 survived 变异
  ↓
Step 5: 生成增强建议 [case_optimizer.py]
  - add_cases（基于 F 集中 + 缺口 + survived 变异）
  - modify_cases（基于低分维度 + 断言不够强）
  - deprecate_cases（基于重复/过时）
  - spec_changes（基于新发现的业务规则）
  - 写 case_optimization_proposal.json
  ↓
Step 6: 与人确认 [AskUserQuestion，由子 skill 触发]
  - 展示增强建议
  - 用户选择接受/拒绝/修改每条建议
  ↓
Step 7: 更新 cases YAML [case_io.py --apply]
  - 通过 case_io.py 写入，保留完整 canonical schema
  - 追加 case_iterations.jsonl
  ↓
Step 8: 度量提升 [case_iteration_report.py]
  - 重跑评测（eval_runner + diagnoser + scorer）
  - 对比 quality_before / quality_after
  - 生成迭代报告 MD + HTML
```

## 6. 与人确认的环节

| 环节 | 确认什么 | 为什么 | 实现 |
|------|---------|--------|------|
| Step 5 后 | 新增用例建议 | 用例可能不符合业务理解 | AskUserQuestion 多选 |
| Step 5 后 | 修改用例断言 | 断言修改可能改变评测标准 | AskUserQuestion 单选 |
| Step 5 后 | 废弃用例建议 | 用例可能有业务价值不能删 | AskUserQuestion 单选 |
| Step 5 后 | spec 变更 | 业务规则变更需确认 | AskUserQuestion 确认 |
| Step 8 后 | 质量分变化 | 确认提升方向正确 | 报告展示 |

**非交互模式**（CI/CD）：`--non-interactive` 或 `--auto-apply`，全部接受建议。

## 7. 子 skill 设计：test-case-self-optimization

`skills/test-case-self-optimization/SKILL.md` 的 prompt 指导 Agent：

1. 读上一轮 `reports/<run_id>_diagnosis.json`
2. 调 `case_optimizer.py --run <run_id> --dry-run` 生成建议 JSON
3. 读建议 JSON，用 AskUserQuestion 逐条问用户接受/拒绝/修改
4. 用户确认后调 `case_optimizer.py --run <run_id> --apply` 写入 cases YAML
5. 调 `case_iteration_report.py --run <run_id>` 生成迭代报告
6. 展示报告，记录到 memory_kb

**脚本零 LLM 原则**：case_optimizer.py 只做确定性分析 + 建议生成（基于规则映射 F-type → case template）。真正"生成新用例内容"的创造性工作由 Agent（Claude）读建议 JSON 后用 Task 工具完成，或由 test-case-generator 子 skill 复用。

## 8. 实现清单

### 8.1 新增脚本（scripts/）

| 脚本 | 职责 | LLM | CLI |
|------|------|-----|-----|
| `case_io.py` | cases YAML 读写，保留完整 schema，diff，校验 | 零 | `--read/--write/--validate/--diff` |
| `case_quality_checker.py` | 12 维度确定性质量检查 | 零 | `--config --split [--out]` |
| `case_optimizer.py` | 错误分布+缺口+建议生成+apply | 零 | `--config --run --split [--apply] [--dry-run] [--non-interactive]` |
| `mutation_generator.py` | 变异生成 + kill matrix | 零 | `--config --run --split [--out]` |
| `case_iteration_report.py` | 迭代报告 MD + HTML | 零 | `--config --proposal <id> [--run <run_id>]` |

### 8.2 新增子 skill

`skills/test-case-self-optimization/SKILL.md` — 自优化编排 prompt + AskUserQuestion 指示

### 8.3 扩展子 skill

- `skills/requirements-analysis/SKILL.md` — 吸收 UC 15 字段 + testspec 4 表
- `skills/test-case-generator/SKILL.md` — 吸收 16 项自检 + 五层断言
- `skills/orchestrator/SKILL.md` — 新增阶段 4.5 用例自优化

### 8.4 扩展 config.yaml

```yaml
case_optimization:
  enabled: true
  concentration_threshold: 0.4   # F 类集中阈值
  min_concentration_count: 3     # F 类集中最小绝对数
  quality_threshold: 0.75        # 质量分阈值，低于触发增强
  low_score_dimension: 0.6       # 单维低分阈值
  mutation_types: [mut_skip_tool, mut_repeat_tool, mut_wrong_param, mut_empty_result, mut_hallucinate, mut_redundant_steps]
  auto_apply: false              # CI 模式自动 apply
```

### 8.5 扩展 cases YAML schema

新增字段（向后兼容，旧用例无这些字段也能跑）：
```yaml
cases:
  - id: ...
    # ... 原有字段 ...
    test_level: gray_box          # black_box | gray_box | white_box
    category: functional          # functional | dfx_security | dfx_reliability | dfx_performance | adversarial
    lifecycle: active             # active | deprecated | draft
    dimension_id: DIM-001         # 关联需求维度（spec 缺口分析用）
    scenario_id: SC-001           # 关联需求场景
```

### 8.6 扩展 scoring.hard_fail_if

新增可断言的硬失败条件：
- `step_count_exceeds_1.5x` — 实际步数 > expected_steps * 1.5
- `tool_repeat_3x` — 同一工具同参数调用 ≥ 3 次
- `hallucination_detected` — final 含 trace 没有的数字
- `missing_memory_use` — 期望记忆使用但无 memory_retrieval 事件

## 9. 与主分支 eval loop 的关系

用例自优化**不替代**主分支的 prompt 自优化，而是**补充**：

```
一轮评测完成
  ↓
[主分支] prompt 自优化（改被测 Agent）
  - reference_optimizer.py → 注入 reference
  - mutator.py → 生成 patch 计划
  - auto_patcher.py → A/B + Gatekeeper + git commit/rollback
  ↓
[V1.1 新增] 用例自优化（改测试本身）
  - case_quality_checker.py → 12 维质量分
  - case_optimizer.py → 生成增强建议
  - mutation_generator.py → kill matrix
  - case_io.py --apply → 更新 cases YAML
  - case_iteration_report.py → 迭代报告
  ↓
重跑评测（用更新后的 cases + 优化后的 Agent）
  ↓
双闭环：Agent 越来越准，测试越来越全
```

## 10. 业界参考

| 来源 | 借鉴点 | 实现位置 |
|------|--------|---------|
| Meta ACH (arXiv 2501.12862) | Mutation kill matrix → 补测 | mutation_generator.py |
| Opik HRPO | 根因分析思路迁移到用例 | case_optimizer 错误分布分析 |
| Opik GEPA | Pareto 搜索迁移到用例质量多目标 | 12 维加权质量分 |
| DeepEval Synthesizer | Golden→TestCase 分层 | test-case-generator 子 skill |
| arXiv 2505.07270 | 二义性自动修复 | case_quality_checker 维度 7 |
| ISO 25010 | DFX 质量子特性 | case_quality_checker 维度 4 |
| IEEE 829 | 用例字段完整性标准 | case_quality_checker 维度 2 |
| TIOBE Quality Indicator | 质量聚合指标 | 12 维加权总分 |
| agent-chaos (GitHub) | Agent 韧性测试注入 | mutation_generator 变异类型 |

## 11. 验收标准

- [x] case_io.py 能读写 cases YAML 保留完整 schema（含新增 test_level/category/lifecycle/dimension_id 字段）
- [x] case_quality_checker.py 输出 12 维评分，权重合计 1.00
- [x] case_optimizer.py 能从 diagnosis 生成 add/modify/deprecate/spec_changes 四类建议
- [x] mutation_generator.py 能生成 6 类变异并产出 kill matrix
- [x] case_iteration_report.py 能生成 MD + HTML 报告，含质量分变化/覆盖率变化/mutation 检出率
- [x] test-case-self-optimization 子 skill 能编排完整 8 步流程
- [x] 端到端：mock 跑一轮 → 诊断 → 用例自优化 → apply → 重跑 → 质量分提升
- [x] --non-interactive 模式可在 CI 跑通
