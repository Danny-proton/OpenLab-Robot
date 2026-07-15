# OpenLab AgentEval — 设计总纲

> 本文档是所有 PRD 的顶层索引。每个子文档解决一个具体问题。
> 基于：业界调研（Opik/DeepEval/Langfuse/Meta ACH/CodaMosa/ISO 25010）+ 用户需求 + 现有 agent-eval v2.1.0 能力。

---

## 一、产品定位

**Agent 测试从"凭感觉"转为"可设计、可度量、可维护"的工程体系。**

不是平台，是 Claude Code Skill 驱动的本地工作流。核心资产在本地、Git 可追踪、可回滚。

## 二、能力全景（6 层）

| 层 | 能力 | 现状 | PRD 文档 |
|----|------|------|---------|
| L1 测试设计 | 需求分解→SPEC解析→因子提取→方法选择→用例生成→自检→自优化 | 30% | [PRD_TEST_DESIGN.md](PRD_TEST_DESIGN.md) |
| L2 测试执行 | mock/HTTP/OpenLab Robot + UATR trace + 断言验证 | 100% | 已完成（agent-eval） |
| L3 评测诊断 | 5硬+3软+TRACE五维 + F1-F8 + HRPO + 9 Judge | 100% | 已完成（agent-eval） |
| L4 优化回归 | reference注入 + auto_patcher + Gatekeeper + CI | 100% | 已完成（agent-eval） |
| L5 报告可视化 | HTML 11节 + Dashboard 10页 + PDF + CRUD | 95% | 已完成（agent-eval） |
| L6 流程管控 | 用例沉淀/进度监控/spec归档/优化器选择/黑白灰盒管理 | 40% | [PRD_ORCHESTRATION.md](PRD_ORCHESTRATION.md) |

## 三、业界对标（3 个差距 + 3 个机会）

### 差距（要补）
1. **用例自优化空白**：业界只有 prompt 自优化（HRPO/GEPA），没有 test-case 自优化。→ 把 HRPO 根因 + mutation kill matrix 迁移到测试用例。
2. **测试方法库空白**：等价类/边界值/状态迁移/正交/决策表/场景法在 LLM 时代无标准库。→ 建库 + 按因子自动路由。
3. **黑/白/灰三档管理空白**：业界各做各的。→ 统一框架（黑盒=HTTP / 伪白盒=trace 插桩 / 白盒=代码扫描）。

### 机会（可抢占）
1. "扫描记忆"概念——业界没有，自建（接口/工具/轨迹/失败模式四元组）。
2. Agent 覆盖率标准——业界未定型（轨迹/行为/mutation 覆盖）。
3. Agent DFX 覆盖——韧性(chaos)有开源雏形(agent-chaos)，可接入。

### 可直接复用
- DeepEval Golden→TestCase 分层资产模型
- Opik Experiment=Dataset×Execution
- Langfuse Score 三源(API/EVAL/ANNOTATION)+ScoreConfig schema
- Opik 6 种优化器（HRPO/GEPA/MetaPrompt/Evolutionary/Few-Shot Bayesian/Parameter）
- Meta ACH mutation kill matrix
- arXiv 2505.07270 二义性自动修复

## 四、文档体系

```
docs/
├── DESIGN_OVERVIEW.md              ← 本文档（总纲）
├── PRODUCT_README.md               ← 产品介绍（产品角度）
├── PRD_PROGRESS.md                 ← 开发进展与路线图
├── PRD_TEST_DESIGN.md              ← 测试设计 PRD（8 阶段 + DFX + 自优化）
├── PRD_CASE_SELF_OPTIMIZATION.md   ← 用例自优化 PRD（错误分布→迭代→质量度量）
├── PRD_ORCHESTRATION.md            ← 总流程管控 PRD（Opik 式管控）
├── TECH_SELECTION.md               ← 技术选型分析（为什么选 UATR/HRPO/Skill）
└── RESEARCH_REPORT.md              ← 业界调研报告（完整版）
```

## 五、mobile-bank-agent-eval 独立部署

mobile-bank-agent-eval 必须能独立拿出去用，不依赖 agent-eval 目录。

**方案**：把 agent-eval 的核心脚本复制进 mobile-bank-agent-eval/scripts/，作为内置依赖。

```
mobile-bank-agent-eval/
├── SKILL.md                         ← 主编排
├── scripts/                         ← 全部脚本（含 agent-eval 核心能力）
│   ├── eval_runner.py               ← 从 agent-eval 复制
│   ├── diagnoser.py                 ← 从 agent-eval 复制
│   ├── scorer.py                    ← 从 agent-eval 复制
│   ├── ...（24 个脚本）
│   ├── case_io.py                   ← mobile 特有
│   └── excel_adapter.py             ← mobile 特有
├── skills/                          ← 子 skill
│   ├── requirements-analysis/
│   ├── test-case-design/
│   └── test-case-self-optimization/
├── agents/                          ← 9 个评审 agent
├── docs/                            ← 全部文档
├── guides/
└── examples/
```

## 六、核心设计决策（6 条）

### D1: 用例生成由 Agent 完成，不在脚本里调 LLM
- 子 skill 的 SKILL.md 用 prompt 指导 Agent
- Agent 通过 Task 工具自己生成维度/用例
- 脚本只做确定性 IO（YAML 读写）

### D2: 测试方法库是 YAML 配置，不是代码
- test_method_library.yaml 定义 7 种方法 + 适用因子 + 应用规则
- Agent 读方法库后自己选择和组合

### D3: 用例自优化是显式产品概念
- 完成一轮测试后触发 case_optimizer.py
- 分析 F1-F8 错误分布 → spec 缺口 → 用例质量问题 → 生成增强建议
- 与人确认后更新 cases YAML

### D4: 优化器只生成候选，本地 Gatekeeper 决定接受
- HRPO/GEPA/MetaPrompt 作为可插拔 provider
- 候选 patch 必须过 A/B + 5 条硬规则才能 accept

### D5: 黑/白/灰三档用例分类管理
- 黑盒：HTTP 调用，只看输入输出
- 伪白盒：trace 插桩，看工具调用轨迹
- 白盒：代码扫描，提取工具/参数/Advisor 链

### D6: 数据格式 YAML + JSONL，Git 友好
- cases/config/metrics/mutators 用 YAML
- trace/runs/scores 用 JSONL
- 报告用 HTML/MD
- 不上 SQLite/PostgreSQL（v0 阶段）
