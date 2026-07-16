# Guide 17 — 用例自优化指南（V1.1 新增）

> 本指南说明 agent-eval-v1.1 的用例自优化能力：如何从一轮评测结果自动迭代测试用例集。
> 对应 PRD：`docs/PRD_CASE_SELF_OPTIMIZATION.md`

## 1. 什么是用例自优化

**用例自优化**：完成一轮测试后，基于错误分布分析、spec 缺口、用例质量检查、mutation kill matrix，自动迭代测试用例集，使下一轮测试的覆盖度和有效率提升。

与 prompt 自优化的区别：
- prompt 自优化改的是**被测 Agent**（prompt/tool/workflow/reference）—— 由 `reference_optimizer.py` / `auto_patcher.py` 实现
- 用例自优化改的是**测试本身**（case/spec/因子）—— 由 V1.1 新增脚本实现

两者正交，可同时运行，形成双闭环：Agent 越来越准，测试越来越全。

## 2. 5 个新增脚本

| 脚本 | 职责 | 零 LLM |
|------|------|--------|
| `case_io.py` | cases YAML 读写，保留完整 canonical schema，校验，diff | ✓ |
| `case_quality_checker.py` | 12 维质量评分（9 标准 + 3 Agent 专属） | ✓ |
| `case_optimizer.py` | 错误分布+缺口+建议生成+apply（核心） | ✓ |
| `mutation_generator.py` | 6 类变异 + kill matrix（参考 Meta ACH） | ✓ |
| `case_iteration_report.py` | 迭代报告 MD + HTML | ✓ |

## 3. 12 维质量评分

| # | 维度 | 权重 | Agent 专属 |
|---|------|------|-----------|
| 1 | SPEC 完整性 | 0.13 | |
| 2 | 用例完整性 | 0.09 | |
| 3 | 功能点覆盖度 | 0.13 | |
| 4 | DFX 覆盖度 | 0.13 | |
| 5 | 有效用例率 | 0.09 | |
| 6 | 执行可行性 | 0.09 | |
| 7 | 无二义性 | 0.09 | |
| 8 | 长度合理 | 0.04 | |
| 9 | 断言可验证 | 0.09 | |
| 10 | 工具覆盖率 | 0.04 | ✓ |
| 11 | 工作流覆盖率 | 0.04 | ✓ |
| 12 | 记忆覆盖率 | 0.04 | ✓ |

权重合计 1.00。阈值：单维 < 0.6 标记低分；总分 < 0.75 触发质量增强。

## 4. 6 类变异（kill matrix）

| 变异 | 行为 | 目标失败类型 |
|------|------|------------|
| mut_skip_tool | 漏调一个 required 工具 | F3.1 |
| mut_repeat_tool | 同工具重复调用 3 次 | F3.3 |
| mut_wrong_param | 工具参数传错 | F4.4 |
| mut_empty_result | 工具返回空结果 | F5.3 |
| mut_hallucinate | final 编造 trace 没有的数字 | F7.4 |
| mut_redundant_steps | 插入多余 model_call | F8.2/F8.4 |

kill matrix：对每条 case 注入 6 类变异，用 diagnoser 检查能否检出。survived 的变异 → 用例需增强。

## 5. 完整 8 步流程

```
完成一轮评测（eval_runner + diagnoser + scorer）
  ↓
Step 1: 错误分布分析 [case_optimizer 内置]
Step 2: Spec 缺口识别 [case_optimizer 内置]
Step 3: 用例质量检查 [case_quality_checker]
Step 4: Mutation 分析 [mutation_generator]
Step 5: 生成增强建议 [case_optimizer] → proposal JSON
Step 6: 与人确认 [AskUserQuestion，子 skill 触发]
Step 7: 更新 cases YAML [case_io --apply]
Step 8: 度量提升 + 报告 [case_iteration_report]
```

## 6. 命令速查

```bash
# 单独跑质量检查
python ${SKILL_DIR}/scripts/case_quality_checker.py --config .agent-eval/config.yaml --split train

# 单独跑 mutation kill matrix
python ${SKILL_DIR}/scripts/mutation_generator.py --config .agent-eval/config.yaml --latest --split train

# 完整自优化（dry-run，只生成建议）
python ${SKILL_DIR}/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train

# 完整自优化（apply，写入 cases YAML）
python ${SKILL_DIR}/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train --apply --non-interactive

# 迭代报告
python ${SKILL_DIR}/scripts/case_iteration_report.py --config .agent-eval/config.yaml --latest

# cases 读写校验
python ${SKILL_DIR}/scripts/case_io.py --config .agent-eval/config.yaml --split train --validate
```

## 7. 端到端示例（mock 系统）

V1.1 的 `examples/.agent-eval/cases/train.yaml` 提供 8 条测试用例，覆盖所有自优化触发点：

| case | mock 行为 | 触发失败 | 自优化触发 |
|------|----------|---------|-----------|
| loan_risk_001 | skip_tool | F3.1 | 错误集中 F3 |
| loan_risk_002 | redundant | F8.2/F8.4 | 错误集中 F8 |
| loan_risk_003 | success | 无 | 过简单检测 |
| loan_risk_004 | empty_result | F5.3 | DFX 缺口 |
| loan_risk_005 | wrong_param | F4.4 | 参数边界 |
| loan_risk_006 | hallucinate | F7.4 | 幻觉检测 |
| loan_risk_007 | no_memory | F6.1 | 记忆缺口 |
| loan_risk_008 | repeat_tool | F3.3 | repeat 断言 |

预期结果：质量分 0.88 → 0.99，mutation 检出率 42%，新增 9 条用例填补缺口。

## 8. 数据契约

### 输入
- `reports/<run_id>_diagnosis.json` — F1-F8 诊断
- `scores/<run_id>.json` — 评分
- `cases/<split>.yaml` — 完整 canonical schema
- `traces/<run_id>.jsonl` — UATR trace（mutation 用）

### 输出
- `data/<proposal_id>.json` — 优化建议（add/modify/deprecate/spec_changes）
- `data/case_iterations.jsonl` — 迭代历史
- `reports/case_quality_<split>.json` — 质量评分
- `reports/case_mutation_<run_id>.json` + `.md` — kill matrix
- `reports/case_iteration_<proposal_id>.md` + `.html` — 迭代报告
- `data/backups/<split>.<ts>.yaml` — cases 备份

## 9. 与主分支 eval loop 的关系

用例自优化插入在阶段 5-7（prompt 自优化）之后、阶段 4（报告）之前：

```
阶段 3: 执行 + 桥接
阶段 5-7: prompt 自优化（改被测 Agent）
阶段 4.5: 用例自优化（改测试本身）← V1.1 新增
阶段 4: 报告（含迭代报告）
```

## 10. 业界对标

| 来源 | 借鉴点 |
|------|--------|
| Meta ACH (arXiv 2501.12862) | Mutation kill matrix |
| Opik HRPO | 根因分析迁移到用例 |
| DeepEval Synthesizer | Golden→TestCase 分层 |
| arXiv 2505.07270 | 二义性自动修复 |
| ISO 25010 | DFX 质量子特性 |
| IEEE 829 | 用例字段完整性 |
| TIOBE Quality Indicator | 质量聚合指标 |

**业界空白**：有 prompt 自优化，无 test-case 自优化产品化。V1.1 填补此空白。
