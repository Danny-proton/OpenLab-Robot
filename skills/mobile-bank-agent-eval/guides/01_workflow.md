# 工作流

## 架构关系

```
agent-eval（主轴）           mobile-bank-agent-eval（支线）
├── 执行（eval_runner）       ├── 用例生成（子 skill + Agent）
├── 评分（scorer）            │   ├── requirements-analysis
├── 诊断（diagnoser）         │   └── test-case-design
├── 多 Judge（multi_judge）   └── YAML IO（case_io.py）
├── 报告（html_report）
├── reference（reference_optimizer）
└── A/B（auto_patcher）
```

## 完整流程

### 1. 用例生成（mobile-bank-agent-eval）

Agent 通过子 skill 自己生成用例：
- `requirements-analysis`：Agent 分析需求 → 10 维度 + 场景 → YAML
- `test-case-design`：Agent 设计用例 → agent-eval 格式 case YAML

### 2. 执行（agent-eval）

```bash
python <agent-eval>/scripts/eval_runner.py --config .agent-eval/config.yaml --split train --variant baseline
```

### 3. 诊断（agent-eval）

```bash
python <agent-eval>/scripts/diagnoser.py --config .agent-eval/config.yaml --latest
```

### 4. 多 Judge（agent-eval）

```bash
python <agent-eval>/scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id>
```

### 5. 报告（agent-eval）

```bash
python <agent-eval>/scripts/html_report.py --config .agent-eval/config.yaml --run <run_id>
```

### 6. reference + A/B（agent-eval）

```bash
python <agent-eval>/scripts/reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply
python <agent-eval>/scripts/auto_patcher.py --config .agent-eval/config.yaml --baseline-run <run_id> --split regression --auto-apply
```
