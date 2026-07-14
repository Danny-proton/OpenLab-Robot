# Guide 09 — 多评审 Agent 体系 (v1)

v1 引入多 Agent 评审。9 个 Agent.md 定义角色，multi_judge.py 调度聚合。

## 9 个评审 Agent

| Agent | 职责 | 能改代码 | 实现方式 |
|-------|------|---------|---------|
| DomainJudge | 业务规则覆盖 | ❌ | 规则型（Python） |
| ToolTraceJudge | 工具调用轨迹 | ❌ | 规则型 |
| WorkflowJudge | 流程完整性 | ❌ | 规则型 |
| FaithfulnessJudge | 证据一致性 | ❌ | 规则型 |
| RegressionJudge | 回归风险 | ❌ | 规则型（仅 A/B 模式） |
| SafetyJudge | 安全合规（可一票否决） | ❌ | 规则型 |
| OptimizerPlanner | 制定优化计划 | ❌ | LLM 型（Claude Code 按 .md 执行） |
| PatchWriter | 生成代码 patch | ✅（唯一） | LLM 型 |
| Gatekeeper | 接受/拒绝裁决 | ❌ | 规则型 + LLM 型混合 |
| ReportWriter | 撰写报告 | ❌ | LLM 型 |

## 为什么不让 PatchWriter 自己评价自己

v0 的 mutator 既生成 patch 又隐式评价"这个 patch 应该有效"。v1 把这两步分开：
- PatchWriter 只负责按 OptimizerPlanner 的计划写代码
- 评价由 6 个独立 Judge 做
- Gatekeeper 综合 Judge 意见做最终裁决

这样避免了"自己改自己评"的利益冲突。

## 规则型 Judge vs LLM 型 Judge

**规则型**（DomainJudge / ToolTraceJudge / WorkflowJudge / FaithfulnessJudge / RegressionJudge / SafetyJudge）：
- 用 Python 实现在 `multi_judge.py`
- 确定性，可复现
- 不需要 LLM API
- v1 默认用这些

**LLM 型**（OptimizerPlanner / PatchWriter / ReportWriter）：
- 用 Agent.md 定义，由 Claude Code 在调用时按 .md 执行
- 需要 LLM
- 适合复杂判断
- v1 可选：Claude Code 调用 skill 时会自动按这些 .md 行事

**Gatekeeper**：
- 混合实现：`multi_judge.py` 里有规则版的 `gatekeeper_decide()`
- 5 条硬规则机械判定
- LLM 型 Gatekeeper 可以在规则版基础上加"软判断"，但 v1 默认用规则版

## Judge 输出统一格式

每个 Judge 输出一个 JSON：

```json
{
  "case_id": "loan_risk_001",
  "judge": "ToolTraceJudge",
  "score": 0.5,
  "verdict": "partial",
  "failure_types": ["F3.1", "F4.4"],
  "evidence": [
    {"trace_event_id": "span_0006", "reason": "required tool analyze_cashflow not called"}
  ],
  "recommendation": "检查 tool description 和 policy"
}
```

- `score`: 0.0 / 0.5 / 1.0
- `verdict`: pass / partial / fail
- `failure_types`: 引用 F1-F7 taxonomy
- `evidence`: 必须引用具体 trace 事件
- `recommendation`: 给 OptimizerPlanner 的建议

## Gatekeeper 决策规则

ACCEPT 必须同时满足：

1. `abtest_verdict.recommendation == "ACCEPT"`（机械 5 条全过）
2. `RegressionJudge.score >= 0.5`（无严重回归）
3. `SafetyJudge.safety_veto != true`（无安全一票否决）
4. 所有 judge 平均分 >= 0.7
5. Judge 之间无严重分歧（agreement_matrix 最低值 >= 0.5）

任何一条不满足 → REJECT。

## Judge Agreement Matrix

对每对 Judge，统计他们在所有 case 上 verdict 一致的比例：

```
DomainJudge × ToolTraceJudge: 0.85
DomainJudge × WorkflowJudge: 0.72
...
```

- 平均一致率 >= 0.7：judge 们观点一致，结论可信
- 平均一致率 0.5-0.7：有分歧，需要人工复核
- 平均一致率 < 0.5：严重分歧，说明评测标准不清晰或 case 设计有问题

## 使用方式

### 单 run 评审

```bash
python multi_judge.py --config .agent-eval/config.yaml --run <run_id> --split train
```

输出 `<run_id>_judges.json` + `<run_id>_judges.md`。

### A/B 评审（带 RegressionJudge）

```bash
python multi_judge.py --config .agent-eval/config.yaml \
    --abtest <baseline_run_id> <candidate_run_id> --split regression
```

### 在 Claude Code 里

直接说"评审一下这个 run"，Claude Code 会：
1. 调 `multi_judge.py` 跑规则型 Judge
2. 读 `reviewers/*.md` 扮演 LLM 型 Judge（OptimizerPlanner / PatchWriter / ReportWriter）
3. 综合结论给出建议
