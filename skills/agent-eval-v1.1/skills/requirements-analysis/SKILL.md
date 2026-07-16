---
name: requirements-analysis
description: "需求分析子 skill（阶段 1）。把需求文本拆成测试维度和场景。本子 skill 内含完整 prompt 文字，指示 Agent 用 Task 工具生成结构化 JSON，再调 generate_requirements.py 写成 Excel。脚本不调任何外部 LLM。"
allowed-tools: Bash(python *), Bash(python3 *), Read, Write, Edit, Task, AskUserQuestion
---

# 需求分析子 skill（阶段 1 / 4）

> **架构定位**：这是"大 skill 套小 skill 套 script"结构里的**小 skill** 层。
> prompt 拼装和用例生成在本文件里用文字呈现，由 Agent（你，Claude）自己读、自己想、自己生成 JSON；
> 然后**调用 Task 工具**把生成工作委派给一个隔离子 agent（避免主上下文被大量 case 污染）；
> 最后调 `generate_requirements.py` 这个**机械脚本**把 JSON 写成 Excel。
> 脚本零 LLM 调用，与任何外部模型 URL / API key 完全解耦。

## 你的输入

- `description`：用户提供的 Agent 需求说明文本（可能是 PRD 摘要、产品描述、功能清单）
- 若用户给的是已有测试用例文件，走"逆向分析"模式（见下文）

## 你的输出

- `data/requirements_analysis.xlsx`（3 个 sheet：测试维度 / 测试场景 / Skill 归属建议）
- `data/uc_blocks.md`（UC 15 字段块，每个 UC 一个块）— 结构化需求分解，吸收自 test-design-agent-raw（见 `docs/PRD_REQUIREMENT_TESTDESIGN.md` § 3.2）
- `data/testspec.md`（4 个 markdown 表：测试对象 / 测试操作 / 测试数据 / 关系）— 需求→用例的中间契约，吸收自 test-design-agent-raw（见 `docs/PRD_REQUIREMENT_TESTDESIGN.md` § 3.4）
- stdout 输出 JSON 摘要（供下一阶段消费）

> 三类输出之间的关系：UC 块（第 1.5 步）→ 6 维度+场景（第 2 步）→ testspec 4 表（第 5.5 步）。UC 是结构化输入，维度/场景是覆盖分解，testspec 是给用例生成提供有限词汇表的中间契约。

## 第 1 步：确认需求文本

如果用户没给 `description`，用 `AskUserQuestion` 问：

> 请提供被测 Agent 的需求说明（PRD 摘要 / 功能描述 / 业务场景清单），用于生成测试维度和场景。

如果用户给的是已有测试用例（JSON/YAML/Excel），走逆向分析（见第 4 步）。

## 第 1.5 步：UC 15 字段块（吸收 test-design-agent-raw，作为结构化输入）

> 本步把非结构化的需求文本（PRD/SPEC/功能清单）拆成结构化的 UC（Use Case）块，作为后续 6 维度提取（第 2 步）和 testspec 4 表生成（第 5.5 步）的**结构化输入**。
> 设计来源：`docs/PRD_REQUIREMENT_TESTDESIGN.md` § 3.2、`docs/DELTA_GENERAL_TO_AGENT.md` § 4。

每个需求功能点分解成一个 UC 块，固定 15 个字段：

| # | 字段 | 说明 | Agent 评测映射 |
|---|------|------|---------------|
| 1 | 用例编号 | `UC-<场景>-NNNNN` | 关联 tc_id 前缀 |
| 2 | 用例名称 | 简短描述 | |
| 3 | 用例描述 | 业务目标说明 | |
| 4 | 角色 (Actor) | 谁触发该 UC | Agent 的 user 角色 |
| 5 | 前置条件 | env/config/network/data/第三方依赖 | `input.application_id` 等 |
| 6 | 最小保证 | 系统兜底（目标未达也不丢数据/不误操作） | |
| 7 | 成功保证 | 目标达成时系统输出 | `expected.final_decision` |
| 8 | 触发事件 | UC 入口信号 | `input.user_message` |
| 9 | 主成功场景 | 编号的可观察动作序列 | `expected_tools.order.soft` |
| 10 | 扩展场景 | E1/E2 分支（异常/替代路径） | 异常/边界用例来源 |
| 11 | DFX 属性 | 可维护/性能/可靠/安全/兼容 | DFX 用例来源 |
| 12 | 行业特性 & 合规 | PCI-DSS/等保/HIPAA/适当性管理 | `business_rules` 来源 |
| 13 | 数据字典 | 输入数据结构 | `input.attachments` |
| 14 | 是否架构需求 | 是/否 | |
| 15 | 是否影响架构 | 是/否 | |

**UC 字段 → cases YAML 映射规则**（第 2 阶段用例生成时遵循）：

| UC 字段 | cases YAML 路径 | 转换说明 |
|---------|----------------|----------|
| 7 成功保证 | `expected.final_decision.contains` | 把"成功保证"拆成可机器验证的关键词/正则/枚举数组 |
| 9 主成功场景 | `expected_tools.order.soft` | 主场景里的编号动作序列 → 工具调用顺序数组 |
| 10 扩展场景 | 独立 tc 的 expected | 每个 E1/E2 分支 → 1 条独立用例，expected 用扩展场景描述 |
| 12 行业特性合规 | `business_rules.must_satisfy[]` | 合规条款 → `trace_event_contains` / `final_answer_contains` 规则 |

### 【生成 prompt】（UC 15 字段块）—— 传给 Task 子 agent

```
你是一位资深智能体系统需求分析师。请把下面的【Agent 需求说明】拆成 UC（Use Case）块。每个功能点一个 UC 块，固定 15 个字段，用 markdown 表格输出。

【Agent 需求说明】：
{{DESCRIPTION}}

请严格按以下 markdown 格式输出（每个 UC 块之间用 --- 分隔，不要解释）：

### UC-<场景>-00001

| # | 字段 | 内容 |
|---|------|------|
| 1 | 用例编号 | UC-xxx-00001 |
| 2 | 用例名称 | ... |
| 3 | 用例描述 | ... |
| 4 | 角色 | ... |
| 5 | 前置条件 | ... |
| 6 | 最小保证 | ... |
| 7 | 成功保证 | ... |
| 8 | 触发事件 | ... |
| 9 | 主成功场景 | 1. xxx 2. xxx 3. xxx |
| 10 | 扩展场景 | E1: xxx / E2: xxx |
| 11 | DFX 属性 | 性能/可靠/安全/... |
| 12 | 行业特性合规 | PCI-DSS/等保/... |
| 13 | 数据字典 | ... |
| 14 | 是否架构需求 | 是/否 |
| 15 | 是否影响架构 | 是/否 |

字段填写要求：
- 字段 9（主成功场景）必须是编号的可观察动作序列，便于后续映射到 expected_tools.order.soft
- 字段 10（扩展场景）每个 E1/E2 分支用一句话描述异常或替代路径
- 字段 12（行业特性合规）尽量给出可机器验证的关键词或条款编号（如 PCI-DSS 3.4 / 等保三级 8.1.4）
- 字段 14/15 默认"否"，仅当需求明确涉及架构调整时填"是"
```

子 agent 返回的 markdown 保存到 `${SKILL_PATH}/data/uc_blocks.md`。这份 UC 块在第 2 步作为生成维度的**附加上下文**（在原 prompt 的【Agent 需求说明】后追加一节【UC 块】），让维度提取有结构化依据而不是凭空发散。

## 第 2 步：用 Task 工具委派生成（正向分析）

**不要自己一次性生成全部内容**，而是用 `Task` 工具 spawn 一个子 agent，把下面的 prompt 完整传给它。这样主上下文保持干净，且可并行。

调用 `Task` 工具，`subagent_type` 用 `general-purpose`，`prompt` 字段填入下面【生成 prompt】整段（把 `{{DESCRIPTION}}` 替换为用户需求文本）：

---

### 【生成 prompt】（正向分析）—— 传给 Task 子 agent

```
你是一位资深智能体（Agent）系统架构师与 QA 专家，精通 agent_evaluation 业务测试覆盖方法论。

你审视需求时，不把 Agent 视为简单的文本生成器，而是视其为一个具备"目标-感知-规划-记忆-执行"闭环的复杂动态系统。

请仔细阅读下面的【Agent 需求说明】，找出其中隐藏的架构漏洞、死循环风险以及工程落地痛点，并按金融领域测试覆盖框架生成测试维度与场景：

参考覆盖框架（6 类）：
1. 业务场景覆盖 — 按业务功能拆解用户典型场景（账户服务、转账支付、存款、贷款、信用卡、投资理财、投诉售后等）
2. 业务流程覆盖 — 正常路径、替代路径、异常路径
3. 用户角色与意图覆盖 — 身份差异、意图多样性（查询、操作、投诉、闲聊等）
4. 业务规则与约束覆盖 — if-then 逻辑、数值约束、合规要求（如适当性管理、禁止刚性兑付）
5. 输入形态与上下文覆盖 — 不完整信息、错别字、指代消解、多轮上下文
6. 安全与边界覆盖 — 敏感信息泄露、越权操作、提示注入、诱导突破

具体要求：
- 每个测试维度对应上述 6 个覆盖类型之一
- 维度名称应体现具体业务场景（如「账户服务场景覆盖」而非仅「业务场景覆盖」）
- 场景描述需结合需求中的具体功能点
- 每个维度至少包含 2-3 个具体场景
- 维度 ID 用 DIM-001 / DIM-002 ... 顺序编号
- 场景 ID 用 SC-001 / SC-002 ... 顺序编号，并标注所属维度

【Agent 需求说明】：
{{DESCRIPTION}}

请严格按以下 JSON 格式输出（只输出 JSON，不要 markdown 标记，不要解释）：
{
  "dimensions": [
    {"id": "DIM-001", "name": "维度名称", "type": "覆盖类型"}
  ],
  "scenarios": [
    {"id": "SC-001", "dimension": "DIM-001", "name": "子场景", "description": "描述"}
  ],
  "skill_suggestions": [
    {"dimension_id": "DIM-001", "dimension_name": "维度名称", "skill": "所属Skill", "reason": "理由"}
  ]
}

skill 字段从以下选其一：orchestrator / requirements-analysis / test-case-generator / test-executor / test-reporter / 建议 新建。
```

---

### 【生成 prompt】（逆向分析）—— 当用户给的是已有测试用例时

```
你是一个专业的需求分析工程师。你擅长从已有的测试用例集中逆向分析，反推出测试维度和场景，并判断各维度归属于哪个 Skill。

【测试用例集】：
{{TEST_CASES_TEXT}}

请执行：
1. 解析用例结构，按子智能体、意图类型、交互轮次、边界类型等维度对用例聚类
2. 从聚类结果反向归纳出测试维度
3. 判断每个维度应归属到哪个现有 Skill（orchestrator / requirements-analysis / test-case-generator / test-executor / test-reporter）或建议新建

请严格按以下 JSON 格式输出（只输出 JSON，不要 markdown 标记）：
{
  "dimensions": [
    {"id": "DIM-001", "name": "维度名称", "type": "覆盖类型"}
  ],
  "scenarios": [
    {"id": "SC-001", "dimension": "DIM-001", "name": "子场景", "description": "描述"}
  ],
  "skill_suggestions": [
    {"dimension_id": "DIM-001", "dimension_name": "维度名称", "skill": "所属Skill", "reason": "理由"}
  ]
}
```

---

## 第 3 步：校验子 agent 返回的 JSON

子 agent 返回的文本可能裹了 markdown 代码块。你（主 Agent）负责：

1. 剥离 ```json ... ``` 包裹
2. `json.loads` 解析，失败则让 Task 子 agent 重生成（最多 2 次）
3. 校验 `dimensions` 非空、每个维度有 id/name/type；`scenarios` 非空、每个场景有 id/dimension/name
4. 校验所有 scenario.dimension 在 dimensions.id 集合里

## 第 4 步：调机械脚本写 Excel

把校验通过的 JSON 写到临时文件（或通过 stdin），调脚本：

```bash
# 方式 A：stdin 传 JSON（推荐，不留临时文件）
cat <<'EOF' | python ${SKILL_PATH}/scripts/generate_requirements.py --write-stdin --output ${SKILL_PATH}/data/requirements_analysis.xlsx
<把校验通过的 JSON 粘到这里>
EOF

# 方式 B：先写临时文件再传
python ${SKILL_PATH}/scripts/generate_requirements.py --write-file \
  --json-file /tmp/req_analysis.json \
  --output ${SKILL_PATH}/data/requirements_analysis.xlsx
```

脚本 stdout 会输出 JSON 摘要（含 dimensions_count / scenarios_count / dimensions 列表），把它展示给用户。

## 第 5 步：列出维度供用户确认

```bash
python ${SKILL_PATH}/scripts/generate_requirements.py --list ${SKILL_PATH}/data/requirements_analysis.xlsx
```

把维度列表展示给用户，询问：
- 维度是否合理？是否需要增删？
- 进入阶段 2（用例生成）时，每个场景生成几条用例？全部维度还是指定维度？

## 第 5.5 步：testspec 4 表（中间契约，吸收 test-design-agent-raw）

> testspec.md 是需求→用例之间的**中间契约**，给后续用例生成提供有限的词汇表（5 对象分类 / 7 DFX 操作 / 数据维度 / 13 关系类型），避免用例设计发散。
> 设计来源：`docs/PRD_REQUIREMENT_TESTDESIGN.md` § 3.4、`docs/DELTA_GENERAL_TO_AGENT.md` § 4。

第 5 步用户确认维度后，用 Task 工具 spawn 一个子 agent 生成 testspec.md。子 agent 拿到的输入是：UC 块（第 1.5 步产出的 `data/uc_blocks.md`）+ 已确认的 dimensions/scenarios（第 5 步后的 JSON）。

### 4 张表的内容

**表 1：测试对象（5 分类）** — 把 UC 里的对象归类，每个分类有固定命名和 ID 前缀：

| 分类 | 命名 | ID | Agent 扩展 |
|------|------|----|-----------|
| 业务场景类 | "xx 业务场景" | `TestObject-Scenario-NNN` | → dimension |
| 平台能力类 | "xx 能力" | `TestObject-Capability-NNN` | → Agent 工具能力 |
| 数据智能类 | "xx 数据分析" | `TestObject-DataIntel-NNN` | → Agent 推理能力 |
| 安全合规类 | | `TestObject-Security-NNN` | → `business_rules` |
| 架构支撑类 | | `TestObject-Architecture-NNN` | → workflow/advisor 链 |

**表 2：测试操作（7 DFX 类型，动宾结构）** — 每个操作关联一个 DFX 维度，ID 前缀带 DFX 类型：

| DFX | 前缀 | Agent 扩展 |
|-----|------|-----------|
| 功能 FUN | `TestOperation-FUN-NNN` | → `expected_tools` |
| 可靠性 DFR | `TestOperation-DFR-NNN` | → fallback 场景 |
| 性能 DFP | `TestOperation-DFP-NNN` | → `expected_steps` |
| 安全 DFS | `TestOperation-DFS-NNN` | → forbidden tools |
| 兼容性 DFC | `TestOperation-DFC-NNN` | → 多 Agent 版本 |
| 数据智能 DFAI | `TestOperation-DFAI-NNN` | → 推理断言 |
| 业务交互 DFINT | `TestOperation-DFINT-NNN` | → 跨系统场景 |

**表 3：测试数据** — 列名固定为 `测试对象 / 参数 / 取值范围 / 默认值 / 单位 / 描述`。是后续等价类/边界值用例的数据来源。

**表 4：关系（13 类型）** — 6 应用组合关系（先后依赖 / 前者影响后者 / 同时发生 / 共享 / 约束 / 互斥）+ 7 实现依赖关系（异步无同步 / 乱序 / 超时 / 消息交互 / 共享数据缺陷 / 独占资源 / 死锁）。关系表是场景用例（`SCN_` 前缀）的生成依据。

### 【生成 prompt】（testspec 4 表）—— 传给 Task 子 agent

```
你是测试架构师。请基于下面的【UC 块】和【已确认的维度与场景】生成 testspec.md，包含 4 张 markdown 表：测试对象（5 分类）/ 测试操作（7 DFX）/ 测试数据 / 关系（13 类型）。

【UC 块】（来自第 1.5 步）：
{{UC_BLOCKS_MD}}

【已确认的维度与场景】（来自第 5 步）：
{{DIMENSIONS_SCENARIOS_JSON}}

要求：
- 测试对象表：每个 UC 块至少 1 个对象，按 5 分类归类，ID 用 TestObject-<Type>-NNN
- 测试操作表：动宾结构命名（如"加载贷款申请""分析流水""检查负债比"），DFX 类型从前述 7 类选，ID 用 TestOperation-<DFX>-NNN
- 测试数据表：每个有数值/字符串参数的对象列 1 行，标注取值范围（如金额 0-10000000、期限 1-360 月）
- 关系表：6 应用组合 + 7 实现依赖，按实际场景列关系对（如：贷款申请-风险审查：先后依赖；风险审查-放款：约束关系）
- 严格 markdown 表格输出，4 张表之间用 ## 标题分隔，不要解释
```

子 agent 返回的 testspec markdown 保存到 `${SKILL_PATH}/data/testspec.md`。这份文件在第 2 阶段（用例生成）被 `test-case-generator` 子 skill 消费，作为因子提取和用例类型前缀（FUN_/SCN_/DFX_）的来源。

## 与 agent-eval 主能力的衔接

本阶段产出 `requirements_analysis.xlsx`，是后续所有阶段的输入。它**不直接**进入 agent-eval 的 eval loop（eval loop 消费的是 cases YAML + UATR trace）。桥接发生在阶段 3 之后：`excel_to_uatr.py` 把执行结果转成 UATR trace 喂给 diagnoser/multi_judge/optimizer。

## 重要约束

- ❌ 本子 skill 不许调任何外部 LLM API（OpenAI / DeepSeek / 自建模型 URL 一律不许）
- ❌ 不许在脚本里拼 prompt
- ✅ prompt 在本文件里以文字呈现
- ✅ 生成工作由 Agent 自己做，或用 Task 工具委派给子 agent
- ✅ 脚本只做 JSON → Excel 的机械写入 + list + read
- ✅ UC 块（第 1.5 步）和 testspec 4 表（第 5.5 步）是 markdown 文本，由 Task 子 agent 直接产出，不需要脚本写入
- ✅ UC 字段 7/9/10/12 必须在 testspec 和后续 cases YAML 中保留可追溯映射（见第 1.5 步映射规则表）
- ✅ testspec 4 表的对象/操作 ID 前缀（TestObject-<Type>-NNN / TestOperation-<DFX>-NNN）必须与第 2 阶段用例的 tc_id 前缀（FUN_/SCN_/DFX_）保持类型一致
