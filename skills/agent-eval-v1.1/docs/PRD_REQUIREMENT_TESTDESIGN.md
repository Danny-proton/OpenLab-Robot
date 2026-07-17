# PRD — 需求分析与测试设计流程（V1.1）

> 本文档定义 V1.1 的需求分析和测试用例设计流程，吸收 `test-design-agent-raw` 成熟技能的设计，
> 扩展 Agent 评测专属能力。是 `skills/requirements-analysis/SKILL.md` 和 `skills/test-case-generator/SKILL.md` 的设计依据。

## 1. 设计目标

把通用测试设计的成熟方法论（UC 分析、测试对象建模、测试操作建模、关系建模、16 项自检）
**迁移到 Agent 评测场景**，补齐主分支 agent-eval 在 L1 测试设计层的短板（原进度 20%）。

## 2. 流程总览（6 阶段，对应子 skill）

```
用户需求文本 / PRD / SPEC
  ↓
阶段1: requirements-analysis 子 skill
  ├─ 1a. 需求分解 → UC 15 字段块（吸收 test-design-agent-raw）
  ├─ 1b. 测试维度提取（6 覆盖框架：业务场景/流程/角色意图/规则约束/输入上下文/安全边界）
  ├─ 1c. 测试场景生成（每维度 1-N 场景）
  ├─ 1d. testspec 4 表（测试对象/操作/数据/关系）— 吸收成熟设计
  └─ 1e. Skill 归属建议（哪些维度需要哪些 Agent skill）
  ↓
requirements_analysis.xlsx（3 sheet：测试维度/测试场景/Skill归属建议）+ testspec.md（4 表）
  ↓
阶段2: test-case-generator 子 skill
  ├─ 2a. 因子提取（等价类/边界值/状态迁移/正交/决策表/场景法/因果图 7 方法）
  ├─ 2b. 方法路由（根据因子类型选方法）
  ├─ 2c. 用例生成（Agent 用 Task 工具并行，五层断言 schema）
  ├─ 2d. 格式化检查（id 唯一/字段完整/前缀分类 FUN_/SCN_/DFX_）
  ├─ 2e. 16 项自检（吸收成熟设计，带 * 关键项硬失败）
  └─ 2f. 12 维质量评分（调 case_quality_checker.py）
  ↓
test_cases.xlsx（11 列）+ cases/<split>.yaml（完整 canonical schema）
  ↓
阶段3: test-executor 子 skill（执行 + 桥接，原样保留）
阶段4.5: test-case-self-optimization 子 skill（V1.1 新增，见 PRD_CASE_SELF_OPTIMIZATION）
阶段4: test-reporter 子 skill（原样保留）
```

## 3. 阶段1：需求分析（requirements-analysis 子 skill）

### 3.1 输入

| 输入 | 格式 | 必填 |
|------|------|------|
| Agent PRD | 文本 | 是 |
| Agent SPEC | 文本（工具列表/参数 schema/Advisor 链/业务规则） | 是 |
| 代码扫描记忆 | JSON（工具列表/参数/Advisor 链） | 否 |
| 历史 case | YAML | 否（迭代时） |
| 历史错误 | JSON（上轮 F1-F8 分布） | 否（迭代时） |

### 3.2 UC 15 字段块（吸收 test-design-agent-raw）

每个需求分解成一个 UC（Use Case）块，15 个固定字段：

| # | 字段 | 说明 | Agent 评测扩展 |
|---|------|------|--------------|
| 1 | 用例编号 | UC-<场景>-NNNNN | |
| 2 | 用例名称 | | |
| 3 | 用例描述 | | |
| 4 | 角色 (Actor) | 谁触发 | Agent 的 user 角色 |
| 5 | 前置条件 | env/config/network/data/第三方 | Agent 的 input.application_id 等 |
| 6 | 最小保证 | 系统兜底（目标未达也不丢数据） | |
| 7 | 成功保证 | 目标达成时系统输出 | expected.final_decision |
| 8 | 触发事件 | | input.user_message |
| 9 | 主成功场景 | 编号的可观察动作序列 | expected_tools.order.soft |
| 10 | 扩展场景 | E1/E2 分支 | 异常/边界用例来源 |
| 11 | DFX 属性 | 可维护/性能/可靠/安全/兼容 | DFX 用例来源 |
| 12 | 行业特性 & 合规 | PCI-DSS/等保/HIPAA | business_rules 来源 |
| 13 | 数据字典 | | input.attachments |
| 14 | 是否架构需求 | | |
| 15 | 是否影响架构 | | |

**Agent 评测扩展**：UC 字段 7/9/10/12 直接映射到 cases YAML 的 expected/expected_tools/business_rules。

### 3.3 测试维度提取（6 覆盖框架）

从 UC 提取 6 个覆盖维度：

| 维度 | 说明 | 示例（手机银行） |
|------|------|---------------|
| 业务场景 | Agent 处理的业务场景 | 风险审查/贷后管理/补充材料 |
| 流程 | 端到端流程 | 初审→复审→终审 |
| 角色意图 | 用户意图分类 | 查询/申请/投诉/取消 |
| 规则约束 | 业务规则 | 流水波动>30%必须提示风险 |
| 输入上下文 | 输入边界 | 单轮/多轮/带附件/空输入 |
| 安全边界 | 合规/越权 | 禁止明文卡号/禁止直接放款 |

输出 JSON：
```json
{
  "dimensions": [
    {"id": "DIM-001", "name": "业务场景", "type": "business_scenario"},
    {"id": "DIM-002", "name": "异常恢复", "type": "workflow"}
  ],
  "scenarios": [
    {"id": "SC-001", "dimension_id": "DIM-001", "name": "企业贷款风险审查", "description": "..."}
  ],
  "skill_suggestions": [
    {"dimension_id": "DIM-001", "skill": "loan-risk-agent", "reason": "..."}
  ]
}
```

### 3.4 testspec 4 表（吸收成熟设计，作为中间契约）

在需求分析阶段产出 testspec.md，作为需求→用例的中间契约：

#### 表1：测试对象（5 分类）
| 分类 | 命名 | ID | Agent 扩展 |
|------|------|----|-----------|
| 业务场景类 | "xx 业务场景" | TestObject-Scenario-NNN | → dimension |
| 平台能力类 | "xx 能力" | TestObject-Capability-NNN | → Agent 工具能力 |
| 数据智能类 | "xx 数据分析" | TestObject-DataIntel-NNN | → Agent 推理能力 |
| 安全合规类 | | TestObject-Security-NNN | → business_rules |
| 架构支撑类 | | TestObject-Architecture-NNN | → workflow/advisor |

#### 表2：测试操作（7 DFX 类型，动宾结构）
| DFX | 前缀 | Agent 扩展 |
|-----|------|-----------|
| 功能 FUN | TestOperation-FUN-NNN | → expected_tools |
| 可靠性 DFR | TestOperation-DFR-NNN | → fallback 场景 |
| 性能 DFP | TestOperation-DFP-NNN | → expected_steps |
| 安全 DFS | TestOperation-DFS-NNN | → forbidden tools |
| 兼容性 DFC | TestOperation-DFC-NNN | → 多 Agent 版本 |
| 数据智能 DFAI | TestOperation-DFAI-NNN | → 推理断言 |
| 业务交互 DFINT | TestOperation-DFINT-NNN | → 跨系统场景 |

#### 表3：测试数据
| 测试对象 | 参数 | 取值范围 | 默认值 | 单位 | 描述 |
（边界值/等价类的数据来源）

#### 表4：关系（13 类型）
6 应用组合关系（先后依赖/前者影响后者/同时发生/共享/约束/互斥）+ 7 实现依赖关系（无同步/乱序/超时/消息交互/共享数据缺陷/独占资源/死锁）。
→ 关系表是场景用例（SCN_）的生成依据。

### 3.5 输出

`requirements_analysis.xlsx`（3 sheet）+ `testspec.md`（4 表）+ JSON（供下游）。

## 4. 阶段2：测试用例生成（test-case-generator 子 skill）

### 4.1 因子提取 + 方法路由（7 方法库）

| 因子类型 | 方法 | 适用场景 |
|---------|------|---------|
| 输入域可划分 | 等价类 | application_id 格式 |
| 边界敏感 | 边界值 | 金额/期限/评分 |
| 状态依赖 | 状态迁移 | 申请状态流转 |
| 多因素组合 | 正交 | 工具组合×场景 |
| 条件-动作 | 决策表 | 风险等级判定 |
| 端到端 | 场景法 | 业务流程 |
| 因果 | 因果图 | 业务规则联动 |

方法库 = YAML 配置（`data/test_method_library.yaml`，扩展点）。Agent 读方法库，根据因子类型路由。

### 4.2 用例生成（五层断言 schema）

每条用例输出 JSON：
```json
{
  "test_cases": [
    {
      "scenario_id": "SC-001",
      "tc_id": "loan_risk_004",
      "dimension_id": "DIM-001",
      "title": "风险审查-工具选择边界-相似工具区分",
      "priority": "P1",
      "preconditions": ["Agent 已加载贷款申请"],
      "steps": ["1. 用户提交申请", "2. Agent 调用工具分析"],
      "user_input": "请帮我分析这个企业贷款申请是否有风险",
      "expected": {"final_decision": {"contains": ["流水波动", "负债", "补充材料"]}},
      "assertion_type": "contains",
      "test_level": "gray_box",
      "category": "functional",
      "lifecycle": "active"
    }
  ]
}
```

并行生成：≤10 场景单 Task，>10 拆批每批 10。

### 4.3 格式化检查（确定性）

- id 唯一（无重复 tc_id）
- 字段完整（id/input/expected/expected_tools/...）
- 前缀分类（FUN_/SCN_/DFX_ 或 category 字段）
- 步骤↔预期对应（`见预期结果 n` 全部可解析）

### 4.4 16 项自检（吸收成熟设计）

带 `*` 为关键项（不通过则用例不入库）：

| # | 检查 | 关键 | Agent 适配 |
|---|------|------|-----------|
| 1 | 无跨用例隐式依赖 | * | cases 独立性 |
| 2 | 不拆分逻辑连续业务流 | * | workflow 用例完整性 |
| 3 | 步骤↔预期对应 | | |
| 4 | 无孤儿预期 | * | |
| 5 | 步骤不引用不存在预期 | * | |
| 6 | 步骤无"验证/检查"动词 | * | 步骤只描述操作 |
| 7 | 核心功能点非空 | * | |
| 8 | 所有核心点被用例覆盖 | * | spec 完整性 |
| 9 | 输出是实例化非概述 | | |
| 10 | 无语法/逻辑/错别字 | * | 二义性检测 |
| 11 | 行业特性 & 合规覆盖 | * | business_rules |
| 12 | 云原生场景覆盖 | * | （按需） |
| 13 | 数据智能场景覆盖 | * | （按需） |
| 14 | SR→用例组一一对应 | * | dimension 覆盖 |
| 15 | 性能用例充分（边界+压力+指标） | * | DFP |
| 16 | 可靠性用例充分（故障注入+切换+恢复） | * | DFR |

**Agent 评测新增自检项**（17-20）：
| 17 | expected_tools.required 非空 | * | 行为层断言 |
| 18 | business_rules.must_satisfy 可机器验证 | | 规则层断言 |
| 19 | expected_steps 已设置 | | 效率断言 |
| 20 | scoring.hard_fail_if 已设置 | | 硬失败条件 |

### 4.5 12 维质量评分

调 `case_quality_checker.py`，<0.75 触发重新生成（test-case-generator 子 skill 第 6 步）。

## 5. 与 test-design-agent-raw 的差异

| 维度 | test-design-agent-raw | agent-eval V1.1 |
|------|----------------------|-----------------|
| 被测对象 | 确定性系统 | 概率性 Agent |
| 断言 | 单层（步骤→预期） | 五层（输出/工具/规则/效率/硬失败） |
| 失败归因 | pass/fail | F1-F8 16 子类 |
| 用例自优化 | 无 | 8 步闭环（本 PRD 的姊妹文档） |
| Trace | 无 | UATR 0.5 |
| 中间契约 | testspec.md（4 表） | testspec.md + cases YAML（五层断言） |
| 覆盖率 | 功能+DFX | 功能+DFX+工具+工作流+记忆 |
| 输出格式 | Excel（6 列） | Excel（11 列）+ YAML（完整 schema） |

## 6. 验收标准

- [x] requirements-analysis 子 skill 产出 UC 15 字段 + 6 维度 + testspec 4 表
- [x] test-case-generator 子 skill 产出五层断言用例 + 16+4 项自检
- [x] 用例可被 case_quality_checker.py 评分
- [x] 用例可被 execute_testcases.py 执行
- [x] 用例可被 excel_to_uatr.py 桥接到 eval loop
