# Guide 12 — CI 持续回归 (v1)

v1 支持 CI 集成，在每次代码变更后自动跑回归评测，检测是否引入回归。

## 核心命令

```bash
# CI 模式（exit 0 = 通过，1 = 回归）
python ci_regression.py --config .agent-eval/config.yaml \
    --baseline-run <last_known_good_run_id> \
    --split regression \
    --ci

# 标记某个 run 为 last_known_good
python ci_regression.py --config .agent-eval/config.yaml \
    --mark-good <run_id>
```

## CI 集成示例

### GitHub Actions

```yaml
name: Agent Eval Regression
on: [push, pull_request]

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install deps
        run: pip install pyyaml
      - name: Start Spring AI Agent
        run: |
          # 启动你的 agent 服务
          ./gradlew bootRun &
          sleep 30
      - name: Run regression test
        run: |
          python .claude/skills/agent-eval/scripts/ci_regression.py \
            --config .agent-eval/config.yaml \
            --split regression \
            --ci
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: agent-eval-report
          path: .agent-eval/reports/
```

### GitLab CI

```yaml
agent-eval:
  script:
    - python .claude/skills/agent-eval/scripts/ci_regression.py
        --config .agent-eval/config.yaml --ci
  artifacts:
    paths:
      - .agent-eval/reports/
```

## CI 判定逻辑

CI 模式下，`ci_regression.py` 做以下检查：

1. **跑当前版本** 在 regression split 上
2. **对比 last_known_good**（如果存在）
3. **跑 RegressionJudge**（multi_judge.py 的一部分）
4. **检查硬失败数**：current > baseline → FAIL
5. **检查 forbidden tool**：current 有 forbidden violation → FAIL
6. **检查 RegressionJudge verdict**：fail → FAIL

任何一条触发 → exit 1，CI 失败。

## last_known_good 机制

`.agent-eval/last_known_good.json`：

```json
{
  "run_id": "20260702-120000-baseline-v1",
  "marked_at": "2026-07-02T12:00:00+09:00"
}
```

- 第一次跑 CI 时没有 last_known_good，只跑当前版本，不对比
- 手动标记：`--mark-good <run_id>`（通常在 accept patch 后执行）
- CI 通过后，可以自动 mark-good（在 CI 脚本里加 `--mark-good` 步骤）

## Regression Trend

每次 CI 跑都会追加一条记录到 `.agent-eval/regression_trend.jsonl`：

```json
{"ts": "2026-07-02T12:42:00+09:00", "current_run_id": "...", "baseline_run_id": "...",
 "passed": true, "weighted_score": 0.85, "n_hard_fail": 0}
```

这个文件是 append-only 的历史记录，可以在 Dashboard 的 "Regression" 页面查看趋势。

## 推荐工作流

1. **开发阶段**：在 train split 上迭代优化（用 eval_runner + multi_judge + mutator + abtest）
2. **合并前**：在 PR 里跑 CI regression，确保不破坏旧能力
3. **合并后**：手动或自动 `--mark-good`，更新 last_known_good
4. **周期性**：每周跑 adversarial split，发现边缘场景问题

## v1 不做的

- ❌ 不做生产流量在线监控（v2）
- ❌ 不做自动 rollback（人工决策）
- ❌ 不做多项目评测看板（v2）
- ❌ 不做权限与审计（v2）

## 故障排查

**CI 一直 FAIL**：
1. 检查 `.agent-eval/last_known_good.json` 是否指向一个真的好的 run
2. 检查 regression split 的 case 是否过时（业务变化后 case 没更新）
3. 看 `_ci_verdict.json` 里的具体 reasons

**CI 一直 PASS 但实际有回归**：
1. regression split 覆盖不够，加 case
2. RegressionJudge 阈值太松，调 `judge_regression()` 的判定
3. 检查 forbidden tool 列表是否完整
