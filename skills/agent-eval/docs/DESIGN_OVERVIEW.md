# OpenLab AgentEval — 设计总纲

> 本文档是所有 PRD 的顶层索引。
> 基于：业界调研（Opik/DeepEval/Langfuse/Meta ACH/CodaMosa/ISO 25010）+ 用户需求 + agent-eval v2.1.0。

## 一、产品定位

**Agent 测试从"凭感觉"转为"可设计、可度量、可维护"的工程体系。**

不是平台，是 skill 驱动的本地工作流。核心资产在本地、Git 可追踪、可回滚。

## 二、能力全景（6 层）

| 层 | 能力 | 现状 | PRD 文档 |
|----|------|------|---------|
| L1 测试设计 | 需求分解→SPEC解析→因子提取→方法选择→用例生成→自检→自优化 | 20% | [PRD_CASE_SELF_OPTIMIZATION.md](PRD_CASE_SELF_OPTIMIZATION.md) |
| L2 测试执行 | mock/HTTP/OpenLab Robot + UATR trace + 断言验证 | 60% | 已完成 |
| L3 评测诊断 | 5硬+3软+TRACE五维 + F1-F8 + HRPO + 9 Judge | 60% | 已完成 |
| L4 优化回归 | reference注入 + auto_patcher + Gatekeeper + CI | 60% | 已完成 |
| L5 报告可视化 | HTML 11节 + Dashboard 10页 + PDF + CRUD | 50% | 已完成 |
| L6 流程管控 | 用例沉淀/进度监控/spec归档/优化器选择/黑白灰盒管理 | 20% | [PRD_ORCHESTRATION.md](PRD_ORCHESTRATION.md) |

## 三、业界对标

### 差距（要补）
1. 用例自优化空白（业界只有 prompt 自优化）
2. 测试方法库空白（LLM 时代无标准库）
3. 黑/白/灰三档管理空白

### 机会（可抢占）
1. "扫描记忆"概念自建
2. Agent 覆盖率标准未定型
3. Agent DFX 覆盖（韧性 chaos 有雏形）

## 四、文档体系

所有文档在 `skills/agent-eval/docs/`：

| 文档 | 说明 |
|------|------|
| DESIGN_OVERVIEW.md | 本文档（总纲） |
| PRD_CASE_SELF_OPTIMIZATION.md | 用例自优化 PRD |
| PRD_ORCHESTRATION.md | 总流程管控 PRD |
| ADAPTER_SPEC.md | 适配器接口规范 |
| RESEARCH_REPORT.md | 业界调研报告 |

## 五、架构

```
master 分支:
├── skills/agent-eval/              ← 主 skill（通用能力 + 文档）
├── skills/mobile-bank-agent-eval/  ← 定制 skill（独立可部署副本）
├── plugins/marketplace/            ← 插件市场
└── robot-src/                      ← Robot 源码

mobile-bank-agent-eval-dev 分支:
├── skills/agent-eval/              ← 主 skill
└── mobile-bank-agent-eval/         ← 定制 skill（移到根，独立开发）
```

## 六、核心设计决策

1. 用例生成由 Agent 完成，不在脚本里调 LLM
2. 测试方法库是 YAML 配置
3. 用例自优化是显式产品概念（业界空白）
4. 优化器只生成候选，本地 Gatekeeper 决定接受
5. 黑/白/灰三档用例分类管理
6. 数据格式 YAML + JSONL
7. 执行器和用例输入都通过适配器接口解耦
8. 两个 skill 都独立可部署
