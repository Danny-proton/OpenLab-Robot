# 通用测试设计 → Agent 评测：新增点分析

> 本文档回答一个问题：把成熟的通用测试设计技能（`test-design-agent-raw`）
> 改造成 **Agent 评测** 需要新增什么？
>
> 对照对象：
> - 成熟技能：`skills/test-design-agent-raw/`（6 阶段流水线：xlsx→md → requirement-parser → testspec-generator → testspec-check → testcase-generator → testcase-to-xlsx）
> - Agent 评测：`skills/agent-eval/`（4 阶段流水线 + eval loop + F1-F8 + 用例自优化）

## 1. 根本差异：被测对象从「确定性系统」变成「概率性 Agent」

通用测试设计的被测对象是**确定性软件系统**：给定输入 → 确定输出，断言是"等价类/边界值"驱动的函数级或接口级验证。

Agent 评测的被测对象是**概率性智能体**：给定输入 → 输出路径不唯一，断言要覆盖：
- **最终答案正确性**（输出层）
- **工具调用正确性**（行为层：该调的调了没？不该调的调了没？顺序对不对？参数对不对？）
- **业务规则合规**（规则层：硬约束是否满足）
- **执行效率**（过程层：是否绕路、是否冗余思考、轮数是否合理）
- **工作流质量**（编排层：前置检查、异常恢复、记忆使用）

这一根本差异决定了下表的所有新增点。

## 2. 新增点总览

| # | 新增维度 | 通用测试设计 | Agent 评测需要新增 | 实现位置 |
|---|---------|------------|------------------|---------|
| 1 | **断言体系** | 步骤↔预期结果一一对应（`见预期结果 n`） | 多层断言：final_answer / expected_tools / business_rules / expected_steps / scoring.hard_fail_if | cases YAML schema |
| 2 | **失败归因** | 用例 pass/fail 二态 | F1-F8 八类失败 + 16 子类（F8.1-F8.4 执行冗余） | diagnoser.py |
| 3 | **Trace 契约** | 无（只看输入输出） | UATR 0.5 trace 事件 schema（agent/model/tool/memory/skill/planner 6 类 24 事件） | common.py |
| 4 | **执行效率断言** | 无 | expected_steps + F8 冗余检测（轮数过多/重复规划/无效中间步/探索式徘徊） | diagnoser.py |
| 5 | **工具调用断言** | 无 | expected_tools.required / forbidden / order.soft | cases YAML |
| 6 | **业务规则断言** | 隐含在预期结果文字里 | business_rules.must_satisfy[].trace_event_contains / final_answer_contains（可机器验证） | cases YAML + scorer.py |
| 7 | **硬失败条件** | 无 | scoring.hard_fail_if（forbidden_tool_called / missing_required_business_rule / invalid_json_schema） | scorer.py |
| 8 | **覆盖率维度** | 功能点 / DFX 7 维 | 功能点 + DFX 7 维 + **Agent 专属 3 维**：工具覆盖 / 工作流覆盖 / 记忆覆盖 | case_quality_checker.py |
| 9 | **用例自优化** | 无（用例一次性生成） | 错误分布分析 → spec 缺口 → 质量检查 → mutation kill matrix → 增强/修改/废弃建议 | case_optimizer.py + mutation_generator.py |
| 10 | **Mutation 测试** | 无 | 注入变异 Agent 行为（漏调工具/参数错/返回空/超时），看用例能否检出 | mutation_generator.py |
| 11 | **优化目标分离** | 只优化被测系统 | **两类优化**：①优化被测 Agent（prompt/tool/workflow/reference）②优化测试本身（case/spec/因子） | reference_optimizer.py + case_optimizer.py |
| 12 | **黑/白/灰三档** | 无 | test_level: black_box / gray_box / white_box（灰盒可见 trace，白盒可见 prompt/memory） | cases YAML + PRD_ORCHESTRATION |
| 13 | **多 Judge 评审** | 无 | 9 个评审 Agent（6 规则型 + 3 决策型），含 SafetyJudge 一票否决 | agents/*.md + multi_judge.py |
| 14 | **HRPO 根因** | 无 | 层次化根因分析（现象→直接因→根因→reference 注入点） | opik_adapter.py |
| 15 | **Reference 注入** | 无 | 把"最优执行路径"固化成 reference 文件，按需加载（比改 prompt 稳） | reference_optimizer.py |
| 16 | **A/B 自动化** | 无 | baseline vs candidate，Gatekeeper 决策，自动 git commit/rollback | auto_patcher.py |
| 17 | **迭代度量** | 用例数 / 通过率 | 用例数 + 覆盖率 + 质量分（9维加权）+ mutation 检出率 + 迭代前后质量分变化 | case_iteration_report.py |
| 18 | **行业合规断言** | DFX 属性文字描述 | 可机器验证的合规规则（PCI-DSS/等保/HIPAA 关键词或 trace 事件） | cases YAML business_rules |
| 19 | **Skill 触发断言** | 无 | expect_skill_trigger.prompt_hash（验证 skill 是否被正确触发） | cases YAML + diagnoser F1 |
| 20 | **记忆使用断言** | 无 | expect_memory_use + memory_retrieval 事件检查（F6） | cases YAML + diagnoser F6 |

## 3. 详细新增点说明

### 3.1 多层断言体系（最重要）

通用测试的断言是**单层**的：步骤→预期结果。Agent 评测需要**五层**断言：

```yaml
# Agent 评测用例的完整断言结构（cases YAML）
expected:
  final_decision:                    # 第1层：输出层
    contains: ["流水波动", "负债", "补充材料"]
    # 或 equals / regex / schema

expected_tools:                      # 第2层：行为层
  required: [load_loan_application, analyze_cashflow, check_debt_ratio]
  forbidden: [approve_loan_directly]
  order:
    soft: [load_loan_application, analyze_cashflow, check_debt_ratio]  # 顺序建议

business_rules:                      # 第3层：规则层
  must_satisfy:
    - id: risk_rule_missing_guarantee
      description: 担保信息缺失时不能直接给出通过结论
      trace_event_contains:          # 可机器验证：检查 trace 事件
        event: tool_result
        field: result.summary
        equals: "mock result of analyze_cashflow"
      # 或 final_answer_contains: ["担保"]

expected_steps: 9                    # 第4层：过程层（效率断言）

scoring:                             # 第5层：硬失败条件
  hard_fail_if:
    - forbidden_tool_called
    - missing_required_business_rule
    - invalid_json_schema
```

通用测试设计没有这五层，因为确定性系统的"步骤→预期"已经足够。Agent 的不确定性要求把断言拆到不同层，每层独立评分、独立归因。

### 3.2 失败归因 taxonomy（F1-F8）

通用测试只有 pass/fail。Agent 评测需要把每个 fail 归因到具体类别，才能定位修改对象：

| 代码 | 名称 | 修改对象 | 子类 |
|------|------|---------|------|
| F1 | Skill 触发失败 | SKILL.md description | F1.1 没触发 |
| F2 | 任务理解失败 | prompt | F2.1 没识别任务类型 |
| F3 | 工具选择失败 | tool schema + policy | F3.1 漏工具 / F3.3 重复调用 |
| F4 | 工具参数失败 | tool schema + memory | F4.4 ID或对象错误 |
| F5 | Workflow 失败 | advisor 链 | F5.1 缺前置 / F5.3 缺fallback |
| F6 | Memory 失败 | memory + prompt | F6.1 没检索到/结果为空 |
| F7 | 输出失败 | prompt + memory | F7.1 格式 / F7.3 漏规则 / F7.4 幻觉 |
| **F8** | **执行冗余失败** | **reference** | F8.1 轮数过多 / F8.2 重复规划 / F8.3 无效中间步 / F8.4 探索式徘徊 |

**F8 是 Agent 评测独有的**：即使最终答案正确，如果绕路了也算失败（效率 ≠ 正确性）。通用测试没有这个概念。

### 3.3 用例自优化（业界空白，本次重点）

通用测试设计是**一次性生成**：生成完就完了。Agent 评测需要**迭代优化测试本身**：

```
完成一轮评测
  ↓
错误分布分析（F1-F8 哪类集中？）
  ↓
spec 缺口识别（哪个维度 0 用例？哪个 100% 通过可能太简单？）
  ↓
用例质量检查（9 维度加权评分）
  ↓
mutation kill matrix（注入变异，看用例能否检出）
  ↓
生成增强建议（新增/修改/废弃/改spec）
  ↓
与人确认 → 更新 cases YAML → 重跑评测 → 度量提升
```

这与 prompt 自优化的区别：
- prompt 自优化改的是**被测 Agent**（prompt/tool/workflow）
- 用例自优化改的是**测试本身**（case/spec/因子）

业界只有 prompt 自优化（HRPO/GEPA），没有 test-case 自优化产品化。这是 V1.1 的核心创新。

### 3.4 Agent 专属覆盖率维度

通用测试的覆盖率是：功能点 + DFX 7 维（性能/兼容/可靠/安全/韧性/可服务/可维护）。

Agent 评测需要新增 3 个专属维度：
- **工具覆盖率**：被测 Agent 的工具列表，每条 expected_tools.required 是否都有用例覆盖
- **工作流覆盖率**：advisor 链 / 前置检查 / 异常恢复 / fallback 场景是否都有用例
- **记忆覆盖率**：expect_memory_use 场景是否覆盖（多轮上下文 / 检索触发 / 空结果处理）

### 3.5 黑/白/灰三档用例管理

通用测试不区分。Agent 评测需要三档：
- **黑盒**：只给输入和预期输出，不看 trace（测最终效果）
- **灰盒**：可见 trace，断言工具调用/业务规则/步数（测行为过程）—— 本 skill 默认档
- **白盒**：可见 prompt/memory，断言 skill 触发/记忆使用（测内部机制）

```yaml
test_level: gray_box  # black_box | gray_box | white_box
```

### 3.6 可机器验证的合规断言

通用测试的合规是 DFX 属性的文字描述（"符合 PCI-DSS"）。Agent 评测需要可机器验证：

```yaml
business_rules:
  must_satisfy:
    - id: pci_dss_no_card_storage
      description: 不得在最终答案中明文存储卡号
      final_answer_contains_not: ["\\d{16}"]  # 正则反向断言
```

## 4. 保留复用的成熟设计

test-design-agent-raw 有很多设计**直接可复用**，不需要重造：

| 成熟设计 | 复用方式 |
|---------|---------|
| UC 15 字段块（用例编号/名称/描述/角色/前置/最小保证/成功保证/触发/主成功场景/扩展场景/DFX/合规/数据字典/架构需求） | 作为需求分析子 skill 的结构化输入格式 |
| 测试对象建模 5 分类（业务场景/平台能力/数据智能/安全合规/架构支撑） | 作为维度提取的分类框架 |
| 测试操作建模 7 DFX 类型（FUN/DFR/DFP/DFS/DFC/DFAI/DFINT） | 作为用例类型前缀 + DFX 覆盖率维度 |
| 关系建模 13 类型（6 应用组合 + 7 实现依赖） | 作为场景用例（SCN_）的生成依据 |
| testspec 4 表（对象/操作/数据/关系） | 作为需求分析与用例生成之间的中间契约 |
| 16 项自检表（带 `*` 关键项） | 转成 case_quality_checker 的确定性检查规则 |
| `见预期结果 n` 步骤↔预期对应 | 作为用例格式化检查的机械验证规则 |
| 前缀分类（FUN_/SCN_/DFX_） | 作为用例分类标签 + 覆盖率统计维度 |
| reference 模板驱动（先读框架再填内容） | 作为子 skill prompt 的组织方式 |

## 5. 改造策略：吸收 + 扩展，不重写

V1.1 的改造策略是**吸收 test-design-agent-raw 的成熟设计 + 扩展 Agent 专属能力**：

```
test-design-agent-raw 的成熟设计（吸收）
  ├─ UC 15 字段 → requirements-analysis 子 skill 输入格式
  ├─ testspec 4 表 → 需求分析→用例生成的中间契约
  ├─ 16 项自检 → case_quality_checker 确定性规则
  ├─ 测试对象/操作/关系建模 → 维度+场景+用例分类
  └─ reference 模板驱动 → 子 skill prompt 组织

agent-eval 的 Agent 专属能力（扩展）
  ├─ 五层断言 → cases YAML schema
  ├─ F1-F8 归因 → diagnoser.py
  ├─ UATR trace → common.py
  ├─ 用例自优化 → case_optimizer.py + mutation_generator.py（V1.1 新增）
  ├─ 9 Judge → multi_judge.py
  ├─ HRPO + reference → opik_adapter.py + reference_optimizer.py
  └─ A/B + Gatekeeper → auto_patcher.py
```

## 6. 验收标准

V1.1 完成后应满足：
- [x] cases YAML 支持完整五层断言 schema
- [x] diagnoser 能归因 F1-F8 全部 16 子类
- [x] case_quality_checker 实现 9 维度 + Agent 专属 3 维确定性检查
- [x] case_optimizer 能从 diagnosis 生成 add/modify/deprecate/spec_changes 建议
- [x] mutation_generator 能注入变异并生成 kill matrix
- [x] 用例自优化闭环可跑通：诊断→分析→建议→确认→更新→重跑→度量
- [x] 迭代报告 MD + HTML 输出质量分变化/覆盖率变化/mutation 检出率
- [x] mock 系统支持触发 F3/F7/F8 各类失败供测试
- [x] 端到端测试在 mock 上跑通无错误
