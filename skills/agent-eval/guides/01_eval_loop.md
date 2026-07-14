# Guide 01 — 评测循环

这份指南解释 `eval_runner.py` / `scorer.py` / `diagnoser.py` / `mutator.py` / `abtest.py` 如何串起来。跑第一次评测前先读。

## 一轮的形状

```
cases/*.yaml  ──▶  eval_runner.py  ──▶  runs/<run_id>.jsonl
                          │                  │
                          │                  ▼
                  adapter (HTTP/mock)   traces/<run_id>.jsonl
                          │                  │
                          ▼                  ▼
                   raw agent output   scorer.py  ──▶  scores/<run_id>.json
                                                            │
                                                            ▼
                                                    diagnoser.py  ──▶  reports/<run_id>_diagnosis.md
                                                            │
                                                            ▼
                                                    mutator.py  ──▶  patches/candidate_*.md
                                                            │
                                                            ▼
                                                    abtest.py  ──▶  reports/abtest_*.md
                                                            │
                                                            ▼
                                                    (accept / rollback)
```

## run_id 命名约定

`run_id` 格式：`YYYYMMDD-HHMMSS-<variant>-<label>`，例如 `20260702-183000-baseline-loan_v1`。

这样既能按时间排序，也方便 grep 某个 variant。

## `eval_runner.py` 一步步做什么

1. 加载 `.agent-eval/config.yaml`，里面指向：
   - `cases_dir` — case YAML 目录
   - `metrics_dir` — 指标定义目录
   - `adapter` — 用哪个 adapter 文件
   - `traces_dir` / `runs_dir` / `scores_dir` / `reports_dir` / `patches_dir`
2. 从 `cases/<split>.yaml` 加载指定 split（`train` / `regression` / `adversarial`）。
3. 对每条 case：
   a. 生成 `case_run_id` = `<run_id>::<case_id>`。
   b. 用 `case.input` 和 `case_run_id` 调 adapter。adapter 返回 `{final_answer, raw_trace}`。
   c. 把 raw trace 规范化后写到 `traces/<run_id>.jsonl`（一行一个 JSON 对象，schema 见 `02_trace_contract.md`）。
   d. 在 `runs/<run_id>.jsonl` 写一条记录：`{case_id, case_run_id, status, latency_ms, final_answer, trace_path}`。
4. 全部 case 跑完后，进程内调用 `scorer.py` 算单 case + 汇总分数，写到 `scores/<run_id>.json`。
5. 在 `reports/<run_id>.md` 生成基线报告。

## `scorer.py` 算什么

对每条 case，它检查：

- case 里的 `hard_fail_if` 规则（如 `forbidden_tool_called` / `missing_required_business_rule` / `invalid_json_schema`）。任何一条命中，这条 case 就是硬失败，其他分数都不重要。
- `metrics/*.yaml` 里定义的 5 个硬指标 + 3 个软指标。公式见 `03_metric_contract.md`。
- 加权总分：`0.35 * task_success + 0.20 * tool_correctness + 0.20 * business_rule_coverage + 0.15 * output_schema + 0.10 * efficiency - hard_fail_penalty`。

一次 run 的汇总分是所有 case 的均值。但 diagnoser **不**用汇总分——它按单 case 工作。

## `diagnoser.py` 做什么

对每条失败 case，它遍历 trace，把失败归因到 F1–F7 中的一个或多个（见 `04_failure_taxonomy.md`）。每条诊断记录包含：

- `case_id`
- `case_run_id`
- `failure_type`（F1–F7）
- `evidence` — `{event, step, reason}` 列表，引用具体 trace 事件
- `suggested_mutation_target` — 该改哪个组件（prompt / tool_schema / tool_policy / workflow / memory / skill）
- `suggested_mutation_rule` — `mutators/*.yaml` 里的一个 key

diagnoser 永远不会在没有 trace 证据时说"prompt 不好"。

## `mutator.py` 做什么

读诊断文件，在 `mutators/*.yaml` 里查到匹配的 mutation 规则，输出一份 **patch 计划**——一个 markdown 文件，描述应该做的最小改动。它**不会** apply patch（由用户或 Claude Code 手动 apply，然后跑 A/B）。

patch 计划包含：

- `patch_id` — `candidate_<N>`
- `targets` — `{file, change_type, description}` 列表
- `expected_failure_ids` — 这个 patch 应该修掉哪些被诊断的失败
- `risk` — `low` / `medium` / `high`
- `rollback_hint` — 怎么撤销

## `abtest.py` 做什么

接收一个 baseline run_id 和一个 candidate patch。跑 candidate variant（意思是：用户已经把 patch apply 到 agent 上了，`--candidate-patch` 只是记录改了什么）在指定 split 上。对比：

- 单 case 分数 delta
- 硬失败数 delta
- forbidden tool 违规数 delta
- 汇总分 delta

然后按 `06_patch_acceptance.md` 的规则给出 accept / reject 建议。

## 各 split 的角色

| Split | 何时用 | 接受条件 |
|-------|--------|---------|
| `train` | 迭代修复时；小而快 | candidate.train_score > baseline.train_score + 0.03 |
| `regression` | 接受 patch 之前 | candidate.regression_hard_fail == 0 且 candidate.forbidden_tool_violation == 0 |
| `adversarial` | 周期性压测 | 相对上次已知好版本无新增硬失败 |

**永远不要**只凭 `train` 接受 patch。接受前必须跑 `regression`。

## 幂等性

`eval_runner.py` **按 run_id 不幂等**——每次调用都生成新 run_id。这是故意的：每次都想要一份新记录，这样能 diff run。如果想恢复中断的 run，传 `--resume <run_id>`，它会跳过 `runs/<run_id>.jsonl` 里已有记录的 case。
