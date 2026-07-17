---
name: test-case-generator
description: "用例生成子 skill（阶段 2，JiuwenSwarm 适配）。根据需求分析 Excel 中的维度和场景，生成详细可执行的测试用例。本子 skill 内含完整 prompt 文字，指示 Agent 用 task 工具并行生成结构化 JSON，再调 generate_testcases.py 写成 Excel。脚本不调任何外部 LLM。"
allowed-tools: bash, read, write, edit, task, question, todo_create, todo_complete, todo_insert, todo_list, todo_remove, send_message, list_members, view_task
---

# 测试用例生成子 skill（阶段 2 / 4，JiuwenSwarm 适配）

> **架构定位**：这是"大 skill 套小 skill 套 script"结构里的**小 skill** 层。
> prompt 拼装在本文件里用文字呈现，由 Agent（你，JiuwenSwarm）自己读、自己想、自己生成 JSON；
> 场景多时**调用 `task` 工具**把生成工作分批并行委派给子 agent（Team 模式下用 `send_message` 派发给名为 `test-case-generator` 的 Teammate，可同时派多批）；
> 最后调 `generate_testcases.py` 这个**机械脚本**把 JSON 写成 Excel。
> 脚本零 LLM 调用，与任何外部模型 URL / API key 完全解耦。

## 你的输入

- `data/requirements_analysis.xlsx`（阶段 1 产出，含测试维度 / 测试场景 / Skill 归属建议）
- `data/uc_blocks.md`（阶段 1 第 1.5 步产出，UC 15 字段块）
- `data/testspec.md`（阶段 1 第 5.5 步产出，4 表中间契约：测试对象/测试操作/测试数据/关系）
- 用户选择的 `per_scenario`（每个场景生成几条用例，默认 3）
- 用户选择的 `dimensions`（全部维度，或指定 DIM-001,DIM-002 子集）

## 你的输出

- `data/test_cases.xlsx`（用例 ID / 场景引用 / 维度 ID / 标题 / 优先级 / 前置条件 / 测试步骤 / 用户输入 / 预期结果 / 断言类型 / 状态）
- `data/cases/<split>.yaml`（canonical cases YAML，含完整五层断言 schema，供 eval loop 消费）
- stdout 输出 JSON 摘要（供下一阶段消费）

## 五层断言 schema（cases YAML canonical schema，吸收 + 扩展自 test-design-agent-raw）

> 通用测试的断言是**单层**的（步骤→预期结果）。Agent 评测需要**五层**断言，每层独立评分、独立归因。设计来源：`docs/DELTA_GENERAL_TO_AGENT.md` § 3.1、`docs/PRD_REQUIREMENT_TESTDESIGN.md` § 4.2。
> 生成用例时必须为每条用例填写这五层（灰盒默认档；黑盒只需第 1 层；白盒追加记忆层）。

```yaml
# cases YAML 一条用例的完整断言结构（五层）
expected:                            # 第 1 层：输出层（最终答案正确性）
  final_decision:
    contains: ["流水波动", "负债", "补充材料"]
    # 或 equals / regex / schema

expected_tools:                      # 第 2 层：行为层（工具调用正确性）
  required: [load_loan_application, analyze_cashflow, check_debt_ratio]
  forbidden: [approve_loan_directly]
  order:
    soft: [load_loan_application, analyze_cashflow, check_debt_ratio]  # 顺序建议

business_rules:                      # 第 3 层：规则层（业务规则合规，可机器验证）
  must_satisfy:
    - id: risk_rule_missing_guarantee
      description: 担保信息缺失时不能直接给出通过结论
      trace_event_contains:          # 检查 trace 事件
        event: tool_result
        field: result.summary
        equals: "mock result of analyze_cashflow"
      # 或 final_answer_contains: ["担保"]
      # 或 final_answer_contains_not: ["\\d{16}"]  # 正则反向断言（合规）

expected_steps: 9                    # 第 4 层：过程层（执行效率断言）
                                    # 超过此步数→F8.1 轮数过多

scoring:                             # 第 5 层：硬失败条件（一票否决）
  hard_fail_if:
    - forbidden_tool_called
    - missing_required_business_rule
    - invalid_json_schema
```

| 层 | 字段 | 作用 | 失败归因 |
|---|------|------|----------|
| 1 | `expected.final_decision` | 验证最终答案正确性 | F7 输出失败 |
| 2 | `expected_tools.required/forbidden/order` | 验证工具调用正确性 | F3 工具选择 + F4 参数 |
| 3 | `business_rules.must_satisfy` | 验证业务规则合规 | F5 workflow + F7.3 漏规则 |
| 4 | `expected_steps` | 验证执行效率（不绕路） | F8 执行冗余 |
| 5 | `scoring.hard_fail_if` | 一票否决条件 | 硬失败不评总分 |

## 第 1 步：读取维度和场景

先列出维度，让用户决定生成范围：

```bash
python ${SKILL_PATH}/scripts/generate_testcases.py --list --input ${SKILL_PATH}/data/requirements_analysis.xlsx
```

用 `question` 工具问用户：
- 每个场景生成几条用例？（默认 3）
- 全部维度还是指定维度？（指定则给 DIM-001,DIM-002 形式）

然后读场景 JSON（这一步把场景喂给 task 子 agent）：

```bash
python ${SKILL_PATH}/scripts/generate_testcases.py --read-scenarios \
  --input ${SKILL_PATH}/data/requirements_analysis.xlsx \
  [--dimensions DIM-001,DIM-002] > /tmp/scenarios.json
```

`/tmp/scenarios.json` 形如 `{"scenarios": [{...}, ...]}`，把它作为生成 prompt 的输入。

## 第 1.5 步：因子提取 + 方法路由（7 方法库，吸收自 test-design-agent-raw）

> 本步从阶段 1 产出的 testspec.md（4 表）和 UC 块中提取测试因子，并为每个因子路由到合适的黑盒测试方法。方法库是**有限词汇表**，避免用例设计发散。设计来源：`docs/PRD_REQUIREMENT_TESTDESIGN.md` § 4.1、`docs/PRD_TEST_DESIGN.md` § 3-4。

### 7 方法库

| 因子类型 | 方法 | 适用场景（Agent 评测举例） | 产出的用例前缀 |
|---------|------|--------------------------|--------------|
| 输入域可划分 | 等价类 | `application_id` 格式、`user_role` 枚举 | FUN_ |
| 边界敏感 | 边界值 | 金额/期限/评分阈值 | FUN_/DFP_ |
| 状态依赖 | 状态迁移 | 申请状态流转（草稿→提交→审核→通过/拒绝） | SCN_ |
| 多因素组合 | 正交 | 工具组合 × 场景 × 角色 | FUN_/SCN_ |
| 条件-动作 | 决策表 | 风险等级判定（多条件→动作） | FUN_ |
| 端到端 | 场景法 | 业务流程（来自 UC 字段 9 主成功场景 + 字段 10 扩展场景） | SCN_ |
| 因果 | 因果图 | 业务规则联动（来自 UC 字段 12 行业特性合规） | DFX_ |

### 因子提取流程

Agent（主上下文）读 `data/testspec.md`，按下面规则提取因子：

1. **从表 1 测试对象提取场景因子**：每个 `TestObject-Scenario-*` → 1 个场景法因子
2. **从表 2 测试操作提取功能/DFX 因子**：每个 `TestOperation-FUN-*` → 1 个等价类或决策表因子；`TestOperation-DFP-*` → 边界值因子；`TestOperation-DFS-*` → 因果图因子
3. **从表 3 测试数据提取边界值/等价类因子**：每行（取值范围）→ 1 个边界值因子（取 min-1/min/max/max+1）+ 1 个等价类因子（合法/非法）
4. **从表 4 关系提取场景因子**：6 应用组合关系 → `SCN_` 场景用例因子；7 实现依赖关系 → `DFR_` 可靠性用例因子

### 方法路由规则

把每个因子的 `factor_type` 字段（从上表第 1 列选）映射到方法（第 2 列）。路由结果以 JSON 形式喂给第 2 步的生成 prompt：

```json
{
  "factors": [
    {"id": "F-001", "source": "TestObject-Scenario-001", "factor_type": "状态依赖", "method": "状态迁移", "case_prefix": "SCN_"},
    {"id": "F-002", "source": "TestOperation-DFP-003", "factor_type": "边界敏感", "method": "边界值", "case_prefix": "DFP_"}
  ]
}
```

> **扩展点**：方法库可外置为 `data/test_method_library.yaml`，让 Agent 读 YAML 配置而非硬编码本节文字。V1.1 阶段先用本节文字内置，后续再外置。

## 第 2 步：用 task 工具委派生成

**场景数 ≤ 10**：一次 `task` 调用生成全部。
**场景数 > 10**：按 10 个一批切分，**并行**发起多个 `task` 调用（在一条消息里放多个 task tool_use 块；Team 模式下用多个 `send_message` 派发给同一 Teammate 或不同 Teammate），最后合并。

调用 `task` 工具，`prompt` 字段填入下面【生成 prompt】整段（把 `{{SCENARIOS_JSON}}` 替换为读到的场景 JSON，`{{PER_SCENARIO}}` 替换为数字）。JiuwenSwarm 的 `task` 工具无需指定 `subagent_type`，由框架按 description 路由：

---

### 【生成 prompt】—— 传给 task 子 agent

```
你是一位智能体（Agent）高级评测工程师，也是一位资深的高级软件测试工程师。

你专注于 Agent 系统的质量保障。你熟练掌握 ReAct、CoT（思维链）等 Agent 交互模式。你设计的用例旨在验证 Agent 在动态环境下的决策准确性、工具调用率以及任务最终达成率，也精通边界值分析法、等价类划分法、状态迁移法及各类黑盒测试技巧。你不仅能设计常规功能用例，还能设计深度的异常、边界和安全用例。

请根据我提供的测试维度和测试场景，设计一套针对 Agent 智能体功能的测试用例。

【测试场景列表】（JSON）：
{{SCENARIOS_JSON}}

【每个场景生成用例数】：{{PER_SCENARIO}}

每个测试用例必须包含：
- tc_id: 用例 ID（TC-NNNN，全局唯一，从 TC-0001 递增）
- scenario_id: 场景引用（SC-XXX，必须是上面列表里存在的 id）
- dimension_id: 维度 ID（从 scenario 反查，若场景 JSON 里有就用，没有则留空）
- title: 标题（简短描述，≤20 字）
- priority: 优先级（高 / 中 / 低）
- preconditions: 前置条件（执行前的系统状态，可空）
- steps: 测试步骤（编号列表，数组，每条一个字符串）
- user_input: 用户输入（直接发给 Agent 的文本，可包含变量占位符 {{var}}）
- expected: 预期结果（可验证的断言描述）
- assertion_type: 断言类型（contains / exact / regex / schema / status_code / tool_called / business_rule）

设计原则：
- 原子性：每个用例验证一个行为
- 确定性：步骤无歧义
- 自包含：数据内联，不依赖外部文件
- 可追溯性：链接回场景 ID
- 覆盖度：每个场景的 N 条用例应覆盖正常路径 / 异常路径 / 边界
- DFX 覆盖：在适当场景下加入性能、安全、韧性用例
- **五层断言**：每条用例按 `expected` / `expected_tools` / `business_rules` / `expected_steps` / `scoring` 五层填写（见上节"五层断言 schema"）
- **因子驱动**：每条用例必须关联第 1.5 步提取的某个 `factor_id`，并标注所用的测试方法
- **UC 追溯**：每条用例的 `expected` 必须能追溯到阶段 1 UC 块的某条字段（7 成功保证 / 9 主成功场景 / 10 扩展场景 / 12 行业特性合规）

请严格按以下 JSON 格式输出（只输出 JSON，不要 markdown 标记，不要解释）：
{
  "test_cases": [
    {
      "scenario_id": "SC-001",
      "tc_id": "TC-0001",
      "dimension_id": "DIM-001",
      "title": "标题",
      "priority": "高",
      "preconditions": "前置条件",
      "steps": ["步骤1", "步骤2"],
      "user_input": "用户输入文本",
      "expected": {"final_decision": {"contains": ["关键词"]}},
      "expected_tools": {"required": [], "forbidden": [], "order": {"soft": []}},
      "business_rules": {"must_satisfy": []},
      "expected_steps": 5,
      "scoring": {"hard_fail_if": []},
      "assertion_type": "contains",
      "factor_id": "F-001",
      "method": "状态迁移",
      "case_prefix": "SCN_",
      "test_level": "gray_box",
      "category": "functional",
      "lifecycle": "active"
    }
  ]
}
```

---

## 第 3 步：合并并校验多个 task 返回

如果有多个并行 `task` 调用，合并所有 `test_cases` 数组，然后：

1. 剥离每个返回里的 markdown 代码块
2. `json.loads` 解析，失败则让该批 task 子 agent 重生成（最多 2 次）
3. **tc_id 全局唯一性校验**：合并后若有重复，按出现顺序重新编号 TC-0001, TC-0002, ...
4. **scenario_id 存在性校验**：每个 tc.scenario_id 必须在第 1 步读到的 scenarios 列表里
5. **必填字段校验**：tc_id / scenario_id / title / user_input / expected 非空

## 第 4 步：调机械脚本写 Excel

把校验通过的合并 JSON 通过 stdin 传给脚本：

```bash
cat <<'EOF' | python ${SKILL_PATH}/scripts/generate_testcases.py --write-stdin \
  --input ${SKILL_PATH}/data/requirements_analysis.xlsx \
  --output ${SKILL_PATH}/data/test_cases.xlsx
{"test_cases": [ ...合并后的全部用例... ]}
EOF
```

脚本 stdout 输出 JSON 摘要（含 test_cases_count / by_priority / by_scenario），展示给用户。

## 第 5 步：用例质量自检（可选，接入 agent-eval 能力）

如果用户开启了质量自检（默认开），用 `task` 工具 spawn 一个 QA 子 agent，按 `docs/PRD_TEST_DESIGN.md` 的 9 维度检查：

| 维度 | 权重 |
|------|------|
| SPEC完整性 | 0.15 |
| 用例完整性 | 0.10 |
| 功能点覆盖度 | 0.15 |
| DFX覆盖度 | 0.15 |
| 有效用例率 | 0.10 |
| 执行可行性 | 0.10 |
| 无二义性 | 0.10 |
| 长度合理 | 0.05 |
| 断言可验证 | 0.10 |

QA 子 agent 输出加权总分和缺陷清单。总分 < 0.7 则回到第 2 步重生成（最多 2 轮迭代）。

## 第 5.5 步：20 项用例自检（16 项成熟 + 4 项 Agent 专属，吸收自 test-design-agent-raw）

> 9 维度加权评分是**软指标**（评总分决定是否重生成）。本步是**硬指标**：把每条自检项转成**确定性 eval 断言**，带 `*` 的关键项不通过则该用例直接不入库（不参与后续执行/评分）。
> 设计来源：`docs/PRD_REQUIREMENT_TESTDESIGN.md` § 4.4、`docs/DELTA_GENERAL_TO_AGENT.md` § 4（16 项成熟表）。

### 16 项成熟自检（来自 test-design-agent-raw testcase-generator/references/self-checklist.md）

| # | 检查项 | 关键 | eval 断言写法 | Agent 适配说明 |
|---|--------|------|---------------|---------------|
| 1 | 无跨用例隐式依赖 | * | `not tc.depends_on_other_tc` | cases 独立性：每条 case 自包含 |
| 2 | 不拆分逻辑连续业务流 | * | `not tc.splits_continuous_workflow` | workflow 用例完整性：跨步流程不切碎 |
| 3 | 步骤↔预期对应 | | `all(step.expected_ref is not None for step in tc.steps)` | 每个步骤都能映射到某个 expected |
| 4 | 无孤儿预期 | * | `not tc.has_orphan_expected` | expected 没有对应步骤 |
| 5 | 步骤不引用不存在的预期 | * | `not tc.has_missing_expected_ref` | 步骤引用的预期编号存在 |
| 6 | 步骤无"验证/检查"动词 | * | `not tc.has_verification_verb_in_steps` | 步骤只描述操作，不写"验证 X"/"检查 Y" |
| 7 | 核心功能点非空 | * | `tc.core_points is not None and len(tc.core_points) > 0` | 关联 testspec 表 2 的 FUN 操作 |
| 8 | 所有核心点被用例覆盖 | * | `all(cp.covered for cp in core_points)` | spec 完整性 |
| 9 | 输出是实例化非概述 | | `not tc.is_summary_level` | 用例数据具体到值，不是"类似情况" |
| 10 | 无语法/逻辑/错别字 | * | `not tc.has_grammar_issue` | 二义性检测 |
| 11 | 行业特性 & 合规覆盖 | * | `tc.has_industry_compliance_case` | business_rules 来自 UC 字段 12 |
| 12 | 云原生场景覆盖 | * | `tc.has_cloud_native_case`（按需） | 多 Agent 版本/容器化 |
| 13 | 数据智能场景覆盖 | * | `tc.has_data_intelligence_case`（按需） | Agent 推理/检索 |
| 14 | SR→用例组一一对应 | * | `sr.case_group_id is not None` | dimension 覆盖：每条 SR 至少 1 条用例 |
| 15 | 性能用例充分（边界+压力+指标） | * | `count(tc.category=='performance') >= 3` | DFP_ 前缀 |
| 16 | 可靠性用例充分（故障注入+切换+恢复） | * | `count(tc.category=='reliability') >= 3` | DFR_ 前缀 |

### 4 项 Agent 评测新增自检（17-20）

| # | 检查项 | 关键 | eval 断言写法 | 说明 |
|---|--------|------|---------------|------|
| 17 | `expected_tools.required` 非空 | * | `len(tc.expected_tools.required) > 0` | 行为层断言必须有；纯输出层用例（黑盒）可豁免 |
| 18 | `business_rules.must_satisfy` 可机器验证 | | `all(rule.has_trace_event_contains or rule.has_final_answer_contains for rule in tc.business_rules.must_satisfy)` | 规则层断言可机器验证 |
| 19 | `expected_steps` 已设置 | | `tc.expected_steps is not None and tc.expected_steps > 0` | 效率断言（灰盒必填） |
| 20 | `scoring.hard_fail_if` 已设置 | | `len(tc.scoring.hard_fail_if) > 0` | 硬失败条件至少 1 条 |

### 自检执行方式

用 `task` 工具 spawn 一个 self-check 子 agent，输入是第 4 步写出的 `test_cases.xlsx` 对应的 JSON，输出是每条用例的 20 项 pass/fail 表 + 关键项（`*`）失败清单：

```json
{
  "self_check_summary": {
    "total_cases": 45,
    "hard_fail_cases": ["TC-0007", "TC-0019"],
    "soft_fail_cases": ["TC-0012"],
    "pass_rate": 0.93,
    "failed_items_by_case": {
      "TC-0007": ["item_6_verification_verb", "item_17_expected_tools_empty"],
      "TC-0019": ["item_11_industry_compliance_missing"]
    }
  }
}
```

- **硬失败用例**（任一 `*` 项不通过）：从 `test_cases.xlsx` 移除，不进入阶段 3 执行；返回第 2 步重生成（最多 2 轮）
- **软失败用例**（仅非 `*` 项不通过）：保留，但在 cases YAML 里打 `quality_flag: soft_fail` 标签，供阶段 4 报告展示

### 自检 prompt 模板（传给 task 子 agent）

```
你是 QA 评测工程师。请对下面【用例集】执行 20 项自检（16 项成熟 + 4 项 Agent 专属）。
带 * 的为关键项，不通过则该用例硬失败（不入库）。

【用例集】（JSON）：
{{TEST_CASES_JSON}}

严格按下面 JSON 输出（不要 markdown 标记）：
{
  "self_check_summary": {
    "total_cases": N,
    "hard_fail_cases": [...],
    "soft_fail_cases": [...],
    "pass_rate": 0.xx,
    "failed_items_by_case": {"TC-xxxx": ["item_N_xxx", ...]}
  }
}

20 项检查项的 item key：
item_1_no_cross_case_deps, item_2_no_split_continuous_flow, item_3_step_expected_correspondence,
item_4_no_orphan_expected, item_5_no_step_refs_nonexistent_expected, item_6_no_verification_verbs_in_steps,
item_7_core_points_non_empty, item_8_all_core_points_covered, item_9_instantiated_not_summarized,
item_10_no_grammar_issues, item_11_industry_compliance_covered, item_12_cloud_native_covered,
item_13_data_intelligence_covered, item_14_sr_case_group_one_to_one, item_15_performance_cases_sufficient,
item_16_reliability_cases_sufficient, item_17_expected_tools_required_non_empty,
item_18_business_rules_machine_verifiable, item_19_expected_steps_set, item_20_scoring_hard_fail_if_set
```

## 与下一阶段的衔接

本阶段产出 `test_cases.xlsx`，是阶段 3（执行）的输入。每个用例的 `user_input` 会被 `execute_testcases.py` 替换到 HTTP body 模板的 `{{用户输入}}` 占位符里。

## 重要约束

- ❌ 本子 skill 不许调任何外部 LLM API
- ❌ 不许在脚本里拼 prompt
- ✅ prompt 在本文件里以文字呈现
- ✅ 生成工作由 Agent 自己做，或用 `task` 工具并行委派（Team 模式下用 `send_message`）
- ✅ 脚本只做 JSON → Excel 的机械写入 + list + read-scenarios
- ✅ 场景多时必须分批并行（一条消息多个 task tool_use；Team 模式下多个 send_message），避免主上下文爆炸
- ✅ 每条用例必须填五层断言（expected/expected_tools/business_rules/expected_steps/scoring），灰盒默认档
- ✅ 第 1.5 步因子提取的 `factor_id` 必须在每条用例中保留（`tc.factor_id` 字段），用于追溯 testspec 表
- ✅ 第 5.5 步 20 项自检的 `*` 关键项不通过的用例直接淘汰，不进入阶段 3 执行
- ✅ 方法库（7 方法）V1.1 阶段内置在本文件，后续可外置为 `data/test_method_library.yaml`
