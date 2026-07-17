# PRD — 总流程管控

> 参考 Opik Experiment/Langfuse Score 机制，设计本地化的流程管控。

## 1. Experiment 机制（参考 Opik）

### 概念
Experiment = Dataset × Execution × Score

```
Dataset（cases YAML）
  ↓
Execution（eval_runner，生成 trace + scores）
  ↓
Score（5硬+3软+TRACE五维+F1-F8+9 Judge）
  ↓
Experiment 记录（run_id 关联三者）
```

### 本地实现
- Dataset = `.agent-eval/cases/<split>.yaml`
- Execution = `.agent-eval/runs/<run_id>.jsonl` + `.agent-eval/traces/<run_id>.jsonl`
- Score = `.agent-eval/scores/<run_id>.json`
- Experiment 索引 = `.agent-eval/data/experiments.jsonl`（append-only）

### experiment 记录格式
```json
{
  "experiment_id": "exp_001",
  "run_id": "20260715-...",
  "dataset": "cases/train.yaml",
  "variant": "baseline",
  "scores": {"weighted_score": 0.723, "n_hard_fail": 1},
  "diagnosis": {"F3.1": 1, "F7.3": 2},
  "timestamp": "2026-07-15T...",
  "tags": ["baseline", "v2.1"]
}
```

## 2. 优化器选择矩阵（参考 Opik 6 种）

| 优化器 | 适用场景 | 输入要求 | 我们的实现 |
|--------|---------|---------|-----------|
| **HRPO** | F8 执行冗余 / 复杂根因 | metric 带 reason | ✅ opik_adapter.py fallback |
| **MetaPrompt** | 通用 prompt 精化 | prompt + dataset | ✅ opik_adapter.py fallback |
| **GEPA** | 单轮重反思 | task + reflection | 🔨 待接 gepa-ai |
| **Evolutionary** | 多目标（分数 vs 长度） | 种群参数 | 🔨 待接 DEAP |
| **Few-Shot Bayesian** | 优化 few-shot 示例 | demonstrations | 🔨 待接 Optuna |
| **Parameter** | 调 temperature/top_p | 参数空间 | 🔨 待接 Optuna TPE |
| **rule_based** | 简单 tool/prompt 改动 | 无 | ✅ mutator.py |
| **DeepEval** | 专业 metric | dataset + 50+指标 | ✅ deepeval_adapter.py |

### 选择流程
```
1. 识别约束（改 prompt / tool / 参数 / 用例？）
2. 检查输入就绪度（metric 有 reason？有 reflection？有 demonstrations？）
3. 按矩阵选
4. 可链式（如 HRPO 找模式 → Parameter 调参）
```

## 3. Score 机制（参考 Langfuse 三源）

### 三源 Score
| 来源 | 说明 | 我们的实现 |
|------|------|-----------|
| API | 脚本自动计算 | ✅ scorer.py |
| EVAL | LLM-as-Judge | ✅ multi_judge.py（9 agent） |
| ANNOTATION | 人工标注 | 🔨 待实现（ask_setup.py 交互） |

### ScoreConfig schema
```yaml
score_configs:
  - name: task_success
    type: numeric
    range: [0, 1]
    source: api
    weight: 0.35
  - name: domain_judge
    type: categorical
    values: [pass, partial, fail]
    source: eval
    weight: 0.10
```

## 4. Spec 版本管理

### 概念
测试 spec（需求/因子/方法选择）作为版本化资产。

### 本地实现
```
.agent-eval/data/
├── requirements.yaml          ← 当前版本
├── requirements.v1.yaml       ← 历史版本
├── test_factors.yaml          ← 测试因子
├── method_selection.yaml      ← 方法选择记录
└── spec_history.jsonl         ← 变更历史（append-only）
```

### spec_history 记录
```json
{
  "version": "v3",
  "timestamp": "...",
  "change": "新增 DIM-011 用户画像覆盖",
  "trigger": "case_optimizer 发现 DIM-007 0 用例",
  "approved_by": "user"
}
```

## 5. 黑/白/灰三档用例管理

| 档位 | 定义 | 输入来源 | 执行方式 | trace 深度 |
|------|------|---------|---------|-----------|
| **黑盒** | 只看输入输出 | PRD / 需求文本 | HTTP 调用 | 仅 final_answer |
| **伪白盒** | 看工具调用轨迹 | SPEC / 代码扫描 + trace 插桩 | HTTP + EvalTraceAdvisor | UATR 24 类事件 |
| **白盒** | 看代码结构 | 代码扫描 + 静态分析 | mock + 代码级断言 | 代码覆盖/分支/函数 |

### 三档用例在 cases YAML 里的标记
```yaml
- id: mb_001
  name: 查询余额
  test_level: black_box        # 或 gray_box / white_box
  input: ...
```

## 6. 执行进度管理

> v1.1.1 升级：进度从"瞬时 stdout"升级为"落盘 + 门户可视化"。详见 [PRD_REPORT_PORTAL.md](PRD_REPORT_PORTAL.md) §3。

### 6.1 三层模型

```
生产者        存储层              消费层
sidecar.py → progress_tracker → report_portal.py / 人工查询
  (stdout)    (data/progress.jsonl, 落盘)   (portal.html Progress 页)
```

### 6.2 sidecar.py 进度 JSON（stdout，向后兼容）
```json
{
  "status": "running",
  "step": 3,
  "step_name": "跑基线",
  "total_steps": 9,
  "run_id": "20260715-...",
  "progress_pct": 33,
  "session_id": "sess_20260715-...",
  "duration_ms": null
}
```

### 6.3 progress_tracker.py 落盘（v1.1.1 新增）

sidecar `--persist`（默认开）自动调 `progress_tracker.emit`，把事件 append 到 `data/progress.jsonl`：

```bash
# 直接查询（不依赖门户）
python progress_tracker.py --config .agent-eval/config.yaml latest      # 最近一条
python progress_tracker.py --config .agent-eval/config.yaml timeline    # 按 session/step 聚合
python progress_tracker.py --config .agent-eval/config.yaml summary     # 总览
```

`timeline` 输出每个 session 的 9 步状态 + duration_ms，供门户 Progress 页直接渲染阶段时间线 + 耗时条形图。

### 6.4 进度可视化（三处）
- **门户 Progress 页**（v1.1.1 新增）：进度环 + 9 步时间线 + 阶段耗时条形图 + 历史会话。★ 主入口
- HTML 报告的"执行摘要"节
- Dashboard 的 Overview 页
- CI 日志的 sidecar stdout（CI 用 `--no-persist` 关闭落盘）

### 6.5 埋点插入约定
- orchestrator 每步进入/完成调 sidecar（既有契约，不变，sidecar 自动落盘）。
- `eval_runner.py` 每 case 完成后可选轻量埋点（`--extra '{"n_done": i}'`）。
- `case_optimizer.py` apply 前后埋点 step 4.5。

## 7. 用例沉淀

### cases YAML 版本管理
- Git 追踪 cases/ 目录
- 每次自优化后 commit
- commit message 格式：`case-opt: +3 cases (DIM-007), -1 duplicate, quality 0.72→0.81`

### 用例分类
```yaml
cases:
  - id: mb_001
    category: functional         # 功能用例
    lifecycle: active            # active / deprecated / draft
  - id: mb_002
    category: dfx_security       # DFX 安全
    lifecycle: active
  - id: mb_003
    category: adversarial        # 对抗用例
    lifecycle: draft
```

## 8. 测试方法库

### test_method_library.yaml
```yaml
methods:
  - id: eq-class
    name: 等价类划分
    applicable_factors: [input_param, range]
    llm_prompt: "把输入域分成等价类，每类选代表值"
    coverage_type: input_coverage

  - id: boundary
    name: 边界值分析
    applicable_factors: [numeric, range]
    llm_prompt: "测试边界值和边界附近的值"
    coverage_type: boundary_coverage

  - id: state-transition
    name: 状态迁移
    applicable_factors: [multi_turn, state]
    llm_prompt: "识别所有状态和转换路径，测试每条路径"
    coverage_type: state_coverage

  - id: orthogonal
    name: 正交实验
    applicable_factors: [multi_param, combination]
    llm_prompt: "用正交表减少组合数，覆盖主要交互"
    coverage_type: combination_coverage

  - id: decision-table
    name: 决策表
    applicable_factors: [rule, if_then]
    llm_prompt: "列出所有条件组合，生成决策表"
    coverage_type: rule_coverage

  - id: scenario
    name: 场景法
    applicable_factors: [workflow, business_process]
    llm_prompt: "识别完整业务流程，测试正常/异常/替代路径"
    coverage_type: workflow_coverage

  - id: cause-effect
    name: 因果图
    applicable_factors: [causal, constraint]
    llm_prompt: "分析输入条件与输出结果的因果关系"
    coverage_type: causal_coverage
```

## 9. 功能对照（vs Opik）

| Opik 功能 | 我们的状态 | 实现方式 |
|----------|-----------|---------|
| Dataset 管理 | ✅ | cases YAML + Git |
| Experiment | ✅ | experiments.jsonl |
| Optimizer 选择矩阵 | 🔨 | ask_setup.py --stage optimize（待增强为矩阵） |
| Prompt Library | ✅ | agent_assets/ + reference_optimizer |
| Annotation Queue | 🔨 | 待实现（ask_setup.py 交互） |
| Score 三源 | 🔨 | API✅ / EVAL✅ / ANNOTATION🔨 |
| Optimization Studio (no-code) | ❌ | 不做（v0 用 Skill 替代） |
| Dashboard | ✅ | dashboard.py 10 页 |
| Trace 管理 | ✅ | UATR JSONL + trace_normalizer |
| 中断恢复 | ✅ | eval_runner --resume |

## 10. 待实现清单

- [ ] experiments.jsonl 索引（experiment 管理器）
- [ ] test_method_library.yaml（测试方法库）
- [ ] spec_history.jsonl（spec 版本管理）
- [ ] 三档用例标记（black/gray/white box）
- [ ] 用例分类和生命周期管理
- [ ] ScoreConfig schema 化
- [ ] Annotation Queue（人工标注交互）
- [ ] 优化器选择矩阵 UI（ask_setup 增强）
- [ ] mutation_generator.py（变异生成）
- [ ] chaos 集成（agent-chaos 接入）
