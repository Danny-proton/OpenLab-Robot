# Guide 10 — 外部优化器集成 (v1)

v1 把 DeepEval 和 Opik 作为**可选 provider**接入，不让它们控制流程。

## 核心原则

**外部优化器只生成候选，本地 A/B 门禁决定接受。**

```
UATR trace + cases.yaml
        │
        ├─→ deepeval_adapter.py  ─→ DeepEval metrics ─→ deepeval_scores.json
        │                                                    │
        ├─→ opik_adapter.py     ─→ Opik optimizer   ─→ opik_suggestions.json
        │                                                    │
        ▼                                                    ▼
rule_based mutator.py  ──────────────────→  patch_manager.py（统一管理候选）
                                                         │
                                                         ▼
                                                   abtest.py + multi_judge.py
                                                         │
                                                         ▼
                                                   Gatekeeper（本地门禁）
                                                         │
                                                    ACCEPT / REJECT
```

## DeepEval 集成

DeepEval 适合做 v1 的**metric provider**，不是优化调度中心。

### 接入的 metrics

| DeepEval 能力 | v1 用途 |
|--------------|---------|
| G-Eval | 自定义业务质量评分 |
| Tool Correctness | 工具调用正确性 |
| DAGMetric | 复杂业务规则做成决策树 |
| Conversational G-Eval | 多轮 Agent 对话评测 |
| PromptOptimizer | prompt 优化（生成候选） |

### 用法

```bash
# 跑 DeepEval metrics（未安装 deepeval 时自动用 fallback）
python deepeval_adapter.py --config .agent-eval/config.yaml --run <run_id>
```

输出 `<run_id>.deepeval.json`：

```json
{
  "provider": "deepeval",
  "results": [
    {"case_id": "loan_risk_001", "g_eval_score": 0.8, "tool_correctness": 0.67}
  ]
}
```

### Fallback 模式

如果没装 deepeval（`pip install deepeval`），自动用规则模拟：
- G-Eval → 检查 expected_output 关键词是否在 actual_output
- Tool Correctness → required tools 是否都调用

Fallback 不如真实 DeepEval 准，但保证流程可跑。

## Opik 集成

Opik v1 已经是 Agent Optimizer，支持 MetaPrompt / HRPO / Evolutionary / GEPA。

### 接入的优化器

| Opik 优化器 | 适用场景 | v1 状态 |
|------------|---------|---------|
| MetaPrompt | 简单 prompt 优化 | adapter 已实现 |
| HRPO | 层次化 root cause + 针对性改进 | adapter 已实现 |
| Evolutionary | 进化算法 | adapter 已实现 |
| GEPA | 梯度引导 | adapter 已实现 |

### 用法

```bash
# 只导出 Opik dataset
python opik_adapter.py --config .agent-eval/config.yaml --run <run_id> --export-only

# 跑 MetaPrompt 优化器
python opik_adapter.py --config .agent-eval/config.yaml --run <run_id> --optimizer meta_prompt

# 跑 HRPO
python opik_adapter.py --config .agent-eval/config.yaml --run <run_id> --optimizer hrpo
```

输出 `<run_id>.opik_<optimizer>.json`。

### Fallback 模式

没装 opik 时，基于诊断结果生成简单的 rule-based 建议（和 mutator.py 类似但格式不同）。

### 重要约束

- ❌ **不让 Opik 决定接受/拒绝**——Gatekeeper 用本地规则
- ❌ **不让 Opik 直接改代码**——Opik 只生成建议，PatchWriter 才改代码
- ✅ **Opik 生成的候选进入 patch_manager 统一管理**
- ✅ **Opik 优化结果仍要过 A/B + 回归**

## Patch Candidate Manager

`patch_manager.py` 统一管理来自多个源的候选：

```bash
# 收集所有候选
python patch_manager.py --config .agent-eval/config.yaml --run <run_id> --collect

# 收集并排序
python patch_manager.py --config .agent-eval/config.yaml --run <run_id> --collect --rank

# 接受某个 patch
python patch_manager.py --config .agent-eval/config.yaml --accept <patch_id>
```

排序优先级：
1. rule_based（最可靠，最小改动）
2. deepeval（LLM 优化，需验证）
3. opik（外部优化器，需验证）

## 为什么不直接用 Opik 接管

1. **本地优先**：核心资产（case / trace / score / patch history）必须在本地，不依赖外部服务
2. **可回滚**：Opik 优化可能引入回归，必须能回滚
3. **可审计**：每个 patch 的接受/拒绝必须有明确规则和证据
4. **成本控制**：Opik 优化可能很贵，不应该自动跑

## 接 DeepEval / Opik 的步骤

### 接 DeepEval

```bash
pip install deepeval
# 配置 OPENAI_API_KEY（DeepEval 默认用 OpenAI 做 LLM judge）
export OPENAI_API_KEY=...
```

然后 `deepeval_adapter.py` 自动检测到 deepeval，用真实 metrics。

### 接 Opik

```bash
pip install opik
# 配置 Opik API key
export OPIK_API_KEY=...
opik configure
```

然后 `opik_adapter.py` 自动检测到 opik，用真实优化器。

## v1 不做的

- ❌ 不让 DeepEval 控制评测流程（只做 metric provider）
- ❌ 不让 Opik 直接改代码或接受 patch
- ❌ 不强制要求装 DeepEval / Opik（fallback 保证可跑）
- ❌ 不做 Opik 的在线 experiment 管理（v2 再考虑）
