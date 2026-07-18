# OpenLab AgentEval V1.1 — 设计总纲

> 本文档是所有 PRD 的顶层索引。
> V1.1 在 v2.3.0-mobile-bank 基础上演进，聚焦**用例自优化**（业界空白）。
> 基于：业界调研（Opik/DeepEval/Langfuse/Meta ACH/CodaMosa/ISO 25010）+ test-design-agent-raw 成熟方法论 + agent-eval v2.3.0。

## 一、产品定位

**Agent 测试从"凭感觉"转为"可设计、可度量、可维护、可自优化"的工程体系。**

不是平台，是 skill 驱动的本地工作流。核心资产在本地、Git 可追踪、可回滚。

V1.1 的核心创新：**用例自优化**——完成一轮测试后自动迭代测试用例集（业界只有 prompt 自优化，无 test-case 自优化产品化）。

## 二、能力全景（6 层）

| 层 | 能力 | V1.1 现状 | PRD 文档 |
|----|------|----------|---------|
| L1 测试设计 | 需求分解→SPEC解析→因子提取→方法选择→用例生成→自检→自优化 | 80% ↑ | [PRD_REQUIREMENT_TESTDESIGN.md](PRD_REQUIREMENT_TESTDESIGN.md) |
| L2 测试执行 | mock/HTTP/OpenLab Robot + UATR trace + 断言验证 | 70% ↑ | [PRD_MOCK_SYSTEM.md](PRD_MOCK_SYSTEM.md) |
| L3 评测诊断 | 5硬+3软+TRACE五维 + F1-F8 + HRPO + 9 Judge | 60% | 已完成 |
| L4 优化回归 | reference注入 + auto_patcher + Gatekeeper + CI + **用例自优化** | 80% ↑ | [PRD_CASE_SELF_OPTIMIZATION.md](PRD_CASE_SELF_OPTIMIZATION.md) |
| L5 报告可视化 | HTML 11节 + Dashboard 10页 + PDF + CRUD + 迭代报告 + **统一门户** + **深色玻璃态重构** | 95% ↑↑ | [PRD_REPORT_PORTAL.md](PRD_REPORT_PORTAL.md) |
| L6 流程管控 | 用例沉淀/**进度埋点落盘**/spec归档/优化器选择/黑白灰盒管理 + **进度门户** | 80% ↑↑ | [PRD_ORCHESTRATION.md](PRD_ORCHESTRATION.md) §6 + [PRD_REPORT_PORTAL.md](PRD_REPORT_PORTAL.md) §3 |

↑ = V1.1 相对 v2.3.0 提升；↑↑ = v1.1.1 本次新增（统一门户 + 进度埋点）。

> **v1.1.2（2026-07-18）**：L5 可视化统一收尾——`html_report.py`（eval loop 12 节深度报告）从旧浅色主题迁入深色玻璃态设计体系（玻璃卡片 + 悬浮发光微动效 + 入场动画 + 热力图/雷达/时间线深色适配 + `prefers-reduced-motion` 支持，打印仍输出浅色），至此 **门户 / 4 阶段报告 / 迭代报告 / eval 深度报告四处视觉完全统一**；同时修复门户 `_load_runs_summary` 未下钻 scores JSON `aggregate` 嵌套导致 Overview 平均分/Run 趋势无数据的问题，KPI 卡改单行布局并加数字 count-up 动画。

## 三、业界对标

### V1.1 补齐的差距
1. **用例自优化**（业界空白）→ case_optimizer + mutation_generator + case_iteration_report
2. **测试方法库**（LLM 时代无标准库）→ 7 方法库 YAML + 方法路由
3. **黑/白/灰三档管理**→ cases YAML test_level 字段
4. **Agent 专属覆盖率**→ 工具/工作流/记忆 3 维

### 仍可抢占的机会
1. "扫描记忆"概念自建
2. Agent 覆盖率标准未定型
3. Agent DFX 覆盖（韧性 chaos 有雏形）

## 四、文档体系

| 文档 | 说明 |
|------|------|
| DESIGN_OVERVIEW.md | 本文档（总纲） |
| **PRD_REPORT_PORTAL.md** | **v1.1.1 新增：统一报告门户 + 进度埋点 + 报告可视化重构** |
| **DELTA_GENERAL_TO_AGENT.md** | **V1.1 新增：通用测试转 Agent 评测的新增点分析** |
| **PRD_REQUIREMENT_TESTDESIGN.md** | **V1.1 新增：需求分析与测试设计流程（吸收 test-design-agent-raw）** |
| **PRD_CASE_SELF_OPTIMIZATION.md** | **V1.1 重点：用例自优化详细设计** |
| **PRD_MOCK_SYSTEM.md** | **V1.1 新增：mock 系统设计** |
| PRD_ORCHESTRATION.md | 总流程管控 PRD（§6 进度管理已扩展为埋点落盘 + 门户） |
| PRD_TEST_DESIGN.md | 测试设计 PRD（v2.3.0，已被 PRD_REQUIREMENT_TESTDESIGN 取代，保留历史） |
| ADAPTER_SPEC.md | 适配器接口规范 |
| RESEARCH_REPORT.md | 业界调研报告 |

## 五、V1.1 架构

```
agent-eval-v1.1/
├── SKILL.md                         ← 大 skill 入口（V1.1 版本说明）
├── VERSION.md                       ← 版本历史（含 v1.1.0）
├── skills/                          ← 子 skill（含 prompt + Task 指示）
│   ├── orchestrator/SKILL.md        ← 编排（新增阶段 4.5 用例自优化）
│   ├── requirements-analysis/SKILL.md ← 阶段1（吸收 UC 15字段 + testspec 4表）
│   ├── test-case-generator/SKILL.md ← 阶段2（吸收 16自检 + 五层断言）
│   ├── test-executor/SKILL.md       ← 阶段3（原样）
│   ├── test-reporter/SKILL.md       ← 阶段4（原样 + 迭代报告）
│   └── test-case-self-optimization/SKILL.md ← 【V1.1 新增】阶段4.5
├── scripts/                         ← 零 LLM 机械层
│   ├── generate_requirements.py     ← 阶段1 机械层（原样）
│   ├── generate_testcases.py        ← 阶段2 机械层（原样）
│   ├── execute_testcases.py         ← 阶段3a 执行器（原样）
│   ├── excel_to_uatr.py             ← 阶段3b 桥接器（原样）
│   ├── generate_report.py           ← 阶段4a 报告（原样）
│   ├── eval_runner.py               ← 主分支执行器（原样）
│   ├── diagnoser.py                 ← F1-F8 诊断（原样）
│   ├── multi_judge.py / opik_adapter.py / reference_optimizer.py / auto_patcher.py ← 主分支优化（原样）
│   ├── case_io.py                   ← 【V1.1 新增】cases YAML 读写（保留完整 schema）
│   ├── case_quality_checker.py      ← 【V1.1 新增】12 维质量检查
│   ├── case_optimizer.py            ← 【V1.1 新增】用例自优化（错误分布+缺口+建议）
│   ├── mutation_generator.py        ← 【V1.1 新增】变异 + kill matrix
│   └── case_iteration_report.py     ← 【V1.1 新增】迭代报告 MD + HTML
├── agents/                          ← 9 评审 Agent（原样）
├── guides/                          ← 16 篇 + 【V1.1 新增】17 用例自优化指南
├── docs/                            ← V1.1 文档（本目录）
├── examples/.agent-eval/            ← 配置示例（扩展 cases + config）
└── data/                            ← 运行产物
```

## 六、两条数据流 + 用例自优化闭环

### 数据流 A：手机银行 4 阶段流水线（入口）
```
用户需求 → requirements-analysis → test-case-generator → test-executor → excel_to_uatr 桥接 → eval loop
```

### 数据流 B：agent-eval eval loop（主分支原样）
```
UATR trace → diagnoser(F1-F8) → multi_judge(9Judge) → opik_adapter(HRPO) → reference_optimizer → auto_patcher
```

### 【V1.1 新增】用例自优化闭环（数据流 C）
```
diagnosis.json + scores.json + cases YAML
  ↓ case_quality_checker.py → 12 维质量分
  ↓ case_optimizer.py → 错误分布+缺口+建议 JSON
  ↓ mutation_generator.py → kill matrix
  ↓ test-case-self-optimization 子 skill → AskUserQuestion 确认
  ↓ case_io.py --apply → 更新 cases YAML
  ↓ case_iteration_report.py → 迭代报告 MD+HTML
  ↓ 重跑评测 → 质量分提升
```

**三流汇合**：数据流 A 产出 cases，数据流 B 产出 diagnosis，数据流 C 消费 cases+diagnosis 产出优化后的 cases，反哺 A/B。

## 七、核心设计决策（V1.1）

1. **吸收而非重写**：test-design-agent-raw 的 UC 15字段/testspec 4表/16自检 直接吸收，不重造
2. **用例自优化是显式产品概念**：业界空白，V1.1 产品化
3. **脚本零 LLM**：所有 V1.1 新增脚本零 LLM 调用，创造性工作由 Agent 完成
4. **prompt 在子 skill**：test-case-self-optimization 子 skill 含完整 prompt + AskUserQuestion 指示
5. **镜像现有契约**：case_optimizer 的 CLI 镜像 reference_optimizer/mutator（--config --run --apply --dry-run）
6. **优化目标分离**：prompt 自优化（改 Agent）+ 用例自优化（改测试）正交，双闭环
7. **数据格式 YAML + JSONL**：cases YAML（完整 schema）+ diagnosis.json + case_iterations.jsonl
8. **向后兼容**：新增字段（test_level/category/lifecycle/dimension_id/mock_config）旧用例无也能跑

## 八、版本演进路线

| 版本 | 重点 | 状态 |
|------|------|------|
| v2.3.0-mobile-bank | 4阶段流水线 + 桥接 + 脚本零LLM | 已发布（主分支） |
| **v1.1.0（本版本）** | **用例自优化 + 需求分析吸收成熟设计 + mock系统** | **本次开发** |
| v1.2.0（计划） | 测试方法库 YAML + 黑白灰盒完整管理 | 待规划 |
| v2.0.0（计划） | 多 Agent 对比 + 跨 skill 评测 | 待规划 |

> 注：V1.1 是新版本线（聚焦用例自优化），与 v2.x-mobile-bank 并行。两者通过 cases YAML schema 兼容。
