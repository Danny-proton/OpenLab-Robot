# OpenLab AgentEval — 产品介绍

> 让 Agent 的测试从"凭感觉"转为"可设计、可度量、可维护"的工程体系。

## 产品定位

OpenLab AgentEval 是一个 **Agent 评测与优化框架**，为 AI Agent（智能体）提供从测试设计到持续优化的全生命周期质量保障能力。它不是一个测试平台，而是一套 **Claude Code Skill 驱动的本地评测工作流**——核心资产（case / trace / score / patch history）始终在本地、可 Git 追踪、可回滚。

## 核心能力

### 1. 测试设计（Test Design）

| 阶段 | 方法 | 说明 |
|------|------|------|
| 需求分析 | 10 维度覆盖框架 | 业务场景/流程/角色/规则/输入/安全/多轮状态/异常恢复/性能/合规 |
| SPEC 解析 | Agent PRD + 扫描记忆输入 | 从待测 Agent 的 PRD、SPEC、代码扫描结果提取测试因子 |
| 测试因子提取 | 等价类/边界值/状态迁移/正交实验 | 系统化提取测试因子，避免遗漏 |
| 测试方法库 | 方法选择 + 组合应用 | 根据因子类型选择测试方法，组合生成用例 |
| 用例自检 | 格式化/完整性/二义性/DFX 检查 | 生成后自动检查用例质量 |
| **用例自优化** | 错误分布分析 + 迭代增强 | 完成一轮测试后，分析 F1-F8 错误分布，增强 spec/因子/用例 |

### 2. 测试执行（Test Execution）

| 能力 | 说明 |
|------|------|
| 多模式适配 | mock / HTTP / OpenLab Robot (cc-haha) subprocess |
| UATR Trace | 24 类事件，OpenTelemetry 兼容，含调用结构树 |
| 断言验证 | exact_match / contains / regex / status_code / llm_judge |
| F1-F8 失败归因 | 8 类失败（含 F8 执行冗余：轮数过多/重复规划/探索式徘徊）|

### 3. 评测与诊断（Evaluation & Diagnosis）

| 能力 | 说明 |
|------|------|
| 5 硬指标 | task_success / tool_correctness / business_rule / output_schema / efficiency |
| 3 软指标 | answer_relevance / evidence_faithfulness / step_efficiency |
| TRACE 五维 | Trust / Reliability / Adaptability / Convention / Effectiveness |
| HRPO 层次化根因 | 现象 → 直接原因 → 根因 → 修复层（4 层分析）|
| 9 个评审 Agent | DomainJudge / ToolTraceJudge / WorkflowJudge / FaithfulnessJudge / RegressionJudge / SafetyJudge / Gatekeeper / OptimizerPlanner / PatchWriter |
| Judge Agreement Matrix | Judge 之间一致率，检测评测标准清晰度 |

### 4. 优化与回归（Optimization & Regression）

| 能力 | 说明 |
|------|------|
| reference 自动注入 | 8 个模板（执行路径/工具决策树/字段映射/行动约束等）|
| auto_patcher 全自动 | 生成 reference → apply → A/B → 评审 → accept(git commit)/reject(git checkout) |
| Gatekeeper 5 条硬规则 | train 提升 + regression 零硬失败 + 零 forbidden + 无新失败 + latency 不爆炸 |
| CI 持续回归 | exit 0/1，last_known_good 机制，GitHub Actions 集成 |
| DeepEval/Opik 集成 | 可插拔 metric provider / optimizer provider，本地门禁决定接受 |

### 5. 报告与可视化（Reporting & Visualization）

| 能力 | 说明 |
|------|------|
| HTML 报告 | 11 节结构 + 9 SVG 图表 + trace 调用结构树 + 失败归因 Pareto |
| 交互式 Dashboard | 10 页暗色主题 |
| PDF 报告 | weasyprint HTML→PDF |
| Markdown 报告 | 轻量文本格式 |
| 报告 CRUD 管理 | list / get / search / update / delete / reindex |

### 6. 总流程管控（Orchestration）

| 能力 | 说明 |
|------|------|
| 用例沉淀 | cases YAML 版本管理，Git 追踪 |
| 阶段报告存储 | 每轮评测产物归档 |
| 进度监控 | sidecar.py 标准化进度 JSON |
| Spec 归档 | 需求/spec/因子版本化 |
| Agent 优化器选择 | rule_based / HRPO / DeepEval / Opik GEPA |
| 黑/白/伪白盒用例管理 | 黑盒=HTTP / 伪白盒=trace 插桩 / 白盒=代码扫描 |

## 技术架构

```
Claude Code Skill
├── agent-eval/                    ← 主轴（评测 + 优化）
│   ├── scripts/ (24 个)
│   ├── agents/ (9 个评审 agent)
│   └── guides/ (15 篇)
├── mobile-bank-agent-eval/        ← 支线（用例生成）
│   ├── skills/ (2 个子 skill)
│   └── scripts/ (2 个：case_io + excel_adapter)
└── plugins/marketplace/           ← 插件市场
    ├── TaaS-MCP/                  ← TaaS 测试系统
    └── chrome-devtools-mcp/       ← Chrome 调试 (6 skill)
```

## 选型依据

| 组件 | 选型 | 理由 |
|------|------|------|
| Trace 格式 | UATR (兼容 OpenTelemetry) | 本地优先，可导出到 Opik/Langfuse |
| 优化器 | HRPO (主) + DeepEval/Opik (可插拔) | HRPO 最适合 F8 执行冗余 |
| 评测协议 | Claude Code Skill + Agent | 原生集成，无需额外平台 |
| 数据格式 | YAML + JSONL | Git 友好，人类可读 |

详见 [选型分析文档](TECH_SELECTION.md)。

## License

MIT
