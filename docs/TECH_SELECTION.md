# 技术选型分析

## 设计思路回顾

最开始的设计原则（来自对话第一条）：

> **不要做"Agent 评测平台"，先做"Agent 行为回归测试 + 自动修复 Skill"。**
> 它的核心不是 dashboard，而是：case → trace → score → diagnosis → patch → A/B → rollback。

这个原则贯穿了所有选型决策。

---

## 选型决策

### 1. Trace 格式：UATR（兼容 OpenTelemetry）

**候选**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 原始 OpenTelemetry | 标准、生态好 | 部署成本高（Collector + 后端）、字段不可控、默认不导出 prompt/completion |
| 自定义 JSONL | 简单、灵活 | 无标准、不可互操作 |
| **UATR（兼容 OTel）** | 本地优先、字段可控、可导出到 OTel 平台 | 需要自己维护 schema |

**选择理由**：
- v0 阶段不上 OTel Collector + ClickHouse + Postgres，太重
- 但需要对齐 OTel GenAI semantic conventions（gen_ai.system / gen_ai.operation.name）
- UATR 24 类事件覆盖 Agent 全生命周期，OTel 没有
- 未来接 Opik/Langfuse 只需加 exporter

**关键设计**：
- `schema_version: uatr-0.5` 标识格式
- `attributes` 字段兼容 OTel（gen_ai.system / gen_ai.operation.name）
- `span_id` / `parent_span_id` 支持嵌套调用链
- artifact 引用（content_ref + content_hash）避免 trace 文件过大

### 2. 优化器：HRPO 为主 + DeepEval/Opik 可插拔

**候选**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 贝叶斯优化 | 理论最优 | 需要大量样本，v0 的 case 数（20-50）撑不起 |
| GEPA（梯度引导） | 前沿 | 需要明确的"prompt 基因"表示，迭代成本高 |
| Opik MetaPrompt | 官方支持 | 需要部署 Opik server |
| Opik HRPO | 层次化根因，针对性强 | 需要部署 Opik server |
| **自研 HRPO fallback** | 本地可跑、4 层分析、映射到 reference | 不如真实 Opik HRPO 精细 |
| DeepEval PromptOptimizer | 有 API | 依赖 OpenAI、成本高 |

**选择理由**：
- v0 核心是"失败归因 → 定向改 Agent 组件"，不是玄学搜索
- HRPO（Hierarchical Root cause analysis Prompt Optimization）最适合 F8 执行冗余
- HRPO 的 4 层分析（现象→直接原因→根因→修复层）直接映射到 reference 注入
- Opik/DeepEval 作为可插拔 provider，不进入核心路径
- 外部优化器只生成候选，**本地 Gatekeeper 决定接受**

**集成策略**：
```
UATR trace + cases.yaml
  ↓
opik_adapter.py（HRPO fallback 或真实 Opik）
  ↓
候选 patch
  ↓
本地 A/B + Gatekeeper → accept/reject
```

### 3. 评测协议：Claude Code Skill + Agent

**候选**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| Opik 平台 | 完整 UI + experiment 管理 | 需部署、不是 Claude Code 原生 |
| Langfuse | 观测好 | 主要是观测不是评测 |
| DeepEval | Python 库 | 不是工作流 |
| **Claude Code Skill** | 原生集成、Agent 自动委托、无基础设施 | 依赖 Claude Code |

**选择理由**：
- 用户的使用方是 OpenLab Robot（基于 cc-haha / Claude Code 复现）
- Claude Code 的 Skill 机制已支持：动态上下文注入、子 Agent 隔离执行、A/B 评测
- 用 Skill 不需要额外平台，文件即事实来源
- 9 个评审 Agent 用标准 frontmatter，Claude 自动委托

### 4. 数据格式：YAML + JSONL

**候选**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| SQLite | 查询方便 | 不 Git 友好、二进制 |
| PostgreSQL | 强大 | 需部署 |
| **YAML + JSONL** | Git 友好、人类可读、无依赖 | 查询不如 SQL |

**选择理由**：
- 核心资产（cases / config / mutators / metrics）用 YAML — 可读可 Git
- 运行产物（trace / runs / scores）用 JSONL — 追加写、一行一条
- 报告用 HTML/MD — 可分享
- 未来需要 SQL 查询时加一个 SQLite 索引层即可

### 5. 评审机制：9 个 Agent + Agreement Matrix

**候选**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 单一 LLM judge | 简单 | 不客观、不可复现 |
| 多人评审 | 准确 | 慢、成本高 |
| **多 Agent 评审** | 确定性（规则型）+ 智能（LLM 型）| 需要 9 个 agent 定义 |

**选择理由**：
- 6 个规则型 Judge 确定性、无成本、可复现
- 3 个 LLM 型 Agent（OptimizerPlanner / PatchWriter / Gatekeeper）处理复杂判断
- Agreement Matrix 检测 Judge 之间分歧，低于 0.5 说明评测标准有问题
- SafetyJudge 一票否决机制保证安全
- 关键设计：**PatchWriter 是唯一能改代码的**，避免"自己改自己评"

### 6. 执行适配器：mock / http / openlab_robot

**候选**：

| 方案 | 适用 | 优点 | 缺点 |
|------|------|------|------|
| mock | 测试 pipeline | 无需后端 | 不测真实 agent |
| http | Spring AI / 任意 HTTP agent | 通用 | 黑盒，只能看最终答案 |
| **openlab_robot** | cc-haha / Claude Code | stream-json 协议，trace 完整 | 需装 cc-haha |

**选择理由**：
- mock 保证 pipeline 可跑通（无 API key 也能验证）
- http 覆盖大部分 Spring AI agent
- openlab_robot 用 subprocess + stream-json，获取完整 SDK 消息流
- adapter 机制解耦：新增执行模式只改 common.py call_adapter

---

## 业界对比

### vs Opik

| 维度 | OpenLab AgentEval | Opik |
|------|-------------------|------|
| 定位 | 本地评测工作流 | Agent 优化平台 |
| 部署 | 零基础设施 | 需 server + ClickHouse |
| Trace | UATR JSONL（本地） | OTel → ClickHouse |
| 优化器 | HRPO fallback + 可接 Opik | MetaPrompt/HRPO/GEPA/Evolutionary |
| 评测 | 9 Agent + F1-F8 + TRACE 五维 | experiment + metric |
| 接受规则 | 本地 Gatekeeper 5 条硬规则 | 平台 UI 人工判断 |
| Claude Code 原生 | ✅ | ❌ |
| 成本 | 零 | 需部署 |

**结论**：Opik 适合大规模 experiment 管理和优化器实验；OpenLab AgentEval 适合本地快速迭代和 Claude Code 原生集成。两者互补——Opik 可作为 v1+ 的 exporter。

### vs DeepEval

| 维度 | OpenLab AgentEval | DeepEval |
|------|-------------------|----------|
| 定位 | 评测+优化工作流 | Metric 库 |
| Metric | 5 硬 + 3 软 + TRACE 五维 | G-Eval / DAGMetric / Tool Correctness |
| 用例管理 | YAML + Git | Python 代码 |
| 优化 | HRPO + reference + auto_patcher | PromptOptimizer |
| 断言 | 5 种（exact/contains/regex/status/llm_judge）| assert_* |
| Claude Code 原生 | ✅ | ❌ |

**结论**：DeepEval 适合作为 metric provider 集成（已实现 deepeval_adapter.py），不作为核心调度。

### vs Langfuse

| 维度 | OpenLab AgentEval | Langfuse |
|------|-------------------|---------|
| 定位 | 评测+优化工作流 | 观测平台 |
| 核心 | case→trace→score→patch→A/B | trace+metric+observation |
| 优化 | 有（HRPO + reference） | 无 |
| 本地优先 | ✅ | ❌（需部署） |

**结论**：Langfuse 适合生产环境在线观测；OpenLab AgentEval 适合开发阶段离线评测。Langfuse 可作为 v2+ 的在线监控 backend。

---

## 为什么不直接用 Opik/Langfuse/DeepEval

1. **v0 核心是"文件化实验系统"不是"平台"**——核心资产在本地、Git 可追踪
2. **Claude Code 原生**——用户的使用方是 cc-haha，Skill 机制天然集成
3. **外部工具是 exporter/provider 不是核心**——Opik/Langfuse/DeepEval 可插拔接入
4. **成本控制**——零基础设施，pip install pyyaml 就能跑
5. **可回滚**——每个 patch 的接受/拒绝有明确规则和 Git 追踪

## 什么时候上 Opik/Langfuse

- **v1+**：需要大规模 experiment 管理时接 Opik
- **v2+**：需要生产在线监控时接 Langfuse
- **任何时候**：需要专业 metric 时接 DeepEval（已实现 adapter）
