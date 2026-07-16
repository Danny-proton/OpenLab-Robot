# Guide 06 — Patch 接受规则

这份指南定义：什么时候接受一个 candidate patch，什么时候拒绝并回滚。**接受规则是机械的，不允许人工主观判断**。

## 接受规则

一个 candidate patch 必须同时满足以下**全部**条件才能被接受：

```
accept if:
  1. candidate.train_score > baseline.train_score + 0.03
  2. candidate.regression_hard_fail_count == 0
  3. candidate.forbidden_tool_violation_count == 0
  4. candidate 没有引入新的 failure_type（即 candidate 的失败集合 ⊆ baseline 的失败集合）
  5. candidate 在 train split 上的 latency_p50 不超过 baseline 的 1.5 倍
```

任何一条不满足，**直接拒绝**，不需要解释"为什么这次可以例外"。

## 为什么是这些条件

1. **train_score 提升 ≥ 0.03**：低于 0.03 的提升在 LLM 抖动范围内，不可信。这个阈值可以根据 case 数调整——case 数 ≥ 50 时可以降到 0.02，case 数 < 10 时应该升到 0.05。
2. **regression 零硬失败**：硬失败意味着违反业务规则或调用了 forbidden 工具，这是不可接受的回归。
3. **零 forbidden tool 违规**：即使其他指标好，调用了 forbidden 工具就是不可接受。
4. **无新 failure_type**：candidate 可以没修好所有问题，但不能引入新问题。例如 baseline 只有 F3，candidate 出现 F5，就是回归。
5. **latency 不超 1.5 倍**：防止"加了一堆 advisor 让正确率上去但延迟爆炸"的退化。

## 拒绝时的处理

拒绝一个 candidate 不意味着白做。`abtest.py` 会把拒绝原因写到报告里：

- 如果是条件 1 不满足：说明 patch 没修掉目标失败，重新看诊断是否归因对。
- 如果是条件 2/3 不满足：说明 patch 引入了新硬失败，**立即回滚** patch，不要尝试"小修小补再 A/B"。
- 如果是条件 4 不满足：说明 patch 改了一个组件但破坏了另一个组件，重新归因。
- 如果是条件 5 不满足：说明 patch 加了太多 advisor / 检索，考虑用更轻量的 mutation。

## 多 candidate 选优

如果一次生成了多个 candidate（budget > 1），abtest 会全部跑，按以下顺序选：

1. 满足全部接受条件的 candidate 中，`train_score` 最高的。
2. 如果多个 candidate 都满足条件，选 `latency_p50` 最低的。
3. 如果都不满足，选"拒绝原因最少"的作为下一轮迭代的起点（但**不接受**）。

## A/B 报告内容

`reports/abtest_<baseline>_vs_<candidate>.md` 必须包含：

- baseline run_id 和 candidate run_id
- candidate patch 文件路径
- 5 条接受条件的逐条判定（pass / fail + 数值）
- 单 case 分数对比表（按 case_id 列出 baseline 分 / candidate 分 / delta）
- 失败 case 对比（baseline 失败但 candidate 通过的、candidate 新失败的）
- 最终建议：`ACCEPT` / `REJECT` / `INCONCLUSIVE`

`INCONCLUSIVE` 用于：candidate 和 baseline 在 train 上完全相同（既不提升也不退化），说明 patch 实际没生效。这种情况要检查 patch 是否真的 apply 了。

## 回滚

如果 candidate 被拒绝，用户/Claude Code 必须手动 `git revert` patch。`abtest.py` 不会自动回滚——自动回滚风险太大（可能误删用户的其他改动）。

回滚后，下一轮迭代可以从 baseline 重新开始，也可以基于"拒绝原因最少"的 candidate 继续。后者更快但更危险，v0 默认从 baseline 重新开始。

## 接受后的操作

接受一个 patch 后：

1. `git commit` patch，commit message 格式：`agent-eval: accept <patch_id> (F<X>.<Y>, +<delta> on train)`。
2. 把这次 accept 记录到 `.agent-eval/reports/accepted_patches.md`（append-only）。
3. 更新 baseline——下一次 A/B 的 baseline 就是这次 accepted 的 candidate。

## 长期追踪

`.agent-eval/reports/accepted_patches.md` 是 append-only 的历史记录，每条记录：

```markdown
## 2026-07-02 accept candidate_003

- patch: .agent-eval/patches/candidate_003.md
- baseline run: 20260702-183000-baseline-loan_v1
- candidate run: 20260702-191500-candidate_003-loan_v1
- failure fixed: F3.1 (loan_risk_001, loan_risk_004)
- train score delta: +0.08 (0.71 → 0.79)
- regression hard fail: 0
- forbidden tool violation: 0
- latency p50 delta: +120ms (3100ms → 3220ms)
- commit: a1b2c3d
```

这份文件是项目"agent 进化史"的单一事实来源。任何"为什么这个 prompt 这么写"的问题，都能在这里找到答案。
