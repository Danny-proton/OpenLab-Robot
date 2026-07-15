# OpenLab AgentEval — 设计总纲

> 本文档是所有 PRD 的顶层索引。每个子文档解决一个具体问题。
> 基于：业界调研（Opik/DeepEval/Langfuse/Meta ACH/CodaMosa/ISO 25010）+ 用户需求 + 现有 agent-eval v2.1.0 能力。

## 一、产品定位

**Agent 测试从"凭感觉"转为"可设计、可度量、可维护"的工程体系。**

不是平台，是 Claude Code Skill 驱动的本地工作流。核心资产在本地、Git 可追踪、可回滚。

## 二、能力全景（6 层）

| 层 | 能力 | 现状 | PRD 文档 |
|----|------|------|---------|
| L1 测试设计 | 需求分解→SPEC解析→因子提取→方法选择→用例生成→自检→自优化 | 30% | [PRD_CASE_SELF_OPTIMIZATION.md](PRD_CASE_SELF_OPTIMIZATION.md) |
| L2 测试执行 | mock/HTTP/OpenLab Robot + UATR trace + 断言验证 | 100% | 已完成（agent-eval scripts/） |
| L3 评测诊断 | 5硬+3软+TRACE五维 + F1-F8 + HRPO + 9 Judge | 100% | 已完成（agent-eval scripts/） |
| L4 优化回归 | reference注入 + auto_patcher + Gatekeeper + CI | 100% | 已完成（agent-eval scripts/） |
| L5 报告可视化 | HTML 11节 + Dashboard 10页 + PDF + CRUD | 95% | 已完成（agent-eval scripts/） |
| L6 流程管控 | 用例沉淀/进度监控/spec归档/优化器选择/黑白灰盒管理 | 40% | [PRD_ORCHESTRATION.md](PRD_ORCHESTRATION.md) |

## 三、业界对标（3 个差距 + 3 个机会）

### 差距（要补）
1. **用例自优化空白**：业界只有 prompt 自优化（HRPO/GEPA），没有 test-case 自优化。
2. **测试方法库空白**：等价类/边界值/状态迁移/正交/决策表/场景法在 LLM 时代无标准库。
3. **黑/白/灰三档管理空白**：业界各做各的。

### 机会（可抢占）
1. "扫描记忆"概念——业界没有，自建。
2. Agent 覆盖率标准——业界未定型。
3. Agent DFX 覆盖——韧性(chaos)有开源雏形。

### 可直接复用
- DeepEval Golden→TestCase 分层资产模型
- Opik Experiment=Dataset×Execution
- Langfuse Score 三源+ScoreConfig
- Opik 6 种优化器
- Meta ACH mutation kill matrix

## 四、文档体系

所有文档在 `skills/agent-eval/docs/`：

| 文档 | 说明 |
|------|------|
| [DESIGN_OVERVIEW.md](DESIGN_OVERVIEW.md) | 本文档（总纲） |
| [PRD_CASE_SELF_OPTIMIZATION.md](PRD_CASE_SELF_OPTIMIZATION.md) | 用例自优化 PRD |
| [PRD_ORCHESTRATION.md](PRD_ORCHESTRATION.md) | 总流程管控 PRD |
| [ADAPTER_SPEC.md](ADAPTER_SPEC.md) | 适配器接口规范 |
| [RESEARCH_REPORT.md](RESEARCH_REPORT.md) | 业界调研报告（完整版） |

## 五、架构

```
仓库结构（master 分支）:
├── skills/agent-eval/              ← 主 skill（通用能力）
│   ├── scripts/ (25个通用脚本)
│   ├── agents/ (9个评审agent)
│   ├── docs/ (5份文档)
│   └── examples/
├── skills/mobile-bank-agent-eval/  ← 定制 skill（master 上也有副本）
├── plugins/marketplace/            ← 插件市场
└── robot-src/                      ← Robot 源码

mobile-bank-agent-eval-dev 分支:
├── skills/agent-eval/              ← 主 skill（通用能力 + 文档）
└── mobile-bank-agent-eval/         ← 定制 skill（独立可部署）
    ├── scripts/ (26个=24通用+2定制)
    ├── skills/ (2个用例生成子skill)
    ├── adapters/ (3个执行器适配器占位)
    ├── agents/ (9个评审agent)
    └── examples/
```

## 六、核心设计决策

1. 用例生成由 Agent 完成，不在脚本里调 LLM
2. 测试方法库是 YAML 配置，不是代码
3. 用例自优化是显式产品概念（业界空白）
4. 优化器只生成候选，本地 Gatekeeper 决定接受
5. 黑/白/灰三档用例分类管理
6. 数据格式 YAML + JSONL，Git 友好
7. 执行器和用例输入都通过适配器接口解耦
8. 两个 skill 都独立可部署
